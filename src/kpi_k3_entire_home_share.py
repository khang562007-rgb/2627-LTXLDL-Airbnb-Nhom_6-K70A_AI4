"""K3: tỷ lệ listing nguyên căn (Entire home/apt), theo khu x mốc.

Dùng trong code:   from kpi3 import k3_entire_share, standardize_k3
Chạy dòng lệnh:    python src/kpi3.py --config configs/porto.yaml

Phép tính:
    Numerator   = số listing có room_type == "Entire home/apt"
    Denominator = tổng số listing trong khu (kể cả room_type thiếu)
    Value       = Numerator / Denominator x 100

Kết quả được tính trước và sau khi loại các cờ trong kpi.skip_flags.k3.
Khu thiếu analysis_area được gán nhãn "(thiếu)"; mỗi mốc có thêm dòng tổng hợp ALL.

Đầu ra:
    data/processed/kpi_k3_entire_home_share.csv
    Bao gồm giá trị trước/sau QA, số listing dùng và số listing bị loại.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
import yaml

REQUIRED_COLUMNS = ["id", "room_type", "analysis_area"]
ENTIRE_HOME_LABEL = "Entire home/apt"
MISSING_AREA_LABEL = "(thiếu)"
ALL_AREA_LABEL = "ALL"
K3_COLUMNS = ["snapshot", "khu", "n_entire", "n_total", "value_pct"]
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


def _flags_path(processed_dir: Path, snapshot: str) -> Path:
    return processed_dir / f"listings_property_flags_{snapshot}.csv.gz"


def load_ok(frame: pd.DataFrame, snapshot: str, skip_cols: Sequence[str], processed_dir: Path) -> tuple[pd.DataFrame, int]:
    if not skip_cols:
        return frame, 0

    path = _flags_path(processed_dir, snapshot)
    if not path.is_file():
        raise FileNotFoundError(
            f"Thiếu file cờ QA {path}. Hãy chạy src/flag_property_cross.py trước khi tính KPI."
        )
    flags = pd.read_csv(path, encoding="utf-8-sig", dtype={"id": str})

    missing = [column for column in skip_cols if column not in flags.columns]
    if missing:
        raise ValueError(f"File cờ {path} thiếu cột: {', '.join(missing)}")
    if frame["id"].duplicated().any() or flags["id"].duplicated().any():
        raise ValueError(f"Mốc {snapshot}: id bị trùng ở listings hoặc ở file cờ, không ghép được.")

    merged = frame.merge(flags[["id"] + list(skip_cols)], on="id", how="left", validate="one_to_one")
    if merged[list(skip_cols)].isna().any().any():
        raise ValueError(
            f"Mốc {snapshot}: có id trong listings chưa có cờ từ QA. Hãy chạy lại QA cho đúng dữ liệu."
        )

    bad = merged[list(skip_cols)].astype(bool).any(axis=1)
    return merged.loc[~bad, list(frame.columns)].reset_index(drop=True), int(bad.sum())


def k3_entire_share(listings: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    result_rows: list[dict[str, object]] = []

    for snapshot, frame in listings.items():
        areas = _area_labels(frame)
        if areas.eq(ALL_AREA_LABEL).any():
            raise ValueError(
                f"Mốc {snapshot} có analysis_area='{ALL_AREA_LABEL}', "
                "trùng nhãn tổng hợp ALL."
            )

        work = pd.DataFrame({"khu": areas, "room_type": frame["room_type"]}, index=frame.index)
        grouped = work.groupby("khu", dropna=False, sort=True).agg(
            n_total=("room_type", "size"),
            n_entire=("room_type", lambda values: int(values.eq(ENTIRE_HOME_LABEL).sum())),
        )

        for area, counts in grouped.iterrows():
            total = int(counts["n_total"])
            entire = int(counts["n_entire"])
            result_rows.append({
                "snapshot": snapshot,
                "khu": area,
                "n_entire": entire,
                "n_total": total,
                "value_pct": _percentage(entire, total),
            })

        total_all = len(frame)
        entire_all = int(frame["room_type"].eq(ENTIRE_HOME_LABEL).sum())
        result_rows.append({
            "snapshot": snapshot,
            "khu": ALL_AREA_LABEL,
            "n_entire": entire_all,
            "n_total": total_all,
            "value_pct": _percentage(entire_all, total_all),
        })

    return pd.DataFrame(result_rows, columns=K3_COLUMNS)


def combine_k3(k3_all: pd.DataFrame, k3_ok: pd.DataFrame) -> pd.DataFrame:
    ok = k3_ok.rename(columns={"n_entire": "n_entire_ok", "n_total": "n_total_ok", "value_pct": "value_pct_ok"})
    out = k3_all.merge(ok, on=["snapshot", "khu"], how="left")
    out[["n_entire_ok", "n_total_ok"]] = out[["n_entire_ok", "n_total_ok"]].fillna(0).astype(int)
    out["n_skipped"] = out["n_total"] - out["n_total_ok"]
    return out[
        ["snapshot", "khu", "n_entire", "n_total", "value_pct",
         "n_skipped", "n_total_ok", "n_entire_ok", "value_pct_ok"]
    ]


def _warn_room_type_variants(listings: Mapping[str, pd.DataFrame]) -> None:
    canonical = {"entire home/apt": ENTIRE_HOME_LABEL, "private room": "Private room"}
    for snapshot, frame in listings.items():
        variants = []
        for value in frame["room_type"].dropna().unique():
            normalized = str(value).strip().casefold()
            if normalized in canonical and value != canonical[normalized]:
                variants.append(repr(value))
        if variants:
            print(
                f"CẢNH BÁO room_type ở mốc {snapshot} có biến thể nhãn "
                f"{', '.join(variants)}; KPI vẫn chỉ khớp chuỗi chính xác."
            )


def _validate_outputs(listings: Mapping[str, pd.DataFrame], k3: pd.DataFrame, snaps: Sequence[str]) -> None:
    for snapshot in snaps:
        source = listings[snapshot]
        rows = k3[k3["snapshot"] == snapshot]
        area_rows = rows[rows["khu"] != ALL_AREA_LABEL]
        all_rows = rows[rows["khu"] == ALL_AREA_LABEL]
        if len(all_rows) != 1:
            raise AssertionError(f"K3 mốc {snapshot} phải có đúng một dòng ALL.")

        all_row = all_rows.iloc[0]
        if int(area_rows["n_total"].sum()) != len(source):
            raise AssertionError(
                f"K3 mốc {snapshot}: tổng n_total theo khu không bằng số dòng đầu vào ({len(source)})."
            )
        if int(all_row["n_total"]) != len(source):
            raise AssertionError(
                f"K3 mốc {snapshot}: n_total ALL={all_row['n_total']}, nhưng tệp có {len(source)} dòng."
            )
        if int(area_rows["n_entire"].sum()) != int(all_row["n_entire"]):
            raise AssertionError(f"K3 mốc {snapshot}: tổng n_entire theo khu khác dòng ALL.")

        expected_entire = int(source["room_type"].eq(ENTIRE_HOME_LABEL).sum())
        if int(all_row["n_entire"]) != expected_entire:
            raise AssertionError(f"K3 mốc {snapshot}: n_entire ALL không khớp dữ liệu đầu vào.")


def _validate_skip(listings: Mapping[str, pd.DataFrame], listings_ok: Mapping[str, pd.DataFrame], skipped: Mapping[str, int], k3: pd.DataFrame, snaps: Sequence[str]) -> None:
    for snapshot in snaps:
        total = len(listings[snapshot])
        kept = len(listings_ok[snapshot])
        if kept + skipped[snapshot] != total:
            raise AssertionError(f"K3 mốc {snapshot}: giữ {kept} + bỏ {skipped[snapshot]} khác tổng {total}.")
        rows = k3[k3["snapshot"] == snapshot]
        all_row = rows[rows["khu"] == ALL_AREA_LABEL].iloc[0]
        area_rows = rows[rows["khu"] != ALL_AREA_LABEL]
        if int(all_row["n_total_ok"]) != kept or int(all_row["n_skipped"]) != skipped[snapshot]:
            raise AssertionError(f"K3 mốc {snapshot}: dòng ALL không khớp số dòng giữ/bỏ.")
        if int(area_rows["n_skipped"].sum()) != skipped[snapshot]:
            raise AssertionError(f"K3 mốc {snapshot}: tổng n_skipped theo khu khác số dòng bỏ.")


def standardize_k3(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "kpi_id": "K03",
        "kpi_name": "entire_home_share",
        "snapshot": frame["snapshot"].astype(str),
        "neighbourhood_cleansed": frame["khu"],
        "value": frame["value_pct_ok"],
        "unit": "%",
        "currency": "",
        "numerator": frame["n_entire_ok"],
        "denominator": frame["n_total_ok"],
        "n_used": frame["n_total_ok"],
        "n_excluded": frame["n_skipped"],
    })
    out["value_before_qa"] = frame["value_pct"]
    out["n_entire_before_qa"] = frame["n_entire"]
    out["n_total_before_qa"] = frame["n_total"]
    out["n_entire_after_qa"] = frame["n_entire_ok"]
    out["n_total_after_qa"] = frame["n_total_ok"]
    return out[STANDARD_KPI_COLUMNS + [
        "value_before_qa", "n_entire_before_qa", "n_total_before_qa",
        "n_entire_after_qa", "n_total_after_qa",
    ]] 


def main(config_path: str = "configs/porto.yaml") -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Tính KPI K3 cho Porto.")
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
    skip_config = (config.get("kpi") or {}).get("skip_flags") or {}
    k3_skip_cols = list(skip_config.get("k3", []))

    listings: dict[str, pd.DataFrame] = {}
    for snapshot in snapshots:
        path = _find_listings_file(interim_dir, snapshot)
        frame = _read_listings(path)
        listings[snapshot] = frame
        print(f"Đã đọc {path}: {len(frame)} dòng, {len(frame.columns)} cột KPI.")
        if len(frame) != 1000:
            print(f"CẢNH BÁO mốc {snapshot}: có {len(frame)} dòng, khác mẫu 1.000 dòng.")
        missing_areas = int(frame["analysis_area"].isna().sum())
        if missing_areas:
            print(
                f"CẢNH BÁO mốc {snapshot}: {missing_areas} dòng thiếu analysis_area, "
                f"được tính vào khu '{MISSING_AREA_LABEL}'."
            )

    _warn_room_type_variants(listings)

    listings_ok: dict[str, pd.DataFrame] = {}
    skipped: dict[str, int] = {}
    for snapshot in snapshots:
        listings_ok[snapshot], skipped[snapshot] = load_ok(
            listings[snapshot], snapshot, k3_skip_cols, processed_dir
        )
        if k3_skip_cols:
            print(
                f"K3 mốc {snapshot}: bỏ {skipped[snapshot]} dòng bị cờ {k3_skip_cols}, "
                f"giữ {len(listings_ok[snapshot])} dòng."
            )

    k3_all = k3_entire_share(listings)
    _validate_outputs(listings, k3_all, snapshots)
    k3 = combine_k3(k3_all, k3_entire_share(listings_ok))
    _validate_skip(listings, listings_ok, skipped, k3, snapshots)

    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / "kpi_k3_entire_home_share.csv"
    standardize_k3(k3).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Đã ghi K3: {out_path}")


if __name__ == "__main__":
    main()
