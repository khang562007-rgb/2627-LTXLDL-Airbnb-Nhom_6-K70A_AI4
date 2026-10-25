"""
Thứ tự chạy, từ gốc repo:
    python src/download.py                                            # tải data/raw/<mốc>/...
    python src/flag_price_calendar.py --config configs/porto.yaml     # lọc 1.000 listing + gắn cờ

"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

CHUNKSIZE = 1_000_000          # calendar thô có hàng triệu dòng nên đọc theo khối


# ---------- đọc và lọc theo ids ----------
def read_listings(path, id_set):
    lst = pd.read_csv(path, usecols=["id", "price", "minimum_nights", "availability_365"],
                      dtype={"id": "str", "price": "str"})
    return lst[lst["id"].isin(id_set)].reset_index(drop=True)


def read_calendar(path, id_set):
    parts = []
    for chunk in pd.read_csv(path, usecols=["listing_id", "date", "available", "minimum_nights", "maximum_nights"],
                             dtype={"listing_id": "str"}, chunksize=CHUNKSIZE):
        parts.append(chunk[chunk["listing_id"].isin(id_set)])
    return pd.concat(parts, ignore_index=True)


# ---------- cờ trên listings ----------
def price_type(df):
    file = df.copy()
    file["flagged_price_type"] = file["price"].str.contains(r"[^0-9.\-]", na=False)
    file["price_clean"] = pd.to_numeric(file["price"].str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
    return file


def price_missing(df):
    file = df.copy()
    file["flagged_price_missing"] = file["price_clean"].isna()
    return file


def price_outlier(df, k):
    file = df.copy()
    valid = file["price_clean"].where(file["price_clean"] > 0)   # chỉ giữ giá dương để tính Q1, Q3
    q1, q3 = valid.quantile(0.25), valid.quantile(0.75)
    upper = q3 + k * (q3 - q1)
    file["flagged_price_outlier"] = (file["price_clean"] <= 0) | (file["price_clean"] > upper)
    return file


def min_nights_outlier(df, cap):
    file = df.copy()
    file["flagged_min_nights_outlier"] = file["minimum_nights"] > cap
    return file


def long_stay_listing(df, threshold):
    file = df.copy()
    file["flagged_long_stay_listing"] = file["minimum_nights"] >= threshold
    return file


def availability_out_of_range(df, low, high):
    file = df.copy()
    file["flagged_availability_out_of_range"] = (file["availability_365"] < low) | (file["availability_365"] > high)
    return file


def price_jump(df, last_price, ratio):
    """last_price: Series (index = id) giá hợp lệ gần nhất của mỗi listing ở các mốc trước."""
    file = df.copy()
    if last_price is None:                # mốc đầu tiên: chưa có mốc trước để so
        file["flagged_price_jump"] = False
        return file
    now = file["price_clean"].where(file["price_clean"] > 0)
    before = file["id"].map(last_price)
    r = now / before
    file["flagged_price_jump"] = (r > ratio) | (r < 1 / ratio)
    return file


# ---------- cờ trên calendar ----------
def calendar_available_type(df):
    file = df.copy()
    file["flagged_available_type"] = (file["available"] != "t") & (file["available"] != "f")
    return file


def calendar_dup_key(df):
    file = df.copy()
    file["flagged_dup_key"] = file.duplicated(subset=["listing_id", "date"], keep=False)
    return file


def calendar_days_wrong(df, ids, expected_days):
    n_days = df.groupby("listing_id")["date"].nunique().reindex(ids).fillna(0).astype(int)
    return pd.DataFrame({
        "listing_id": ids,
        "n_days": n_days.values,
        "flagged_days_wrong": (n_days != expected_days).values,
    })

def calendar_min_nights_outlier(df, cap):
    file = df.copy()
    file["flagged_cal_min_nights_outlier"] = file["minimum_nights"] > cap
    return file


def calendar_max_nights_outlier(df, cap):
    file = df.copy()
    file["flagged_cal_max_nights_outlier"] = file["maximum_nights"] > cap
    return file


def calendar_nights_inconsistent(df):
    file = df.copy()
    file["flagged_nights_inconsistent"] = file["maximum_nights"] < file["minimum_nights"]
    return file
# ---------- pipeline ----------
def check_inputs(cfg):
    paths = [cfg["ids"]]
    for snap in cfg["snapshots"]:
        paths.append(cfg["listings_file"].format(snap=snap))
        paths.append(cfg["calendar_file"].format(snap=snap))
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        raise FileNotFoundError("Thieu file dau vao (chay src/download.py truoc, hoac kiem tra duong dan trong config):\n  "
                                + "\n  ".join(missing))


def run(cfg, out_dir="data/processed", report_dir="reports"):
    check_inputs(cfg)
    ids = pd.read_csv(cfg["ids"], dtype={"listing_id": "str"})["listing_id"].drop_duplicates().tolist()
    id_set = set(ids)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(report_dir).mkdir(parents=True, exist_ok=True)

    rows = []
    last_price = None                              # giá hợp lệ gần nhất của mỗi listing (cho price_jump)
    for snap in cfg["snapshots"]:
        # --- listings: đọc một lần, lọc theo ids ---
        lst = read_listings(cfg["listings_file"].format(snap=snap), id_set)
        lst = price_type(lst)
        lst = price_missing(lst)
        lst = price_outlier(lst, cfg["price_iqr_k"])
        lst = min_nights_outlier(lst, cfg["min_nights_cap"])
        lst = long_stay_listing(lst, cfg["long_stay_threshold"])
        lst = availability_out_of_range(lst, cfg["availability_min"], cfg["availability_max"])
        lst = price_jump(lst, last_price, cfg["price_jump_ratio"])
        valid = lst.drop_duplicates("id").set_index("id")["price_clean"]
        valid = valid.where(valid > 0).dropna()
        last_price = valid if last_price is None else valid.combine_first(last_price)

        # --- calendar: đọc một lần, lọc theo ids, lưu bản đã lọc ---
        cal = read_calendar(cfg["calendar_file"].format(snap=snap), id_set)
        cal.to_csv(Path(out_dir) / f"calendar_{snap}.csv", index=False)
        cal = calendar_available_type(cal)
        cal = calendar_dup_key(cal)
        cal = calendar_min_nights_outlier(cal, cfg["min_nights_cap"])
        cal = calendar_max_nights_outlier(cal, cfg["max_nights_cap"])
        cal = calendar_nights_inconsistent(cal)
        days = calendar_days_wrong(cal, ids, cfg["expected_days"])

        # --- cảnh báo ---
        n_not_found = len(id_set - set(lst["id"]))
        if n_not_found:
            print(f"[CANH BAO] {snap}: {n_not_found}/{len(ids)} id khong co trong listings cua mot nay")
        if lst["price_clean"].isna().all():
            print(f"[CANH BAO] {snap}: khong co gia nao, cac co gia khong danh gia duoc o mot nay")

        # --- ghi kết quả ---
        lst.to_csv(Path(out_dir) / f"flags_listings_{snap}.csv", index=False)
        days.to_csv(Path(out_dir) / f"flags_calendar_{snap}.csv", index=False)
        row_flags = [c for c in cal.columns if c.startswith("flagged_")]
        bad_rows = cal[cal[row_flags].any(axis=1)]        
        bad_rows.to_csv(Path(out_dir) / f"flags_calendar_rows_{snap}.csv", index=False)
        counts = {c: int(t[c].sum()) for t in (lst, cal, days) for c in t.columns if c.startswith("flagged_")}
        rows.append({"snapshot": snap, "n_listings": len(lst), "n_calendar_rows": len(cal), **counts})

    summary = pd.DataFrame(rows)
    summary.to_csv(Path(report_dir) / "flags_summary.csv", index=False)
    print(summary.T.to_string(header=False))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        run(yaml.safe_load(f))