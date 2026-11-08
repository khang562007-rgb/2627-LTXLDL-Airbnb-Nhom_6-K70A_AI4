"""Tính KPI K3 (tỷ lệ nguyên căn) và K4 (biến động nguồn cung).

Liên kết với QA: cột `id`.
    QA (src/flag_property_cross.py) ghi data/processed/listings_property_flags_<mốc>.csv.gz gồm id + các cột cờ.
    KPI đọc file đó, ghép với listings theo `id`, rồi BỎ các dòng bị cờ nằm trong danh sách của KPI đó
    (configs/porto.yaml, mục kpi.skip_flags). QA chỉ cắm cờ, không xoá dòng; KPI mới là nơi quyết định bỏ.

    kpi:
      skip_flags:
        k3: [room_type_category]   # K3 dùng room_type nên bỏ dòng có room_type lạ/thiếu
        k4: []                     # K4 so sánh tập id nên KHÔNG bỏ dòng nào

K3 xuất hai giá trị: value_pct (toàn bộ dòng, "trước QA") và value_pct_ok (sau khi bỏ dòng bị cờ).
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


def _find_listings_file(interim_dir: Path, snapshot: str) -> Path:
    """Tìm tệp listings đã lọc, ưu tiên CSV nén nếu có cả hai định dạng."""
    for suffix in (".csv.gz", ".csv"):
        path = interim_dir / f"listings_{snapshot}{suffix}"
        if path.is_file():
            return path

    expected = interim_dir / f"listings_{snapshot}.csv[.gz]"
    raise FileNotFoundError(f"Không tìm thấy tệp listings cho mốc {snapshot}: {expected}")


def _read_listings(path: Path) -> pd.DataFrame:
    """Đọc đúng ba cột KPI cần dùng và báo rõ cột bị thiếu."""
    try:
        # Đọc riêng header để báo tên cột thiếu thay vì để lỗi usecols chung chung.
        header = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
    except Exception as exc:
        raise ValueError(f"Không đọc được header của tệp {path}: {exc}") from exc

    missing = [column for column in REQUIRED_COLUMNS if column not in header.columns]
    if missing:
        raise ValueError(
            f"Tệp {path} thiếu cột bắt buộc: {', '.join(missing)}"
        )

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
    """Giữ nguyên tên khu; chỉ thay giá trị thiếu bằng nhãn riêng."""
    return listings["analysis_area"].where(
        listings["analysis_area"].notna(), MISSING_AREA_LABEL
    )


def _percentage(numerator: int, denominator: int) -> float | None:
    """Tính phần trăm; mẫu số bằng 0 thì trả None."""
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


# ---------------------------------------------------------------------------
# Liên kết với QA qua cột id
# ---------------------------------------------------------------------------

def _flags_path(processed_dir: Path, snapshot: str) -> Path:
    """File cờ do QA ghi cho một mốc."""
    return processed_dir / f"listings_property_flags_{snapshot}.csv.gz"


def load_ok(
    frame: pd.DataFrame, snapshot: str, skip_cols: Sequence[str], processed_dir: Path
) -> tuple[pd.DataFrame, int]:
    """Bỏ các dòng bị QA cắm cờ trong skip_cols; ghép với file cờ theo `id`.

    Trả về (bảng đã bỏ dòng bị cờ, số dòng bị bỏ). Không có cờ nào cần bỏ thì trả nguyên bảng.
    Dừng với lỗi rõ ràng nếu thiếu file cờ, thiếu cột cờ, id trùng hoặc có id chưa được QA gắn cờ,
    để KPI không lặng lẽ tính như thể không có cờ.
    """
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

    merged = frame.merge(flags[["id"] + skip_cols], on="id", how="left", validate="one_to_one")
    if merged[skip_cols].isna().any().any():
        raise ValueError(
            f"Mốc {snapshot}: có id trong listings chưa có cờ từ QA. Hãy chạy lại QA cho đúng dữ liệu."
        )

    bad = merged[skip_cols].astype(bool).any(axis=1)   # True nếu dính bất kỳ cờ nào trong danh sách
    return merged.loc[~bad, list(frame.columns)].reset_index(drop=True), int(bad.sum())


# ---------------------------------------------------------------------------
# K3
# ---------------------------------------------------------------------------

def k3_entire_share(listings: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Tính tỷ lệ Entire home/apt theo khu và thêm dòng ALL cho mỗi mốc."""
    result_rows: list[dict[str, object]] = []

    for snapshot, frame in listings.items():
        areas = _area_labels(frame)
        if areas.eq(ALL_AREA_LABEL).any():
            raise ValueError(
                f"Mốc {snapshot} có analysis_area='{ALL_AREA_LABEL}', "
                "trùng nhãn tổng hợp ALL."
            )

        # Mẫu số dùng toàn bộ dòng của khu, kể cả room_type bị thiếu.
        work = pd.DataFrame(
            {"khu": areas, "room_type": frame["room_type"]}, index=frame.index
        )
        grouped = work.groupby("khu", dropna=False, sort=True).agg(
            n_total=("room_type", "size"),
            n_entire=(
                "room_type",
                lambda values: int(values.eq(ENTIRE_HOME_LABEL).sum()),
            ),
        )

        for area, counts in grouped.iterrows():
            total = int(counts["n_total"])
            entire = int(counts["n_entire"])
            result_rows.append(
                {
                    "snapshot": snapshot,
                    "khu": area,
                    "n_entire": entire,
                    "n_total": total,
                    "value_pct": _percentage(entire, total),
                }
            )

        total_all = len(frame)
        entire_all = int(frame["room_type"].eq(ENTIRE_HOME_LABEL).sum())
        result_rows.append(
            {
                "snapshot": snapshot,
                "khu": ALL_AREA_LABEL,
                "n_entire": entire_all,
                "n_total": total_all,
                "value_pct": _percentage(entire_all, total_all),
            }
        )

    return pd.DataFrame(result_rows, columns=K3_COLUMNS)


def combine_k3(k3_all: pd.DataFrame, k3_ok: pd.DataFrame) -> pd.DataFrame:
    """Ghép K3 "toàn bộ" với K3 "sau khi bỏ dòng bị cờ" theo (mốc, khu)."""
    ok = k3_ok.rename(
        columns={"n_entire": "n_entire_ok", "n_total": "n_total_ok", "value_pct": "value_pct_ok"}
    )
    out = k3_all.merge(ok, on=["snapshot", "khu"], how="left")
    count_cols = ["n_entire_ok", "n_total_ok"]
    out[count_cols] = out[count_cols].fillna(0).astype(int)   # khu bị bỏ hết dòng: số đếm = 0
    out["n_skipped"] = out["n_total"] - out["n_total_ok"]
    return out[
        ["snapshot", "khu", "n_entire", "n_total", "value_pct",
         "n_skipped", "n_total_ok", "n_entire_ok", "value_pct_ok"]
    ]


# ---------------------------------------------------------------------------
# K4
# ---------------------------------------------------------------------------

def k4_supply_change(
    listings: Mapping[str, pd.DataFrame], snaps: Sequence[str]
) -> pd.DataFrame:
    """So sánh ID ở các mốc liền kề; khu mới/lost lấy theo đúng mốc tương ứng."""
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

        # ID được đọc dạng chuỗi; set difference thể hiện listing mới và biến mất.
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
            result_rows.append(
                {
                    "snapshot": current_snapshot,
                    "khu": area,
                    "n_new": int(n_new),
                    "n_gone": int(n_gone),
                    "n_prev": n_prev,
                    "value_pct": _percentage(n_new - n_gone, n_prev),
                }
            )

        result_rows.append(
            {
                "snapshot": current_snapshot,
                "khu": ALL_AREA_LABEL,
                "n_new": len(new_ids),
                "n_gone": len(gone_ids),
                "n_prev": len(previous),
                "value_pct": _percentage(len(new_ids) - len(gone_ids), len(previous)),
            }
        )

    return pd.DataFrame(
        result_rows,
        columns=["snapshot", "khu", "n_new", "n_gone", "n_prev", "value_pct"],
    )


def _warn_room_type_variants(listings: Mapping[str, pd.DataFrame]) -> None:
    """Báo biến thể khoảng trắng/hoa thường, không tự chuẩn hóa nhãn."""
    canonical = {
        "entire home/apt": ENTIRE_HOME_LABEL,
        "private room": "Private room",
    }
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


def _validate_outputs(
    listings: Mapping[str, pd.DataFrame],
    k3: pd.DataFrame,
    k4: pd.DataFrame,
    snaps: Sequence[str],
) -> None:
    """Kiểm tra tổng dòng, tổng nguyên căn và phép tính trên dữ liệu đầu vào (bản chưa bỏ cờ)."""
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
                f"K3 mốc {snapshot}: tổng n_total theo khu không bằng "
                f"số dòng đầu vào ({len(source)})."
            )
        if int(all_row["n_total"]) != len(source):
            raise AssertionError(
                f"K3 mốc {snapshot}: n_total ALL={all_row['n_total']}, "
                f"nhưng tệp có {len(source)} dòng."
            )
        if int(area_rows["n_entire"].sum()) != int(all_row["n_entire"]):
            raise AssertionError(
                f"K3 mốc {snapshot}: tổng n_entire theo khu khác dòng ALL."
            )

        expected_entire = int(source["room_type"].eq(ENTIRE_HOME_LABEL).sum())
        if int(all_row["n_entire"]) != expected_entire:
            raise AssertionError(
                f"K3 mốc {snapshot}: n_entire ALL không khớp dữ liệu đầu vào."
            )

        # 87,5% là mốc đối chiếu đã được nhóm báo cáo cho mẫu 1.000 dòng (bản CHƯA bỏ cờ).
        # Nếu một snapshot thiếu dòng, tỷ lệ thực tế có thể khác; không ép số liệu.
        if len(source) == 1000 and all_row["value_pct"] != 87.5:
            raise AssertionError(
                f"K3 mốc {snapshot}: tỷ lệ ALL là {all_row['value_pct']}%, "
                "khác 87,5% dù có 1.000 dòng. Hãy kiểm tra room_type đầu vào."
            )

    for previous_snapshot, current_snapshot in zip(snaps, snaps[1:]):
        all_rows = k4[
            (k4["snapshot"] == current_snapshot) & (k4["khu"] == ALL_AREA_LABEL)
        ]
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


def _validate_skip(
    listings: Mapping[str, pd.DataFrame],
    listings_ok: Mapping[str, pd.DataFrame],
    skipped: Mapping[str, int],
    k3: pd.DataFrame,
    snaps: Sequence[str],
) -> None:
    """Kiểm tra phần "sau khi bỏ cờ": số dòng bỏ + số dòng giữ phải bằng số dòng ban đầu."""
    for snapshot in snaps:
        total = len(listings[snapshot])
        kept = len(listings_ok[snapshot])
        if kept + skipped[snapshot] != total:
            raise AssertionError(
                f"K3 mốc {snapshot}: giữ {kept} + bỏ {skipped[snapshot]} khác tổng {total}."
            )
        rows = k3[k3["snapshot"] == snapshot]
        all_row = rows[rows["khu"] == ALL_AREA_LABEL].iloc[0]
        area_rows = rows[rows["khu"] != ALL_AREA_LABEL]
        if int(all_row["n_total_ok"]) != kept or int(all_row["n_skipped"]) != skipped[snapshot]:
            raise AssertionError(f"K3 mốc {snapshot}: dòng ALL không khớp số dòng giữ/bỏ.")
        if int(area_rows["n_skipped"].sum()) != skipped[snapshot]:
            raise AssertionError(f"K3 mốc {snapshot}: tổng n_skipped theo khu khác số dòng bỏ.")


def main() -> None:
    """Đọc config, tính KPI, kiểm tra kết quả và ghi hai tệp CSV."""
    # Tránh lỗi in chú thích tiếng Việt trên một số terminal Windows dùng cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Tính KPI K3 và K4 cho Porto.")
    parser.add_argument("--config", default="configs/porto.yaml")
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
    if skip_config.get("k4"):
        print("CẢNH BÁO: K4 so sánh tập id nên không bỏ dòng nào; bỏ qua kpi.skip_flags.k4.")

    # Đọc từng mốc theo thứ tự trong config; không lọc hoặc sửa dòng đầu vào.
    listings: dict[str, pd.DataFrame] = {}
    for snapshot in snapshots:
        path = _find_listings_file(interim_dir, snapshot)
        frame = _read_listings(path)
        listings[snapshot] = frame

        print(f"Đã đọc {path}: {len(frame)} dòng, {len(frame.columns)} cột KPI.")
        if len(frame) != 1000:
            print(
                f"CẢNH BÁO mốc {snapshot}: có {len(frame)} dòng, khác mẫu "
                "1.000 dòng. KPI sẽ được tính từ toàn bộ dòng hiện có."
            )
        missing_areas = int(frame["analysis_area"].isna().sum())
        if missing_areas:
            print(
                f"CẢNH BÁO mốc {snapshot}: {missing_areas} dòng thiếu analysis_area, "
                f"được tính vào khu '{MISSING_AREA_LABEL}'."
            )

    _warn_room_type_variants(listings)

    # K3: tính hai lần, trước và sau khi bỏ dòng bị QA cắm cờ (ghép theo id).
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
    k4 = k4_supply_change(listings, snapshots)
    _validate_outputs(listings, k3_all, k4, snapshots)

    k3 = combine_k3(k3_all, k3_entire_share(listings_ok))
    _validate_skip(listings, listings_ok, skipped, k3, snapshots)

    # Báo tỷ lệ K3 thực tế của snapshot thiếu dòng để người dùng đối chiếu.
    for snapshot in snapshots:
        all_row = k3[(k3["snapshot"] == snapshot) & (k3["khu"] == ALL_AREA_LABEL)].iloc[0]
        if len(listings[snapshot]) != 1000 and all_row["value_pct"] != 87.5:
            print(
                f"CẢNH BÁO K3 mốc {snapshot}: ALL={all_row['value_pct']}% "
                f"({all_row['n_entire']}/{all_row['n_total']}), khác 87,5% "
                "vì snapshot không có đủ 1.000 dòng."
            )

    if len(snapshots) > 1:
        all_k4 = k4[k4["khu"] == ALL_AREA_LABEL]
        all_k4_zero = all(
            int(row.n_new) == 0 and int(row.n_gone) == 0
            for row in all_k4.itertuples(index=False)
        )
        if all_k4_zero:
            print(
                "CẢNH BÁO: K4 ALL bằng 0 ở mọi cặp mốc; "
                "đây là kết quả đúng theo các ID hiện có trong mẫu."
            )
        else:
            print(
                "Thông tin: tập ID thay đổi giữa các mốc; K4 giữ nguyên "
                "kết quả tính trực tiếp từ ID, không ép về 0."
            )

    processed_dir.mkdir(parents=True, exist_ok=True)
    k3_path = processed_dir / "kpi_k3_entire_home_share.csv"
    k4_path = processed_dir / "kpi_k4_supply_change.csv"
    k3.to_csv(k3_path, index=False, encoding="utf-8-sig")
    k4.to_csv(k4_path, index=False, encoding="utf-8-sig")
    print(f"Đã ghi K3: {k3_path}")
    print(f"Đã ghi K4: {k4_path}")


if __name__ == "__main__":
    main()