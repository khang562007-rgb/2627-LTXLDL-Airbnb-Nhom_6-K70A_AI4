"""Cờ chỗ ở, calendar vs listing và cờ giữa các mốc (Bạn 3), chỉ trên dữ liệu nhóm được giao.
Cần có sẵn trong data/interim/ (do bước lọc tạo ra), hoặc truyền thư mục đầu vào bằng --interim:
    listings_<mốc>.csv(.gz)   và   calendar_<mốc>.csv(.gz)
Chạy từ gốc repo:  python src/flag_property_cross.py [--config configs/porto.yaml] [--interim data/interim]
Kết quả:
    data/processed/listings_property_flags_<mốc>.csv.gz   (id + các cột cờ + bathrooms_clean)
    reports/qa_report_property.csv                          (cùng cột với qa_report_reviews.csv)
"""
import argparse
import json
import re
from pathlib import Path
from src.audit_flags import audit_table, check_collisions, sample_flagged
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
ID = "id"  # khoá của bảng listings

# tên: (loại, bảng, điều kiện, lý do, hành động)  -- cùng dạng với RULES của qa.py (reviews)
RULES = {
    "room_type_category": ("flag", "listings", "room_type ngoài danh mục room_types (hoặc thiếu)",
                           "Danh mục lạ", "Gắn cờ"),
    "property_type_rare": ("flag", "listings", "property_type chiếm dưới property_type_min_share của mốc",
                           "Loại quá hiếm, khó so sánh", "Gắn cờ"),
    "capacity_outlier": ("flag", "listings", "accommodates thiếu, <1 hoặc > capacity_max",
                         "Sức chứa vô lý", "Gắn cờ"),
    "bedrooms_beds_inconsistent": ("flag", "listings", "bedrooms > accommodates, hoặc beds = 0",
                                   "Mâu thuẫn giữa phòng ngủ/giường và sức chứa", "Gắn cờ"),
    "bathrooms_type": ("flag", "listings", "cột bathrooms thiếu hoặc không phải số",
                       "Sai kiểu", "Tạo cột bathrooms_clean (parse từ bathrooms_text), giữ nguyên cột gốc"),
    "amenities_parse": ("flag", "listings", "amenities không parse được thành danh sách JSON",
                        "Không đếm được tiện nghi", "Gắn cờ"),
    "calendar_vs_listing": ("flag", "listings", "listing không có dòng nào trong calendar cùng mốc",
                            "Hai bảng không khớp ID", "Gắn cờ (số dòng calendar mồ côi ghi ở note)"),
    "attr_changed": ("flag", "listings", "cùng id nhưng attr_cols khác nhau giữa các mốc",
                     "Thuộc tính đổi theo thời gian", "Gắn cờ"),
    "coord_drift": ("flag", "listings", "toạ độ cùng id lệch hơn coord_drift_m mét giữa các mốc",
                    "Toạ độ không ổn định", "Gắn cờ"),
    "reviews_decrease": ("flag", "listings", "number_of_reviews giảm so với mốc liền trước",
                         "Số review tích luỹ lẽ ra chỉ tăng", "Gắn cờ"),
}
report = []


def add(rule, snap, total, flagged, note=""):
    kind, table, cond, why, act = RULES[rule]
    report.append(dict(rule=rule, kind=kind, table=table, snapshot=snap,
                       condition=cond, reason=why, action=act,
                       rows_total=int(total), rows_flagged=int(flagged), note=note))


def _q(cfg, key, default):
    """Ngưỡng nằm ở cfg['qa']['property'][key]; chưa có trong config thì dùng mặc định."""
    return cfg.get("qa", {}).get("property", {}).get(key, default)


def find_file(folder, prefix, snap):
    """File đã lọc ở bước trước (nhận .csv.gz và .csv). Thiếu thì dừng, không dùng dữ liệu thô."""
    for ext in (".csv.gz", ".csv"):
        p = folder / f"{prefix}_{snap}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"Thiếu {prefix}_{snap}.csv(.gz) trong {folder} - cần chạy bước lọc trước")


def resolve_interim(configured, snapshots, explicit=None):
    """Tìm thư mục có đủ listings/calendar; ưu tiên --interim hoặc config, rồi DATA cạnh repo."""
    if explicit:
        folder = Path(explicit)
        return folder if folder.is_absolute() else ROOT / folder

    candidates = [ROOT / configured, ROOT / "DATA", ROOT.parent / "DATA"]
    for folder in candidates:
        if all(
            any((folder / f"{prefix}_{snap}{ext}").exists()
                for ext in (".csv.gz", ".csv"))
            for snap in snapshots
            for prefix in ("listings", "calendar")
        ):
            return folder
    return candidates[0]


def _col(df, name):
    """Lấy cột; mốc nào thiếu cột (schema drift) thì trả về cột toàn NaN."""
    return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)


# ---------- nhóm 1: cờ cho từng mốc (hàm nhận df, cfg và trả về mask True/False) ----------

def flag_room_type_category(df, cfg):
    valid = _q(cfg, "room_types", ["Entire home/apt", "Private room", "Shared room", "Hotel room"])
    return ~df["room_type"].isin(valid)          # NaN không nằm trong danh sách nên cũng bị cờ


def flag_property_type_rare(df, cfg):
    share = df["property_type"].value_counts(normalize=True)
    rare = share[share < _q(cfg, "property_type_min_share", 0.005)].index
    return df["property_type"].isin(rare)


def flag_capacity_outlier(df, cfg):
    return ~df["accommodates"].between(1, _q(cfg, "capacity_max", 16))   # NaN => False => bị cờ


def flag_bedrooms_beds_inconsistent(df, cfg):
    return (df["bedrooms"] > df["accommodates"]) | (df["beds"] == 0)     # so với NaN ra False


def _parse_bathrooms_text(text):
    """'1.5 baths' -> 1.5 ; 'Half-bath' -> 0.5 ; không hiểu -> NaN."""
    if not isinstance(text, str):
        return np.nan
    m = re.search(r"\d+(\.\d+)?", text)
    if m:
        return float(m.group())
    return 0.5 if "half" in text.lower() else np.nan


def flag_bathrooms_type(df, cfg):
    original = pd.to_numeric(_col(df, "bathrooms"), errors="coerce")
    df["bathrooms_clean"] = original.fillna(_col(df, "bathrooms_text").apply(_parse_bathrooms_text))
    return original.isna()


def _can_parse_list(x):
    if not isinstance(x, str):
        return False
    try:
        return isinstance(json.loads(x), list)
    except ValueError:
        return False


def flag_amenities_parse(df, cfg):
    return ~_col(df, "amenities").apply(_can_parse_list).astype(bool)


PER_SNAPSHOT_FLAGS = [
    ("room_type_category", flag_room_type_category),
    ("property_type_rare", flag_property_type_rare),
    ("capacity_outlier", flag_capacity_outlier),
    ("bedrooms_beds_inconsistent", flag_bedrooms_beds_inconsistent),
    ("bathrooms_type", flag_bathrooms_type),
    ("amenities_parse", flag_amenities_parse),
]


# ---------- nhóm 2: calendar vs listing ----------

def flag_calendar_vs_listing(listings, calendar):
    """(mask listings: không có trong calendar, mask calendar: id không có trong listings)."""
    return (~listings[ID].isin(set(calendar["listing_id"])),
            ~calendar["listing_id"].isin(set(listings[ID])))


# ---------- nhóm 3: giữa các mốc (hàm nhận dict {mốc: df}, trả về {mốc: mask}) ----------

def _stack(by_snap, cols):
    parts = []
    for snap, df in by_snap.items():
        part = df[[ID] + cols].copy()
        part["snapshot"] = snap
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _ids_to_masks(by_snap, bad_ids):
    return {snap: df[ID].isin(bad_ids) for snap, df in by_snap.items()}


def flag_attr_changed(by_snap, cfg):
    cols = _q(cfg, "attr_cols", ["room_type", "property_type", "bedrooms"])
    n_values = _stack(by_snap, cols).groupby(ID)[cols].nunique(dropna=False)
    return _ids_to_masks(by_snap, n_values.index[(n_values > 1).any(axis=1)])


def flag_coord_drift(by_snap, cfg):
    g = _stack(by_snap, ["latitude", "longitude"]).groupby(ID)
    lat_m = (g["latitude"].max() - g["latitude"].min()) * 111_000
    lon_m = (g["longitude"].max() - g["longitude"].min()) * 111_000 * np.cos(np.radians(g["latitude"].mean()))
    drift_m = np.sqrt(lat_m ** 2 + lon_m ** 2)
    return _ids_to_masks(by_snap, drift_m.index[drift_m > _q(cfg, "coord_drift_m", 200)])


def flag_reviews_decrease(by_snap, cfg):
    wide = _stack(by_snap, ["number_of_reviews"]).pivot_table(
        index=ID, columns="snapshot", values="number_of_reviews", aggfunc="max")
    wide = wide[sorted(wide.columns)]
    decreased = wide < wide.ffill(axis=1).shift(1, axis=1)
    return {snap: df[ID].map(decreased[snap]).eq(True) for snap, df in by_snap.items()}


CROSS_FLAGS = [
    ("attr_changed", flag_attr_changed),
    ("coord_drift", flag_coord_drift),
    ("reviews_decrease", flag_reviews_decrease),
]


# ---------- điều phối ----------

def run(tables, cfg):
    """tables = {"listings": {mốc: df}, "calendar": {mốc: df}}. Thêm cột cờ vào listings và ghi report."""
    report.clear()
    listings, calendar = tables["listings"], tables.get("calendar", {})

    for snap, df in listings.items():
        for name, func in PER_SNAPSHOT_FLAGS:
            df[name] = func(df, cfg)
            note = ""
            if name == "bathrooms_type":
                note = f"còn thiếu sau khi sửa: {int(df['bathrooms_clean'].isna().sum())}"
            add(name, snap, len(df), df[name].sum(), note)

    for snap, cal in calendar.items():
        if snap in listings:
            lm, cm = flag_calendar_vs_listing(listings[snap], cal)
            listings[snap]["calendar_vs_listing"] = lm
            add("calendar_vs_listing", snap, len(lm), lm.sum(),
                f"dòng calendar có id lạ: {int(cm.sum())}/{len(cm)}")

    for name, func in CROSS_FLAGS:
        for snap, mask in func(listings, cfg).items():
            listings[snap][name] = mask
            add(name, snap, len(mask), mask.sum())
    return tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/porto.yaml")
    ap.add_argument(
        "--interim",
        help="Thư mục chứa listings_<mốc> và calendar_<mốc>; mặc định ưu tiên config, tự tìm DATA nếu thiếu.",
    )
    args = ap.parse_args()
    cfg = yaml.safe_load(open(ROOT / args.config, encoding="utf-8"))
    interim = resolve_interim(cfg["paths"]["interim"], cfg["snapshots"], args.interim)
    processed = ROOT / cfg["paths"]["processed"]
    processed.mkdir(parents=True, exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)

    tables = {"listings": {}, "calendar": {}}
    for snap in cfg["snapshots"]:
        tables["listings"][snap] = pd.read_csv(find_file(interim, "listings", snap),
                                               dtype={"id": str}, low_memory=False)
        # calendar rất lớn, ở đây chỉ cần listing_id
        tables["calendar"][snap] = pd.read_csv(find_file(interim, "calendar", snap),
                                               usecols=["listing_id"], dtype={"listing_id": str})
    run(tables, cfg)

    for snap, df in tables["listings"].items():
        cols = [ID] + [c for c in RULES if c in df.columns] + ["bathrooms_clean"]
        df[cols].to_csv(processed / f"listings_property_flags_{snap}.csv.gz",
                        index=False, encoding="utf-8-sig")

    rep = pd.DataFrame(report)
    rep.to_csv(ROOT / "reports" / "qa_report_property.csv", index=False, encoding="utf-8-sig")
    print(rep[["rule", "snapshot", "rows_total", "rows_flagged"]].to_string(index=False))


if __name__ == "__main__":
    main()
