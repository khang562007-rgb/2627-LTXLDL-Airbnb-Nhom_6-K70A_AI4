"""KPI tỷ lệ listing vận hành kiểu thương mại/trung hạn, theo khu x mốc, xuất dạng long format.

Dùng trong code:   from kpi2 import run;  kq = run(cfg)
Chạy dòng lệnh:    python src/kpi2.py --config configs/porto.yaml

Đầu ra: data/processed/kpi_<id>_<slug>.csv với các cột
    kpi_id, kpi_name, snapshot, neighbourhood_cleansed, period, value, unit, currency, n_used, n_excluded
(neighbourhood_cleansed chứa mã khu analysis_area; toàn thành phố = "ALL")

Quy tắc đã chốt:
  - thương mại/trung hạn = availability_365 > availability_commercial HOẶC minimum_nights >= ngưỡng long-stay
  - mẫu số = mọi listing của khu, trừ listing có giá trị vô lý (availability ngoài 0..365, minimum_nights > 365)
  - nguồn availability = cột availability_365 của listings
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

COLUMNS = ["kpi_id", "kpi_name", "snapshot", "neighbourhood_cleansed", "period",
           "value", "unit", "currency", "n_used", "n_excluded"]


def load_area_map(cfg):
    """listing_id -> analysis_area, đọc từ sample.listing_ids_path (id_listing.csv)."""
    p = Path(cfg["sample"]["listing_ids_path"])
    if not p.exists():
        raise FileNotFoundError(f"Khong tim thay {p}")
    try:
        df = pd.read_csv(p, dtype=str)
    except pd.errors.EmptyDataError:
        raise ValueError(f"{p} rong (khong co dong nao), kiem tra lai file")
    missing = {"listing_id", "analysis_area"} - set(df.columns)
    if missing:
        raise ValueError(f"{p} thieu cot {sorted(missing)}; cac cot hien co: {list(df.columns)}")
    return df.drop_duplicates("listing_id").set_index("listing_id")["analysis_area"]


def kpi_by_area(lst, area_map, avail_cap):
    df = lst.copy()
    df["analysis_area"] = df["id"].map(area_map)
    df["excluded"] = df["flagged_availability_out_of_range"] | df["flagged_min_nights_outlier"]

    ok = df[~df["excluded"]].copy()
    ok["avail_gt"] = ok["availability_365"] > avail_cap
    ok["min_nights_ge"] = ok["flagged_long_stay_listing"]          # minimum_nights >= ngưỡng long-stay
    ok["commercial"] = ok["avail_gt"] | ok["min_nights_ge"]

    areas = sorted(df["analysis_area"].dropna().unique())
    g = ok.groupby("analysis_area").agg(
        n_listings=("id", "size"), n_commercial=("commercial", "sum"),
        n_avail_gt=("avail_gt", "sum"), n_min_nights_ge=("min_nights_ge", "sum")).reindex(areas, fill_value=0)
    g["n_excluded"] = df.groupby("analysis_area")["excluded"].sum().reindex(areas, fill_value=0)

    total = g.sum().to_frame("ALL").T                               # toàn thành phố (mẫu 1.000 listing)
    g = pd.concat([g, total]).astype(int)
    g.index.name = "analysis_area"
    n = g["n_listings"].where(g["n_listings"] > 0)
    p = g["n_commercial"] / n
    g["pct"] = (p * 100).round(1)
    g["margin_pp"] = (1.96 * (p * (1 - p) / n) ** 0.5 * 100).round(1)
    g["avail_pct"] = (g["n_avail_gt"] / n * 100).round(1)
    g["long_stay_pct"] = (g["n_min_nights_ge"] / n * 100).round(1)
    return g.reset_index()


def to_long(g, snap, kpi_id):
    measures = [
        ("commercial_share", g["pct"], "%"),
        ("commercial_share_margin95", g["margin_pp"], "pp"),
        ("commercial_listings", g["n_commercial"], "listings"),
        ("availability_share", g["avail_pct"], "%"),
        ("long_stay_share", g["long_stay_pct"], "%"),
    ]
    frames = [pd.DataFrame({
        "kpi_id": kpi_id, "kpi_name": name, "snapshot": snap,
        "neighbourhood_cleansed": g["analysis_area"].values, "period": snap,
        "value": value.values, "unit": unit, "currency": "",
        "n_used": g["n_listings"].values, "n_excluded": g["n_excluded"].values,
    }) for name, value, unit in measures]
    return pd.concat(frames, ignore_index=True)[COLUMNS]


def run(cfg, save=True):
    meta = cfg.get("kpi_commercial_share", {})
    kpi_id = meta.get("id", "K06")                    # đối chiếu mã KPI với bảng KPI của nhóm
    slug = meta.get("slug", "commercial_share")
    area_map = load_area_map(cfg)
    in_dir = Path(cfg["paths"]["processed"])
    parts = []
    for snap in cfg["snapshots"]:
        path = in_dir / f"flags_listings_{snap}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Thieu {path} (chay buoc gan co truoc)")
        lst = pd.read_csv(path, dtype={"id": "str"})
        if lst["id"].map(area_map).isna().any():
            print(f"[CANH BAO] {snap}: co listing khong co analysis_area")
        parts.append(to_long(kpi_by_area(lst, area_map, cfg["availability_commercial"]), str(snap), kpi_id))
    out = pd.concat(parts, ignore_index=True)
    if save:
        path = in_dir / f"kpi_{kpi_id.lower()}_{slug}.csv"
        out.to_csv(path, index=False)
        print("Da ghi:", path)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        kq = run(yaml.safe_load(f))
    print(kq[(kq["kpi_name"] == "commercial_share") & (kq["neighbourhood_cleansed"] == "ALL")].to_string(index=False))