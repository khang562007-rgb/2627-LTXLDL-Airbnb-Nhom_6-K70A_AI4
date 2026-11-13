"""KPI K1 và K2 theo khu vực và snapshot.

Quy tắc KPI K1 — Tỷ trọng listing theo khu vực
    Mục tiêu: theo dõi phân bố nguồn cung listing giữa các khu vực qua thời gian.
    Công thức: số listing trong khu / tổng listing của thành phố x 100%.
    Cờ xu hướng tăng bật khi tỷ trọng tăng liên tiếp ít nhất min_rising_streak lần.

Quy tắc KPI K2 — Tỷ lệ listing thuộc host nhiều listing
    Mục tiêu: theo dõi tỷ trọng nguồn cung thuộc các host có nhiều listing.
    Công thức: số listing thuộc host đạt ngưỡng / tổng listing trong khu x 100%.
    Scope city đếm listing của host trên toàn thành phố; scope area đếm trong từng khu.

Chạy từ thư mục gốc:
    python -m src.kpi --config configs/porto.yaml

Đầu ra:
    data/processed/kpi_k1_area_share.csv
    data/processed/kpi_k2_multi_host_share.csv
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

STANDARD_COLUMNS = [
    "kpi_id", "kpi_name", "snapshot", "neighbourhood_cleansed", "value",
    "unit", "currency", "numerator", "denominator", "n_used", "n_excluded",
]


def load_listings_by_snapshot(config, project_root):
    """Đọc các cột cần cho K1/K2 từ listings đã lọc ở data/interim."""
    by_snap = {}
    interim = project_root / config["paths"]["interim"]
    required = {"id", "host_id", "analysis_area"}
    for snapshot in config["snapshots"]:
        snapshot = str(snapshot)
        path = next(
            (interim / f"listings_{snapshot}{suffix}"
             for suffix in (".csv.gz", ".csv")
             if (interim / f"listings_{snapshot}{suffix}").is_file()),
            None,
        )
        if path is None:
            raise FileNotFoundError(
                f"Thiếu listings_{snapshot}.csv(.gz) trong {interim}; hãy chạy bước lọc trước."
            )
        header = pd.read_csv(path, nrows=0).columns
        missing = sorted(required - set(header))
        if missing:
            raise ValueError(f"{path} thiếu cột bắt buộc: {missing}")
        frame = pd.read_csv(path, usecols=sorted(required), dtype={"id": str, "host_id": str})
        by_snap[snapshot] = frame.rename(columns={"analysis_area": "area"})
    return by_snap


def save_kpi(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def rise_streak(wide, tol=0.0):
    up = wide.diff(axis=1).gt(tol)
    streak = up.astype(int)
    cols = list(wide.columns)
    for prev, cur in zip(cols, cols[1:]):
        streak[cur] = (streak[prev] + 1).where(up[cur], 0)
    return streak


def to_long(frames):
    out = None
    for name, wide in frames.items():
        m = (wide.rename_axis(index="area", columns="snapshot")
                 .reset_index().melt(id_vars="area", var_name="snapshot", value_name=name))
        out = m if out is None else out.merge(m, on=["area", "snapshot"])
    return out.sort_values(["area", "snapshot"]).reset_index(drop=True)


def kpi_k1(by_snap, min_rising_streak, overload_pct=None):
    counts = (pd.DataFrame({s: d["area"].value_counts() for s, d in by_snap.items()}).fillna(0).astype(int))
    share = counts / counts.sum() * 100
    delta = share.diff(axis=1)
    streak = rise_streak(share)
    city = pd.DataFrame(counts.sum().to_dict(), index=counts.index)
    out = to_long({"n_listings_area": counts, "n_listings_city": city,
                   "share_pct": share, "share_delta_pp": delta, "rising_streak": streak})
    out["flag_rising_share"] = out["rising_streak"] >= min_rising_streak
    if overload_pct is not None:
        out["flag_overload"] = out["share_pct"] > overload_pct
    out["share_pct"] = out["share_pct"].round(4)
    out["share_delta_pp"] = out["share_delta_pp"].round(4)

    result = out.rename(columns={"area": "neighbourhood_cleansed"}).copy()
    result["kpi_id"] = "K01"
    result["kpi_name"] = "area_listing_share"
    result["value"] = result["share_pct"]
    result["unit"] = "%"
    result["currency"] = ""
    result["numerator"] = result["n_listings_area"]
    result["denominator"] = result["n_listings_city"]
    result["n_used"] = result["n_listings_area"]
    result["n_excluded"] = 0
    return result[STANDARD_COLUMNS + [
        "n_listings_area", "n_listings_city", "share_delta_pp",
        "rising_streak", "flag_rising_share",
    ] + (["flag_overload"] if overload_pct is not None else [])]


def kpi_k2(by_snap, min_listings, scope, tolerance_pp):
    if scope not in {"city", "area"}:
        raise ValueError("scope của K2 phải là 'city' hoặc 'area'.")
    key = ["host_id"] if scope == "city" else ["area", "host_id"]
    n_all, n_multi = {}, {}
    for snap, d in by_snap.items():
        listings_of_host = d.groupby(key)["id"].transform("size")
        d = d.assign(multi=listings_of_host >= min_listings)
        g = d.groupby("area").agg(n_listings=("id", "size"), n_multi=("multi", "sum"))
        n_all[snap], n_multi[snap] = g["n_listings"], g["n_multi"]
    n_all = pd.DataFrame(n_all).fillna(0).astype(int)
    n_multi = pd.DataFrame(n_multi).reindex(n_all.index).fillna(0).astype(int)

    share = n_multi / n_all.where(n_all > 0) * 100
    delta = share.diff(axis=1)
    streak = rise_streak(share, tolerance_pp)
    out = to_long({"n_listings": n_all, "n_multi_host_listings": n_multi,
                   "multi_host_share_pct": share, "share_delta_pp": delta, "rising_streak": streak})
    out["flag_rising"] = out["share_delta_pp"] > tolerance_pp
    out["multi_host_share_pct"] = out["multi_host_share_pct"].round(4)
    out["share_delta_pp"] = out["share_delta_pp"].round(4)
    result = out.rename(columns={"area": "neighbourhood_cleansed"}).copy()
    result["kpi_id"] = "K02"
    result["kpi_name"] = "multi_host_listing_share"
    result["value"] = result["multi_host_share_pct"].round(4)
    result["unit"] = "%"
    result["currency"] = ""
    result["numerator"] = result["n_multi_host_listings"]
    result["denominator"] = result["n_listings"]
    result["n_used"] = result["n_listings"]
    result["n_excluded"] = 0
    return result[STANDARD_COLUMNS + [
        "n_listings", "n_multi_host_listings", "share_delta_pp",
        "rising_streak", "flag_rising",
    ]]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tính KPI K1 và K2 theo config.")
    parser.add_argument("--config", default="configs/porto.yaml")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    by_snap = load_listings_by_snapshot(config, project_root)
    kpi_config = config.get("kpi", {})
    k1_config = kpi_config.get("k1", {})
    k2_config = kpi_config.get("k2", {})

    k1 = kpi_k1(
        by_snap,
        min_rising_streak=int(k1_config.get("min_rising_streak", 2)),
        overload_pct=k1_config.get("overload_pct"),
    )
    k2 = kpi_k2(
        by_snap,
        min_listings=int(k2_config.get("min_listings_per_host", 2)),
        scope=k2_config.get("scope", "city"),
        tolerance_pp=float(k2_config.get("tolerance_pp", 0.0)),
    )

    processed = project_root / config["paths"]["processed"]
    k1_path = processed / "kpi_k1_area_share.csv"
    k2_path = processed / "kpi_k2_multi_host_share.csv"
    save_kpi(k1, k1_path)
    save_kpi(k2, k2_path)
    print(f"Đã ghi K1: {k1_path} ({len(k1)} dòng)")
    print(f"Đã ghi K2: {k2_path} ({len(k2)} dòng)")


if __name__ == "__main__":
    main()
