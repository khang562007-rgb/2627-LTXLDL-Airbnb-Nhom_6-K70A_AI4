from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
with (ROOT / "configs" / "porto.yaml").open(encoding="utf-8") as config_file:
    cfg = yaml.safe_load(config_file)

DATA_DIR = ROOT / cfg["paths"]["interim"]
REVIEWS = [50, 30, 25, 25]

# Listings
listing_files = sorted(DATA_DIR.glob("listings_*.csv*"))
if not listing_files:
    print("\n[FAIL] Không tìm thấy file listings_*.csv*")
else:
    print(f"\n--- KIỂM TRA LISTINGS ---")
    listing_id = []

    for idx, filepath in enumerate(listing_files):
        df = pd.read_csv(filepath)

        if len(df) != 1000:
            print(f"[FAIL] {filepath.name} không đủ 1000 dòng")
        else:
            print(f"[PASS] {filepath.name} đủ 1000 dòng")

        if "id" in df.columns:
            listing_id.append(set(df["id"]))
        elif "listing_id" in df.columns:
            listing_id.append(set(df["listing_id"]))

        if "room_type" in df.columns:
            if df["room_type"].value_counts().to_dict() == {"Entire home/apt": 875, "Private room": 125}:
                print("[PASS] Đủ 875 Entire home/apt, 125 Private room")
            else:
                print("[FAIL] Không đủ 875 Entire home/apt, 125 Private room")

        if "number_of_reviews" in df.columns:
            if (df["number_of_reviews"] == 0).sum() == REVIEWS[idx]:
                print("[PASS] Đủ số id không có review")
            else:
                print("[FAIL] Không đủ số id không có review")

        if idx == len(listing_files) - 1:
            if "price" in df.columns:
                if df["price"].isna().sum() == 20:
                    print("[PASS] Mốc cuối đủ 20 listing thiếu price")
                else:
                    print("[FAIL] Mốc cuối không đủ 20 listing thiếu price")

        if "analysis_area" in df.columns:
            area_counts = df["analysis_area"].value_counts()
            if area_counts[(area_counts < 120) | (area_counts > 130)].empty:
                print("[PASS] analysis_area đủ từ 120-130 listing")
            else:
                print("[FAIL] analysis_area không đủ từ 120-130 listing")

    if len(listing_id) > 1:
        first_set = listing_id[0]
        all_same = all(s == first_set for s in listing_id[1:])
        if all_same:
            print("[PASS] Các mốc có cùng id")
        else:
            print("[FAIL] Các mốc không có cùng id")

# Calender
cal_files = sorted(DATA_DIR.glob("calendar_*.csv*"))
if not cal_files:
    print("\n[FAIL] Không tìm thấy file calendar_*.csv*")
else:
    print("\n--- KIỂM TRA CALENDAR ---")
    calender_id = []
    for filepath in cal_files:
        df = pd.read_csv(filepath)
        if len(df) == 365000:
            print(f"[PASS] {filepath.name} đủ 365000 dòng")
        else:
            print(f"[FAIL] {filepath.name}: không đủ 365000 dòng")

        if "id" in df.columns:
            calender_id.append(set(df["id"]))
        elif "review_id" in df.columns:
            calender_id.append(set(df["review_id"]))

    if len(calender_id) > 1:
            if all(s == calender_id[0] for s in calender_id[1:]):
                print("[PASS] Các mốc có cùng id")
            else:
                print("[FAIL] Các mốc không có cùng id")

# Review
review_files = sorted(DATA_DIR.glob("reviews_*.csv*"))
if not review_files:
    print("\n[FAIL] Không tìm thấy file reviews_*.csv*")
else:
    print("\n--- KIỂM TRA REVIEWS ---")
    review_id = []
    for filepath in review_files:
        df = pd.read_csv(filepath)
        if len(df) == 5000:
            print(f"[PASS] {filepath.name} đủ 5000 dòng")
        else:
            print(f"[FAIL] {filepath.name} không đủ 5000 dòng")

        if "id" in df.columns:
            review_id.append(set(df["id"]))
        elif "review_id" in df.columns:
            review_id.append(set(df["review_id"]))

    if len(review_id) > 1:
        if all(s == review_id[0] for s in review_id[1:]):
            print("[PASS] Các mốc có cùng id")
        else:
            print("[FAIL] Các mốc không có cùng id")
