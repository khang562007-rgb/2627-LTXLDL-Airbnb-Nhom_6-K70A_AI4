"""QA cờ giá và calendar trên các bảng đã lọc; báo cáo theo schema của qa.py.

Chạy từ gốc repo: python src/flag_price_calendar.py [--config configs/porto.yaml]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit_flags import audit_table, check_collisions, sample_flagged
import pandas as pd
import yaml
RULES = {
    "price_type": ("flag", "listings", "price chứa ký tự không thuộc định dạng số", "Sai kiểu giá", "Tạo price_clean, giữ nguyên price"),
    "price_missing": ("flag", "listings", "price thiếu hoặc không parse được", "Thiếu giá", "Gắn cờ"),
    "price_outlier": ("flag", "listings", "price <= 0 hoặc vượt Q3 + k*IQR", "Giá ngoại lệ", "Gắn cờ"),
    "min_nights_outlier": ("flag", "listings", "minimum_nights vượt ngưỡng cấu hình", "Giá trị lưu trú bất thường", "Gắn cờ"),
    "long_stay_listing": ("flag", "listings", "minimum_nights >= long_stay_threshold", "Listing thiên về lưu trú dài hạn", "Gắn cờ"),
    "availability_out_of_range": ("flag", "listings", "availability_365 ngoài miền cấu hình", "Số ngày sẵn sàng không hợp lệ", "Gắn cờ"),
    "price_jump": ("flag", "listings", "giá hợp lệ tăng/giảm quá price_jump_ratio so với mốc trước", "Giá biến động mạnh giữa các mốc", "Gắn cờ"),
    "available_type": ("flag", "calendar", "available không thuộc t/f", "Sai kiểu khả dụng", "Gắn cờ"),
    "calendar_dup_key": ("flag", "calendar", "trùng khóa (listing_id, date)", "Khóa ngày trùng", "Gắn cờ"),
    "calendar_days_wrong": ("flag", "calendar", "số ngày khác expected_days", "Chuỗi ngày không đủ hoặc thừa", "Gắn cờ theo listing_id"),
    "cal_min_nights_outlier": ("flag", "calendar", "minimum_nights vượt ngưỡng cấu hình", "Giá trị lưu trú bất thường", "Gắn cờ"),
    "cal_max_nights_outlier": ("flag", "calendar", "maximum_nights vượt ngưỡng cấu hình", "Giá trị lưu trú bất thường", "Gắn cờ"),
    "nights_inconsistent": ("flag", "calendar", "maximum_nights < minimum_nights", "Mâu thuẫn số đêm", "Gắn cờ"),
}
LISTING_RULES = list(RULES)[:7]
CALENDAR_ROW_RULES = [
    "available_type",
    "calendar_dup_key",
    "cal_min_nights_outlier",
    "cal_max_nights_outlier",
    "nights_inconsistent",
]
report = []


def add(rule, snap, total, flagged, note=""):
    kind, table, cond, why, act = RULES[rule]
    report.append(dict(rule=rule, kind=kind, table=table, snapshot=snap,
                       condition=cond, reason=why, action=act,
                       rows_total=int(total), rows_flagged=int(flagged), note=note))


def find_file(folder, prefix, snap):
    for ext in (".csv.gz", ".csv"):
        path = folder / f"{prefix}_{snap}{ext}"
        if path.exists():
            return path
    raise FileNotFoundError(f"Thiếu {prefix}_{snap}.csv(.gz) trong {folder}; hãy chạy filter_all.py trước")


def flag_listings(df, q, last_price):
    out = df.copy()
    raw = out["price"].astype("string")
    out["price_type"] = raw.notna() & raw.str.contains(r"[^0-9.\-]", na=False)
    out["price_clean"] = pd.to_numeric(raw.str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
    out["price_missing"] = out["price_clean"].isna()
    positive = out["price_clean"].where(out["price_clean"] > 0)
    q1, q3 = positive.quantile([.25, .75])
    upper = q3 + q.get("price_iqr_k", 2) * (q3 - q1)
    out["price_outlier"] = (out["price_clean"] <= 0) | (out["price_clean"] > upper)
    minimum = pd.to_numeric(out["minimum_nights"], errors="coerce")
    out["min_nights_outlier"] = minimum > q.get("min_nights_cap", 365)
    out["long_stay_listing"] = minimum >= q.get("long_stay_threshold", 30)
    available = pd.to_numeric(out["availability_365"], errors="coerce")
    out["availability_out_of_range"] = ~available.between(q.get("availability_min", 0), q.get("availability_max", 365))
    if last_price is None:
        out["price_jump"] = False
    else:
        prior = out["id"].map(last_price)
        ratio = out["price_clean"] / prior
        limit = q.get("price_jump_ratio", 2)
        out["price_jump"] = (ratio > limit) | (ratio < 1 / limit)
    return out


def flag_calendar(df, ids, q):
    out = df.copy()
    available = out["available"].astype("string").str.lower()
    out["available_type"] = ~available.isin(["t", "f"])
    out["calendar_dup_key"] = out.duplicated(["listing_id", "date"], keep=False)
    minimum = pd.to_numeric(out["minimum_nights"], errors="coerce")
    maximum = pd.to_numeric(out["maximum_nights"], errors="coerce")
    out["cal_min_nights_outlier"] = minimum > q.get("min_nights_cap", 365)
    out["cal_max_nights_outlier"] = maximum > q.get("max_nights_cap", 1125)
    out["nights_inconsistent"] = maximum < minimum
    counts = out.groupby("listing_id")["date"].nunique().reindex(ids).fillna(0).astype(int)
    days = pd.DataFrame({"listing_id": ids, "n_days": counts.to_numpy()})
    days["calendar_days_wrong"] = days["n_days"].ne(q.get("expected_days", 365))
    return out, days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/porto.yaml")
    cfg = yaml.safe_load((ROOT / ap.parse_args().config).open(encoding="utf-8"))
    q = cfg.get("qa", {}).get("price_calendar", {})
    q = {**q, "expected_days": cfg.get("expected_days", 365)}
    interim, processed = ROOT / cfg["paths"]["interim"], ROOT / cfg["paths"]["processed"]
    processed.mkdir(parents=True, exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    report.clear()
    last_price = None
    ids_path = ROOT / cfg["sample"]["listing_ids_path"]
    ids_frame = pd.read_csv(ids_path, dtype=str)
    ids_col = "listing_id" if "listing_id" in ids_frame else "id"
    ids = ids_frame[ids_col].dropna().drop_duplicates().tolist()
    for snap in cfg["snapshots"]:
        listings = pd.read_csv(find_file(interim, "listings", snap), dtype={"id": str}, low_memory=False)
        listings = flag_listings(listings, q, last_price)
        for rule in LISTING_RULES:
            add(rule, snap, len(listings), listings[rule].sum())
        current = listings.drop_duplicates("id").set_index("id")["price_clean"]
        current = current.where(current > 0).dropna()
        last_price = current if last_price is None else current.combine_first(last_price)
        cal = pd.read_csv(find_file(interim, "calendar", snap), dtype={"listing_id": str}, low_memory=False)
        cal, days = flag_calendar(cal, ids, q)
        for rule in CALENDAR_ROW_RULES:
            add(rule, snap, len(cal), cal[rule].sum())
        add("calendar_days_wrong", snap, len(days), days["calendar_days_wrong"].sum())
        listings[["id"] + LISTING_RULES + ["price_clean"]].to_csv(
            processed / f"listings_price_flags_{snap}.csv.gz", index=False, encoding="utf-8-sig")
        cal[["listing_id", "date"] + CALENDAR_ROW_RULES].to_csv(
            processed / f"calendar_row_flags_{snap}.csv.gz", index=False, encoding="utf-8-sig")
        days.to_csv(processed / f"calendar_listing_flags_{snap}.csv", index=False, encoding="utf-8-sig")
    rep = pd.DataFrame(report)
    rep.to_csv(ROOT / "reports" / "qa_report_price_calendar.csv", index=False, encoding="utf-8-sig")
    print(rep[["rule", "snapshot", "rows_total", "rows_flagged"]].to_string(index=False))


if __name__ == "__main__":
    main()