"""K4: biến động nguồn cung ròng theo khu giữa các mốc liên tiếp.

Dùng trong code:   from kpi4 import k4_supply_change, standardize_k4
Chạy dòng lệnh:    python src/kpi4.py --config configs/porto.yaml

Phép tính cho mỗi cặp mốc trước -> hiện tại:
    Listing mới   = ID ở mốc hiện tại nhưng không có ở mốc trước
    Listing mất   = ID ở mốc trước nhưng không có ở mốc hiện tại
    Value         = (Listing mới - Listing mất) / tổng listing mốc trước x 100

Listing mới được phân theo khu ở mốc hiện tại; listing mất theo khu ở mốc trước.
KPI so sánh toàn bộ tập ID, không áp dụng kpi.skip_flags.k4. Mỗi cặp mốc có thêm dòng ALL.

Đầu ra:
    data/processed/kpi_k4_supply_change.csv
    Bao gồm số listing mới, mất, mẫu số mốc trước và cặp mốc được so sánh.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
import yaml

REQUIRED_COLUMNS = ["id", "analysis_area"]
MISSING_AREA_LABEL = "(thiếu)"
ALL_AREA_LABEL = "ALL"
STANDARD_KPI_COLUMNS = [
    "kpi_id", "kpi_name", "snapshot", "neighbourhood_cleansed", "value",
    "unit", "currency", "numerator", "denominator", "n_used", "n_excluded",
]


def _find_listings_file(interim_dir: Path, snapshot: str) -> Path:
    for suffix in (".csv.gz", ".csv"):
        path = interim_dir / f"listings_{snapshot}{suffix}"
        if path.is_file():
            return path
    expected = interim_dir / f"listings_{snapshot}.csv[.gz]"
    raise FileNotFoundError(f"Không tìm thấy tệp listings cho mốc {snapshot}: {expected}")


def _read_listings(path: Path) -> pd.DataFrame:
    try:
        header = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
    except Exception as exc:
        raise ValueError(f"Không đọc được header của tệp {path}: {exc}") from exc

    missing = [column for column in REQUIRED_COLUMNS if column not in header.columns]
    if missing:
        raise ValueError(f"Tệp {path} thiếu cột bắt buộc: {', '.join(missing)}")

    try:
        return pd.read_csv(
            path,
            encoding="utf-8-sig",
            usecols=REQUIRED_COLUMNS,
            dtype={"id": str},
        ).reindex(columns=REQUIRED_COLUMNS)
    except Exception as exc:
        raise ValueError(f"Không đọc được dữ liệu trong tệp {path}: {exc}") from exc


def _area_labels(listings: pd.DataFrame) -> pd.Series:
    return listings["analysis_area"].where(listings["analysis_area"].notna(), MISSING_AREA_LABEL)


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


def k4_supply_change(listings: Mapping[str, pd.DataFrame], snaps: Sequence[str]) -> pd.DataFrame:
    result_rows: list[dict[str, object]] = []

    for snapshot in snaps:
        if snapshot not in listings:
            raise KeyError(f"Không có dữ liệu listings cho mốc {snapshot}.")
        frame = listings[snapshot]
        if frame["id"].isna().any():
            raise ValueError(f"Cột id có giá trị rỗng ở mốc {snapshot}.")
        if frame["id"].duplicated().any():
            raise ValueError(f"Cột id bị trùng ở mốc {snapshot}.")

    for previous_snapshot, current_snapshot in zip(snaps, snaps[1:]):
        previous = listings[previous_snapshot]
        current = listings[current_snapshot]

        previous_ids = set(previous["id"])
        current_ids = set(current["id"])
        new_ids = current_ids - previous_ids
        gone_ids = previous_ids - current_ids

        previous_areas = _area_labels(previous)
        current_areas = _area_labels(current)
        previous_area_by_id = dict(zip(previous["id"], previous_areas))
        current_area_by_id = dict(zip(current["id"], current_areas))

        previous_counts = previous_areas.value_counts(dropna=False).to_dict()
        areas = set(previous_counts)
        areas.update(current_areas.tolist())

        for area in sorted(areas, key=str):
            n_prev = int(previous_counts.get(area, 0))
            n_new = sum(current_area_by_id[listing_id] == area for listing_id in new_ids)
            n_gone = sum(previous_area_by_id[listing_id] == area for listing_id in gone_ids)
            result_rows.append({
                "snapshot": current_snapshot,
                "comparison_period": f"{previous_snapshot}->{current_snapshot}",
                "khu": area,
                "n_new": int(n_new),
                "n_gone": int(n_gone),
                "n_prev": n_prev,
                "value_pct": _percentage(n_new - n_gone, n_prev),
            })

        result_rows.append({
            "snapshot": current_snapshot,
            "comparison_period": f"{previous_snapshot}->{current_snapshot}",
            "khu": ALL_AREA_LABEL,
            "n_new": len(new_ids),
            "n_gone": len(gone_ids),
            "n_prev": len(previous),
            "value_pct": _percentage(len(new_ids) - len(gone_ids), len(previous)),
        })

    return pd.DataFrame(
        result_rows,
        columns=["snapshot", "comparison_period", "khu", "n_new", "n_gone", "n_prev", "value_pct"],
    )


def standardize_k4(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "kpi_id": "K04",
        "kpi_name": "net_supply_change",
        "snapshot": frame["snapshot"].astype(str),
        "neighbourhood_cleansed": frame["khu"],
        "value": frame["value_pct"],
        "unit": "%",
        "currency": "",
        "numerator": frame["n_new"] - frame["n_gone"],
        "denominator": frame["n_prev"],
        "n_used": frame["n_prev"],
        "n_excluded": 0,
    })
    out["comparison_period"] = frame["comparison_period"]
    out["n_new"] = frame["n_new"]
    out["n_gone"] = frame["n_gone"]
    out["n_prev"] = frame["n_prev"]
    return out[STANDARD_KPI_COLUMNS + ["comparison_period", "n_new", "n_gone", "n_prev"]]


def _validate_outputs(listings: Mapping[str, pd.DataFrame], k4: pd.DataFrame, snaps: Sequence[str]) -> None:
    for previous_snapshot, current_snapshot in zip(snaps, snaps[1:]):
        all_rows = k4[(k4["snapshot"] == current_snapshot) & (k4["khu"] == ALL_AREA_LABEL)]
        if len(all_rows) != 1:
            raise AssertionError(f"K4 mốc {current_snapshot} phải có đúng một dòng ALL.")
        row = all_rows.iloc[0]
        previous_ids = set(listings[previous_snapshot]["id"])
        current_ids = set(listings[current_snapshot]["id"])
        if int(row["n_new"]) != len(current_ids - previous_ids):
            raise AssertionError(f"K4 mốc {current_snapshot}: n_new không khớp ID.")
        if int(row["n_gone"]) != len(previous_ids - current_ids):
            raise AssertionError(f"K4 mốc {current_snapshot}: n_gone không khớp ID.")
        if int(row["n_prev"]) != len(listings[previous_snapshot]):
            raise AssertionError(f"K4 mốc {current_snapshot}: n_prev không khớp mốc trước.")


def main(config_path: str = "configs/porto.yaml") -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Tính KPI K4 cho Porto.")
    parser.add_argument("--config", default=config_path)
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parent.parent / config_path
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    project_root = Path(__file__).resolve().parent.parent
    snapshots = config["snapshots"]
    interim_dir = project_root / config["paths"]["interim"]
    processed_dir = project_root / config["paths"]["processed"]

    listings: dict[str, pd.DataFrame] = {}
    for snapshot in snapshots:
        path = _find_listings_file(interim_dir, snapshot)
        frame = _read_listings(path)
        listings[snapshot] = frame
        print(f"Đã đọc {path}: {len(frame)} dòng, {len(frame.columns)} cột KPI.")

    k4 = k4_supply_change(listings, snapshots)
    _validate_outputs(listings, k4, snapshots)

    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / "kpi_k4_supply_change.csv"
    standardize_k4(k4).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Đã ghi K4: {out_path}")


if __name__ == "__main__":
    main()
