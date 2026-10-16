from pathlib import Path
import pandas as pd
ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "clean"
OUT.mkdir(exist_ok=True)

MA_DU_LIEU = "DSE2049-C04-G06-porto"
IDS_PATH = ROOT / "porto-listings.csv"
SNAPSHOTS = ["2025-09-21", "2025-12-25", "2026-03-26", "2026-06-23"]
SHEET = ("https://docs.google.com/spreadsheets/d/"
         "1Ru6653xzX4r29ywxoGSGA543F3QjXwQaVgC19WTwNEA/export?format=csv&gid=0")
CAL_COLS = ["listing_id", "date", "available"]

# calendar chỉ có 3 cột đơn giản -> dùng pyarrow cho nhanh (đa luồng), không có thì dùng engine mặc định
# listings/reviews có text nhiều dòng (description, comments) -> pyarrow đọc lỗi, phải dùng engine mặc định
try:
    import pyarrow  # noqa: F401
    CAL_ENGINE = "pyarrow"
except ImportError:
    CAL_ENGINE = "c"
    print("chưa có pyarrow -> calendar chạy chậm hơn, nên cài: pip install pyarrow")

# 0. tập listing_id của nhóm (đọc dạng chuỗi để không hỏng id dài)
ids_all = pd.read_csv(IDS_PATH, dtype=str, encoding="utf-8-sig")
ids_all.columns = ids_all.columns.str.strip()
ids = ids_all[ids_all["Mã dữ liệu"] == MA_DU_LIEU][["listing_id", "analysis_area"]].copy()
listing_ids = set(ids["listing_id"])
print("số ID:", len(ids), "| trùng:", ids["listing_id"].duplicated().sum())  # kỳ vọng 1000 | 0

# 1. listings: lọc id của nhóm + ghép analysis_area
for snap in SNAPSHOTS:
    raw = pd.read_csv(DATA / snap / "listings.csv.gz", dtype={"id": str}, low_memory=False)
    sub = raw[raw["id"].isin(listing_ids)].merge(
        ids, left_on="id", right_on="listing_id", how="left").drop(columns="listing_id")
    print("listings", snap, "| raw:", len(raw), "->", sub.shape)  # kỳ vọng (1000, ...)

    sub.to_csv(OUT / f"listings_{snap}.csv",
               index=False, encoding="utf-8-sig")

# 2. calendar: chỉ đọc 3 cột cần, lọc id của nhóm
for snap in SNAPSHOTS:
    cal = pd.read_csv(DATA / snap / "calendar.csv.gz",
                      usecols=CAL_COLS, dtype={"listing_id": str}, engine=CAL_ENGINE)
    sub = cal[cal["listing_id"].isin(listing_ids)]
    print("calendar", snap, "| ids:", sub["listing_id"].nunique(), "|", sub.shape)  # kỳ vọng 1000 ids

    sub.to_csv(OUT / f"calendar_{snap}.csv",
               index=False, encoding="utf-8-sig")

# 3. reviews: lọc theo tập review_id trong sheet
sheet = pd.read_csv(SHEET, dtype=str, usecols=["review_id"])
review_ids = set(sheet["review_id"])

for snap in SNAPSHOTS:
    rv = pd.read_csv(DATA / snap / "reviews.csv.gz",
                     dtype={"id": str, "listing_id": str, "reviewer_id": str})
    sub = rv[rv["id"].isin(review_ids)]
    print("reviews", snap, sub.shape)             # kỳ vọng (5000, 6)

    sub.to_csv(OUT / f"reviews_{snap}.csv",
               index=False, encoding="utf-8-sig")