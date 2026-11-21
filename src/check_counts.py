import argparse
from pathlib import Path
import re
import sys
import pandas as pd
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description="Kiểm tra số dòng dữ liệu đã lọc trong data/interim")
ap.add_argument("--config", default="configs/porto.yaml", help="Đường dẫn file cấu hình YAML")
args = ap.parse_args()

cfg_path = Path(args.config)
if not cfg_path.is_absolute():
    cfg_path = ROOT / cfg_path
with cfg_path.open(encoding="utf-8") as config_file:
    cfg = yaml.safe_load(config_file)

DATA_DIR = ROOT / cfg["paths"]["interim"]

# Kỳ vọng theo từng mốc thời gian (hỗ trợ cả mốc cũ 2025-12-25 và mốc mới 2026-09-19).
# Ở mốc 2026-09-19 có 26 listing và 68 review ngừng hoạt động trên InsideAirbnb.
EXPECTED_BY_SNAP = {
    "2025-09-21": {"listings": 1000, "zero_reviews": 50, "missing_price": 40, "reviews": 5000},
    "2025-12-25": {"listings": 1000, "zero_reviews": 30, "missing_price": None, "reviews": 5000},
    "2026-03-26": {"listings": 1000, "zero_reviews": 25, "missing_price": 54, "reviews": 5000},
    "2026-06-23": {"listings": 1000, "zero_reviews": 25, "missing_price": 20, "reviews": 5000},
    "2026-09-19": {"listings": 974, "zero_reviews": 21, "missing_price": 35, "reviews": 4932},
}


def _snap_from_name(name: str) -> str:
    m = re.search(r"\d{4}-\d{2}-\d{2}", name)
    return m.group(0) if m else name


# Listings
listing_files = sorted(DATA_DIR.glob("listings_*.csv*"))
if not listing_files:
    print("\n[FAIL] Không tìm thấy file listings_*.csv*")
else:
    print("\n--- KIỂM TRA LISTINGS ---")
    listing_id = []

    for filepath in listing_files:
        snap = _snap_from_name(filepath.name)
        exp = EXPECTED_BY_SNAP.get(snap, {"listings": 1000, "zero_reviews": 25, "missing_price": 20, "reviews": 5000})
        df = pd.read_csv(filepath, dtype={"id": str}, low_memory=False)
        exp_rows = exp["listings"]

        if len(df) == exp_rows:
            print(f"[PASS] {filepath.name} đủ {exp_rows} dòng")
        else:
            print(f"[FAIL] {filepath.name} có {len(df)} dòng (kỳ vọng {exp_rows})")

        if "id" in df.columns:
            listing_id.append((snap, set(df["id"])))
        elif "listing_id" in df.columns:
            listing_id.append((snap, set(df["listing_id"])))

        if "room_type" in df.columns:
            counts = df["room_type"].value_counts().to_dict()
            if len(df) == 1000 and counts == {"Entire home/apt": 875, "Private room": 125}:
                print("[PASS] Đủ 875 Entire home/apt, 125 Private room")
            elif len(df) == exp_rows and set(counts).issubset({"Entire home/apt", "Private room"}):
                print(f"[PASS] room_type hợp lệ theo mẫu {exp_rows} dòng: {counts}")
            else:
                print(f"[FAIL] room_type không khớp kỳ vọng: {counts}")

        if "number_of_reviews" in df.columns:
            n_zero = int((df["number_of_reviews"] == 0).sum())
            if n_zero == exp["zero_reviews"]:
                print(f"[PASS] Đủ số id không có review ({n_zero})")
            else:
                print(f"[FAIL] Số id không có review là {n_zero} (kỳ vọng {exp['zero_reviews']})")

        if exp.get("missing_price") is not None and "price" in df.columns:
            n_na = int(df["price"].isna().sum())
            if n_na == exp["missing_price"]:
                print(f"[PASS] Mốc {snap} khớp {n_na} listing thiếu price")
            else:
                print(f"[FAIL] Mốc {snap} có {n_na} listing thiếu price (kỳ vọng {exp['missing_price']})")

        if "analysis_area" in df.columns:
            area_counts = df["analysis_area"].value_counts()
            low = 120 if exp_rows == 1000 else 115
            if area_counts[(area_counts < low) | (area_counts > 130)].empty:
                print(f"[PASS] analysis_area nằm trong khoảng [{low}, 130] listing")
            else:
                print("[FAIL] analysis_area ngoài khoảng kỳ vọng")

    if len(listing_id) > 1:
        first_snap, first_set = listing_id[0]
        if all(s.issubset(first_set) for _, s in listing_id[1:]):
            print("[PASS] Tập ID các mốc nhất quán (không phát sinh ID lạ ngoài mẫu 1.000)")
        else:
            print("[FAIL] Có ID lạ ngoài mẫu giữa các mốc")

# Calendar
cal_files = sorted(DATA_DIR.glob("calendar_*.csv*"))
if not cal_files:
    print("\n[FAIL] Không tìm thấy file calendar_*.csv*")
else:
    print("\n--- KIỂM TRA CALENDAR ---")
    calendar_id = []
    for filepath in cal_files:
        snap = _snap_from_name(filepath.name)
        exp_listings = EXPECTED_BY_SNAP.get(snap, {}).get("listings", 1000)
        exp_cal_rows = exp_listings * cfg.get("expected_days", 365)
        df = pd.read_csv(filepath, dtype={"listing_id": str})
        if len(df) == exp_cal_rows:
            print(f"[PASS] {filepath.name} đủ {exp_cal_rows} dòng ({exp_listings} listing x 365 ngày)")
        else:
            print(f"[FAIL] {filepath.name}: có {len(df)} dòng (kỳ vọng {exp_cal_rows})")

        if "listing_id" in df.columns:
            calendar_id.append(set(df["listing_id"]))
        elif "id" in df.columns:
            calendar_id.append(set(df["id"]))

    if len(calendar_id) > 1:
        if all(s.issubset(calendar_id[0]) for s in calendar_id[1:]):
            print("[PASS] Tập listing_id trong calendar nhất quán giữa các mốc")
        else:
            print("[FAIL] Các mốc calendar có listing_id không nhất quán")

# Review
review_files = sorted(DATA_DIR.glob("reviews_*.csv*"))
if not review_files:
    print("\n[FAIL] Không tìm thấy file reviews_*.csv*")
else:
    print("\n--- KIỂM TRA REVIEWS ---")
    review_id = []
    for filepath in review_files:
        snap = _snap_from_name(filepath.name)
        exp_rev = EXPECTED_BY_SNAP.get(snap, {}).get("reviews", 5000)
        df = pd.read_csv(filepath, dtype={"id": str})
        if len(df) == exp_rev:
            print(f"[PASS] {filepath.name} đủ {exp_rev} dòng")
        else:
            print(f"[FAIL] {filepath.name} có {len(df)} dòng (kỳ vọng {exp_rev})")

        if "id" in df.columns:
            review_id.append(set(df["id"]))
        elif "review_id" in df.columns:
            review_id.append(set(df["review_id"]))

    if len(review_id) > 1:
        if all(s.issubset(review_id[0]) for s in review_id[1:]):
            print("[PASS] Tập review_id nhất quán giữa các mốc (không phát sinh ID lạ)")
        else:
            print("[FAIL] Các mốc không có cùng tập review_id")
