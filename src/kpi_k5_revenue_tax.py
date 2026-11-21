"""K5: doanh thu ước tính và thuế du lịch tiềm năng, theo khu x mốc, xuất dạng long format.

Dùng trong code:   from kpi5 import run;  kpi, sens, checks = run(cfg)
Chạy dòng lệnh:    python src/kpi5.py --config configs/porto.yaml

Mô hình số đêm (cho mỗi listing):
    Bookings      = Reviews_L365 / review_rate                (Reviews_L365 = number_of_reviews_ltm)
    Stay Used     = max(Average Stay, minimum_nights)
    Booked Nights = Bookings x Stay Used                      (thô)
    Trần          = min(365, occupancy_cap x 365, Q3 + k x IQR của số đêm thô)   -> Estimated Occupancy <= 70%
Doanh thu = Booked Nights x price_clean.  Thuế = Booked Nights x mức thuế của nhóm (ngắn ngày / dài ngày).
Calendar chỉ dùng để đối chiếu (bảng checks), không ép số đêm khớp số ngày unavailable.

Đầu ra:
    data/processed/kpi_<id>_<slug>.csv    (schema long format của nhóm)
    reports/k05_sensitivity.csv           (Average Stay = 2, 3, 5)
    reports/k05_checks.csv                (kiểm tra ngoại lệ và đối chiếu calendar)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from src.kpi_k6_commercial_share import load_area_map
except ImportError:
    from kpi_k6_commercial_share import load_area_map

COLUMNS = ["kpi_id", "kpi_name", "snapshot", "neighbourhood_cleansed", "period",
           "value", "unit", "currency", "n_used", "n_excluded"]


def get_measures(currency: str):
    cur = currency or "EUR"
    cur_yr = f"{cur}/year"
    return [  # (kpi_name, cột trong bảng tổng hợp, unit, currency, số chữ số thập phân)
        ("estimated_booked_nights", "nights", "nights/year", "", 1),
        ("estimated_occupancy", "occ", "%", "", 1),
        ("estimated_revenue", "revenue", cur_yr, cur, 2),
        ("estimated_revenue_short_stay", "rev_short", cur_yr, cur, 2),
        ("estimated_revenue_long_stay", "rev_long", cur_yr, cur, 2),
        ("tourist_tax_potential_all", "tax_all", cur_yr, cur, 2),
        ("tourist_tax_potential_licensed", "tax_lic", cur_yr, cur, 2),
        ("tourist_tax_short_stay", "tax_short", cur_yr, cur, 2),
        ("tourist_tax_long_stay", "tax_long", cur_yr, cur, 2),
        ("price_outlier_listings", "out_n", "listings", "", 0),
        ("price_outlier_revenue", "out_rev", cur_yr, cur, 2),
    ]
DEFAULTS = {"id": "K05", "slug": "revenue_tax", "review_rate": 0.5, "average_stay_nights": 3,
            "sensitivity_average_stay": [2, 3, 5], "occupancy_cap": 0.70, "max_nights_per_year": 365,
            "use_iqr_fence": True, "iqr_k": 1.5,
            "tourist_tax_per_night": {"short_stay": 3, "long_stay": 3}, "license_exempt_values": ["exempt"]}


# ---------- mô hình ----------
def estimate_nights(df, avg_stay, review_rate):
    bookings = df["reviews_l365"] / review_rate
    stay_used = np.maximum(avg_stay, df["minimum_nights"].fillna(avg_stay))
    return bookings * stay_used


def cap_nights(raw, p):
    cap = min(p["max_nights_per_year"], p["occupancy_cap"] * 365)
    if p["use_iqr_fence"] and len(raw) > 0:
        q1, q3 = raw.quantile(0.25), raw.quantile(0.75)
        cap = min(cap, q3 + p["iqr_k"] * (q3 - q1))
    return raw.clip(upper=cap), cap


# ---------- dữ liệu ----------
def _find_table(folder: Path, prefix: str, snap: str) -> Path | None:
    for ext in (".csv.gz", ".csv"):
        p = folder / f"{prefix}_{snap}{ext}"
        if p.exists():
            return p
    return None


def prepare(snap, cfg, area_map, p):
    processed = Path(cfg["paths"]["processed"])
    interim = Path(cfg["paths"]["interim"])
    flags_path = _find_table(processed, "listings_price_flags", snap) or _find_table(processed, "flags_listings", snap)
    if flags_path is None:
        raise FileNotFoundError(
            f"Thiếu file cờ giá cho mốc {snap} trong {processed} (chạy src/flag_price_calendar.py trước)"
        )
    flags = pd.read_csv(flags_path, dtype={"id": "str"})
    for col in ("long_stay_listing", "price_outlier", "availability_out_of_range", "min_nights_outlier"):
        if f"flagged_{col}" not in flags.columns and col in flags.columns:
            flags[f"flagged_{col}"] = flags[col]

    interim_ls = _find_table(interim, "listings", snap)
    base_cols = ["id", "minimum_nights", "availability_365", "number_of_reviews_ltm", "license", "analysis_area"]
    if interim_ls is not None:
        avail_cols = [c for c in base_cols if c in pd.read_csv(interim_ls, nrows=0).columns]
        raw = pd.read_csv(interim_ls, usecols=avail_cols, dtype={"id": "str", "license": "str"})
    else:
        raw = pd.read_csv(
            cfg["listings"]["raw_file"].format(snap=snap),
            usecols=["id", "minimum_nights", "availability_365", "number_of_reviews_ltm", "license"],
            dtype={"id": "str", "license": "str"},
        )
    extra_cols = [c for c in raw.columns if c == "id" or c not in flags.columns]
    df = flags.merge(raw.drop_duplicates("id")[extra_cols], on="id", how="left")
    df["reviews_l365"] = df["number_of_reviews_ltm"]
    if "analysis_area" not in df.columns or df["analysis_area"].isna().any():
        df["analysis_area"] = df["id"].map(area_map)
    lic = df["license"].astype("string").str.strip().str.lower()
    df["has_license"] = df["license"].notna() & ~lic.isin([v.lower() for v in p["license_exempt_values"]])
    df["segment"] = np.where(df["flagged_long_stay_listing"], "long_stay", "short_stay")
    df["used"] = df["price_clean"].gt(0)              # thiếu giá hoặc giá <= 0 thì loại, ghi n_excluded
    return df


def aggregate(df, avg_stay, p):
    used = df[df["used"]].copy()
    used["reviews_l365"] = used["reviews_l365"].fillna(0)
    used["raw_nights"] = estimate_nights(used, avg_stay, p["review_rate"])
    used["nights"], cap = cap_nights(used["raw_nights"], p)
    used["rate"] = used["segment"].map(p["tourist_tax_per_night"])
    used["revenue"] = used["nights"] * used["price_clean"]
    used["tax_all"] = used["nights"] * used["rate"]
    used["tax_lic"] = used["tax_all"].where(used["has_license"], 0.0)
    short, long_ = used["segment"] == "short_stay", used["segment"] == "long_stay"
    used["rev_short"], used["rev_long"] = used["revenue"].where(short, 0.0), used["revenue"].where(long_, 0.0)
    used["tax_short"], used["tax_long"] = used["tax_all"].where(short, 0.0), used["tax_all"].where(long_, 0.0)
    used["out_n"] = used["flagged_price_outlier"].astype(int)
    used["out_rev"] = used["revenue"].where(used["flagged_price_outlier"], 0.0)

    areas = sorted(df["analysis_area"].dropna().unique()) + ["ALL"]
    big = pd.concat([used, used.assign(analysis_area="ALL")])
    excl = df[~df["used"]]
    excl = pd.concat([excl, excl.assign(analysis_area="ALL")])
    g = big.groupby("analysis_area").agg(
        n_used=("id", "size"), nights=("nights", "sum"), revenue=("revenue", "sum"),
        rev_short=("rev_short", "sum"), rev_long=("rev_long", "sum"), tax_all=("tax_all", "sum"),
        tax_lic=("tax_lic", "sum"), tax_short=("tax_short", "sum"), tax_long=("tax_long", "sum"),
        out_n=("out_n", "sum"), out_rev=("out_rev", "sum")).reindex(areas, fill_value=0)
    g["n_excluded"] = excl.groupby("analysis_area").size().reindex(areas, fill_value=0)
    n = g["n_used"].where(g["n_used"] > 0)
    g["occ"] = g["nights"] / (365 * n) * 100
    g.index.name = "analysis_area"
    return g.reset_index(), used, cap


def to_long(g, snap, kpi_id, currency="EUR"):
    frames = [pd.DataFrame({
        "kpi_id": kpi_id, "kpi_name": name, "snapshot": snap,
        "neighbourhood_cleansed": g["analysis_area"].values, "period": snap,
        "value": g[col].round(nd).values, "unit": unit, "currency": cur,
        "n_used": g["n_used"].values, "n_excluded": g["n_excluded"].values,
    }) for name, col, unit, cur, nd in get_measures(currency)]
    return pd.concat(frames, ignore_index=True)[COLUMNS]


# ---------- độ nhạy và kiểm tra ----------
def sensitivity(df, snap, p):
    rows = []
    for avg in p["sensitivity_average_stay"]:
        g, used, cap = aggregate(df, avg, p)
        r = g[g["analysis_area"] == "ALL"].iloc[0]
        rows.append({"snapshot": snap, "average_stay": avg, "n_used": int(r["n_used"]),
                     "raw_nights_total": round(used["raw_nights"].sum(), 1), "nights_total": round(r["nights"], 1),
                     "occupancy_pct": round(r["occ"], 1), "revenue": round(r["revenue"], 2),
                     "tax_all": round(r["tax_all"], 2), "cap_nights": round(cap, 1),
                     "listings_capped": int((used["raw_nights"] > cap).sum())})
    return pd.DataFrame(rows)


def checks(df, used, cap, snap, cfg):
    rows = []

    def add(name, value, note=""):
        rows.append({"snapshot": snap, "check": name, "value": value, "note": note})

    add("listings_in_snapshot", len(df))
    add("excluded_price_missing_or_nonpositive", int((~df["used"]).sum()), "bị loại khỏi KPI, ghi n_excluded")
    add("zero_reviews_l365", int((used["reviews_l365"] == 0).sum()), "ước lượng 0 đêm: có thể thấp hơn thực tế")
    add("reviews_ltm_missing", int(df["number_of_reviews_ltm"].isna().sum()), "được coi là 0 review")
    add("raw_nights_over_365", int((used["raw_nights"] > 365).sum()), "vô lý về vật lý trước khi cắt trần")
    add("cap_nights_value", round(cap, 1), "trần đang có hiệu lực (min của các trần)")
    add("listings_capped", int((used["raw_nights"] > cap).sum()))
    add("long_stay_listings_used", int((used["segment"] == "long_stay").sum()), "Stay Used = minimum_nights")
    add("price_outlier_kept", int(used["flagged_price_outlier"].sum()), "giữ nguyên trong KPI, xem hàng price_outlier_*")
    add("license_missing", int(df["license"].isna().sum()))
    add("license_exempt", int((df["license"].notna() & ~df["has_license"]).sum()), "cần xác nhận ý nghĩa của giá trị này")
    add("listings_without_area", int(df["analysis_area"].isna().sum()))
    cal_path = Path(cfg["calendar"]["interim_file"].format(snap=snap))
    if not cal_path.exists():
        alt = _find_table(Path(cfg["paths"]["interim"]), "calendar", snap)
        if alt is not None:
            cal_path = alt
    if cal_path.exists():
        cal = pd.read_csv(cal_path, usecols=["listing_id", "available"], dtype={"listing_id": "str"})
        unavail = cal[cal["available"] == "f"].groupby("listing_id").size()
        u = used["id"].map(unavail).fillna(0)
        add("calendar_unavailable_days_total", int(u.sum()), "gồm cả đêm đã đặt và đêm chủ nhà khóa lịch")
        add("estimated_nights_total", round(used["nights"].sum(), 1), "để so với dòng trên, không ép khớp")
        add("est_nights_gt_calendar_unavailable", int((used["nights"] > u).sum()),
            "mô hình nhiều hơn số ngày unavailable: cửa sổ khác nhau (quá khứ và tương lai)")
        mism = (365 - df["availability_365"]) != df["id"].map(unavail).fillna(0)
        add("calendar_vs_listing_availability_mismatch", int(mism.sum()), "đối chiếu availability_365 với calendar")
    else:
        add("calendar_check_skipped", 1, f"không thấy {cal_path}")
    return pd.DataFrame(rows)


# ---------- chạy ----------
def run(cfg, save=True):
    p = {**DEFAULTS, **cfg.get("k05_revenue_tax", {})}
    print("Tham so K5:", {k: v for k, v in p.items() if k not in ("id", "slug")})
    area_map = load_area_map(cfg)
    kpis, senss, chks = [], [], []
    currency = cfg.get("currency", "EUR")
    for snap in cfg["snapshots"]:
        snap = str(snap)
        df = prepare(snap, cfg, area_map, p)
        g, used, cap = aggregate(df, p["average_stay_nights"], p)
        kpis.append(to_long(g, snap, p["id"], currency=currency))
        senss.append(sensitivity(df, snap, p))
        chks.append(checks(df, used, cap, snap, cfg))
    kpi, sens, chk = (pd.concat(x, ignore_index=True) for x in (kpis, senss, chks))
    if save:
        out = Path(cfg["paths"]["processed"]) / f"kpi_{p['id'].lower()}_{p['slug']}.csv"
        Path("reports").mkdir(exist_ok=True)
        kpi.to_csv(out, index=False)
        sens.to_csv("reports/k05_sensitivity.csv", index=False)
        chk.to_csv("reports/k05_checks.csv", index=False)
        print("Da ghi:", out, "| reports/k05_sensitivity.csv | reports/k05_checks.csv")
    return kpi, sens, chk


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        kpi, sens, chk = run(yaml.safe_load(f))
    print("\n== ALL ==")
    print(kpi[kpi["neighbourhood_cleansed"] == "ALL"][["kpi_name", "snapshot", "value", "unit", "currency"]].to_string(index=False))
    print("\n== Do nhay Average Stay ==")
    print(sens.to_string(index=False))
    print("\n== Kiem tra ==")
    print(chk.to_string(index=False))