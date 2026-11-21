"""K1: tỷ trọng listing theo khu vực và snapshot.

Dùng trong code:   from kpi1 import kpi_k1, load_listings_by_snapshot
Chạy dòng lệnh:    python src/kpi1.py --config configs/porto.yaml
Chạy dạng package: python -m src.kpi1 --config configs/porto.yaml

Công thức:
    Tỷ trọng khu = số listing trong khu / tổng listing thành phố x 100%
    Độ thay đổi  = chênh lệch tỷ trọng giữa hai snapshot liên tiếp (điểm %)
    Chuỗi tăng   = số lần tỷ trọng tăng liên tiếp; ngưỡng lấy từ kpi.k1.min_rising_streak

Đầu ra:
    data/processed/kpi_k1_area_share.csv
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
    counts = (pd.DataFrame({s: d["area"].value_counts() for s, d in by_snap.items()})
              .fillna(0).astype(int))
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


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tính KPI K1 theo config.")
    parser.add_argument("--config", default="configs/porto.yaml")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    by_snap = load_listings_by_snapshot(config, project_root)
    k1_config = config.get("kpi", {}).get("k1", {})
    k1 = kpi_k1(
        by_snap,
        min_rising_streak=int(k1_config.get("min_rising_streak", 2)),
        overload_pct=k1_config.get("overload_pct"),
    )

    output_path = project_root / config["paths"]["processed"] / "kpi_k1_area_share.csv"
    save_kpi(k1, output_path)
    print(f"Đã ghi K1: {output_path} ({len(k1)} dòng)")


if __name__ == "__main__":
    main()
