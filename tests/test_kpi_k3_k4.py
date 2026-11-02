"""Kiểm thử KPI K3/K4 bằng vài dòng dữ liệu giả có thể tính tay."""

import pandas as pd
import pytest

from src.kpi_k3_k4 import k3_entire_share, k4_supply_change


def test_k3_keeps_missing_room_type_in_denominator_and_area_group():
    listings = {
        "s1": pd.DataFrame(
            {
                "id": ["1", "2", "3", "4"],
                "room_type": ["Entire home/apt", None, "Entire home/apt", "Private room"],
                "analysis_area": ["A", "A", "B", "B"],
            }
        )
    }

    result = k3_entire_share(listings)
    rows = result.set_index("khu")

    # Tính tay: ALL có 2 căn nguyên căn trên 4 dòng, tính cả room_type thiếu.
    assert rows.loc["ALL", "n_entire"] == 2
    assert rows.loc["ALL", "n_total"] == 4
    assert rows.loc["ALL", "value_pct"] == 50.0
    assert rows.loc["A", "n_total"] == 2
    assert rows.loc["A", "value_pct"] == 50.0


def test_k3_puts_missing_area_in_its_own_group():
    listings = {
        "s1": pd.DataFrame(
            {
                "id": ["1", "2"],
                "room_type": ["Entire home/apt", "Private room"],
                "analysis_area": [None, "A"],
            }
        )
    }

    result = k3_entire_share(listings).set_index("khu")

    assert result.loc["(thiếu)", "n_total"] == 1
    assert result.loc["(thiếu)", "n_entire"] == 1
    assert result.loc["(thiếu)", "value_pct"] == 100.0


def test_k4_counts_new_and_gone_and_zero_previous_area_denominator():
    listings = {
        "s1": pd.DataFrame(
            {
                "id": ["1", "2", "3", "4"],
                "room_type": ["Entire home/apt", None, "Entire home/apt", "Private room"],
                "analysis_area": ["A", "A", "B", "B"],
            }
        ),
        "s2": pd.DataFrame(
            {
                "id": ["1", "2", "3", "5"],
                "room_type": ["Entire home/apt", None, "Entire home/apt", "Entire home/apt"],
                "analysis_area": ["A", "A", "B", "C"],
            }
        ),
    }

    result = k4_supply_change(listings, ["s1", "s2"]).set_index("khu")

    # Tính tay: ID 5 mới, ID 4 mất; ALL là (1 - 1) / 4 = 0%.
    assert result.loc["ALL", "n_new"] == 1
    assert result.loc["ALL", "n_gone"] == 1
    assert result.loc["ALL", "n_prev"] == 4
    assert result.loc["ALL", "value_pct"] == 0.0
    # Khu B có 1 listing mất trên 2 listing trước đó: -50%.
    assert result.loc["B", "n_gone"] == 1
    assert result.loc["B", "value_pct"] == -50.0
    # Khu C chưa có listing ở mốc trước: mẫu số 0 nên để rỗng/NaN.
    assert result.loc["C", "n_new"] == 1
    assert result.loc["C", "n_prev"] == 0
    assert pd.isna(result.loc["C", "value_pct"])


def test_k4_rejects_duplicate_or_missing_ids():
    duplicate_ids = pd.DataFrame(
        {"id": ["1", "1"], "room_type": ["Entire home/apt"] * 2, "analysis_area": ["A"] * 2}
    )
    with pytest.raises(ValueError, match="id bị trùng"):
        k4_supply_change({"s1": duplicate_ids}, ["s1"])

    missing_id = pd.DataFrame(
        {"id": [None], "room_type": ["Entire home/apt"], "analysis_area": ["A"]}
    )
    with pytest.raises(ValueError, match="id có giá trị rỗng"):
        k4_supply_change({"s1": missing_id}, ["s1"])
