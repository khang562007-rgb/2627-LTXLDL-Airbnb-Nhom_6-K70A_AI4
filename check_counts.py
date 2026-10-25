"""Check expected row counts and IDs in interim and processed outputs."""
from pathlib import Path
import sys

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parent
with (ROOT / "configs" / "porto.yaml").open(encoding="utf-8") as config_file:
    CONFIG = yaml.safe_load(config_file)

SNAPSHOTS = CONFIG["snapshots"]
INTERIM_DIR = ROOT / CONFIG["paths"]["interim"]
PROCESSED_DIR = ROOT / CONFIG["paths"]["processed"]
EXPECTED_LISTINGS = 1000
EXPECTED_CALENDAR_ROWS = 365_000
EXPECTED_REVIEW_ROWS = 5_000
EXPECTED_ROOM_TYPES = {"Entire home/apt": 875, "Private room": 125}
EXPECTED_NO_REVIEW_COUNTS = dict(zip(SNAPSHOTS, [50, 30, 25, 25]))
failures = 0


def check(condition, message):
    global failures
    if condition:
        print(f"[PASS] {message}")
    else:
        failures += 1
        print(f"[FAIL] {message}")


def csv_path(folder, stem):
    """Resolve either compressed or plain CSV output."""
    for suffix in (".csv.gz", ".csv"):
        path = folder / f"{stem}{suffix}"
        if path.is_file():
            return path
    return None


def load_csv(folder, stem, label, **kwargs):
    path = csv_path(folder, stem)
    check(path is not None, f"Tìm thấy {label}")
    if path is None:
        return None
    try:
        return pd.read_csv(path, **kwargs)
    except Exception as exc:
        check(False, f"Đọc được {label}: {exc}")
        return None


def check_id_sets(id_sets, label):
    if len(id_sets) < 2:
        return
    reference = next(iter(id_sets.values()))
    check(all(ids == reference for ids in list(id_sets.values())[1:]),
          f"Các mốc có cùng ID {label}")


def main():
    listing_ids = {}
    review_ids = {}

    print("--- INTERIM: LISTINGS ---")
    for snap in SNAPSHOTS:
        df = load_csv(INTERIM_DIR, f"listings_{snap}", f"listings_{snap}",
                      dtype={"id": str}, low_memory=False)
        if df is None:
            continue

        check(len(df) == EXPECTED_LISTINGS,
              f"listings_{snap}: {len(df)} dòng (kỳ vọng {EXPECTED_LISTINGS})")
        if "id" in df.columns:
            listing_ids[snap] = set(df["id"].dropna())
            check(not df["id"].duplicated().any(), f"listings_{snap}: ID không trùng")
        else:
            check(False, f"listings_{snap}: thiếu cột id")

        if "room_type" in df.columns:
            actual = df["room_type"].value_counts().to_dict()
            check(actual == EXPECTED_ROOM_TYPES,
                  f"listings_{snap}: phân bố room_type là {actual}")
        else:
            check(False, f"listings_{snap}: thiếu cột room_type")

        if "number_of_reviews" in df.columns:
            actual = pd.to_numeric(df["number_of_reviews"], errors="coerce").eq(0).sum()
            expected = EXPECTED_NO_REVIEW_COUNTS[snap]
            check(actual == expected,
                  f"listings_{snap}: {actual} listing không review (kỳ vọng {expected})")
        else:
            check(False, f"listings_{snap}: thiếu cột number_of_reviews")

        if "analysis_area" in df.columns:
            counts = df["analysis_area"].value_counts()
            valid = not counts.empty and counts.between(120, 130).all()
            check(valid, f"listings_{snap}: mỗi analysis_area có 120–130 listing")
        else:
            check(False, f"listings_{snap}: thiếu cột analysis_area")

        if snap == SNAPSHOTS[-1] and "price" in df.columns:
            check(df["price"].isna().sum() == 20,
                  f"listings_{snap}: có đúng 20 giá trị price thiếu")
        elif snap == SNAPSHOTS[-1]:
            check(False, f"listings_{snap}: thiếu cột price")

    check_id_sets(listing_ids, "listings")

    print("\n--- INTERIM: CALENDAR ---")
    for snap in SNAPSHOTS:
        df = load_csv(INTERIM_DIR, f"calendar_{snap}", f"calendar_{snap}",
                      usecols=["listing_id"], dtype={"listing_id": str})
        if df is None:
            continue
        check(len(df) == EXPECTED_CALENDAR_ROWS,
              f"calendar_{snap}: {len(df)} dòng (kỳ vọng {EXPECTED_CALENDAR_ROWS})")
        if "listing_id" in df.columns:
            check(df["listing_id"].nunique() == EXPECTED_LISTINGS,
                  f"calendar_{snap}: có {df['listing_id'].nunique()} listing")
            if snap in listing_ids:
                check(set(df["listing_id"].dropna()) == listing_ids[snap],
                      f"calendar_{snap}: ID khớp listings")

    print("\n--- INTERIM: REVIEWS ---")
    for snap in SNAPSHOTS:
        df = load_csv(INTERIM_DIR, f"reviews_{snap}", f"reviews_{snap}",
                      usecols=["id"], dtype={"id": str})
        if df is None:
            continue
        check(len(df) == EXPECTED_REVIEW_ROWS,
              f"reviews_{snap}: {len(df)} dòng (kỳ vọng {EXPECTED_REVIEW_ROWS})")
        if "id" in df.columns:
            review_ids[snap] = set(df["id"].dropna())
    check_id_sets(review_ids, "reviews")

    print("\n--- PROCESSED ---")
    for snap in SNAPSHOTS:
        for stem in (f"listings_property_flags_{snap}", f"listings_review_flags_{snap}"):
            df = load_csv(PROCESSED_DIR, stem, stem, dtype={"id": str})
            if df is not None:
                check(len(df) == EXPECTED_LISTINGS and "id" in df.columns,
                      f"{stem}: có {EXPECTED_LISTINGS} dòng và cột id")

        stem = f"reviews_flagged_{snap}"
        df = load_csv(PROCESSED_DIR, stem, stem, usecols=["id"], dtype={"id": str})
        if df is not None:
            check(len(df) == EXPECTED_REVIEW_ROWS,
                  f"{stem}: {len(df)} dòng (kỳ vọng {EXPECTED_REVIEW_ROWS})")

    if failures:
        print(f"\nCó {failures} kiểm tra chưa đạt.")
        sys.exit(1)
    print("\nTất cả kiểm tra đều đạt.")


if __name__ == "__main__":
    main()
