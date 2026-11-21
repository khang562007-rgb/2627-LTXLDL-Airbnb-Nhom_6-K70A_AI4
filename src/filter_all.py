import argparse
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description="Lọc dữ liệu thô theo mẫu nhóm")
ap.add_argument("--config", default="configs/porto.yaml", help="Đường dẫn file cấu hình YAML")
args = ap.parse_args()

cfg_path = Path(args.config)
if not cfg_path.is_absolute():
    cfg_path = ROOT / cfg_path
cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))

DATA = ROOT / cfg["paths"]["raw_root"]
OUT = ROOT / cfg["paths"]["interim"]
OUT.mkdir(parents=True, exist_ok=True)

SNAPSHOTS = cfg["snapshots"]
s = cfg["sample"]
CAL_COLS = s["calendar_cols"]

try:
    import pyarrow  # noqa: F401
    CAL_ENGINE = "pyarrow"
except ImportError:
    CAL_ENGINE = "c"
    print("chưa có pyarrow -> calendar chạy chậm hơn, nên cài: pip install pyarrow")
    
def read_ids(block):
    """Đọc danh sách id; nếu file chưa có hoặc rỗng thì tải lại từ link."""
    path = ROOT / block["ids_path"]
    if not path.exists() or path.stat().st_size == 0:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.read_csv(block["ids_url"], dtype=str).to_csv(path, index=False, encoding="utf-8-sig")
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    if s.get("data_code") and "Mã dữ liệu" in df.columns:
        df = df[df["Mã dữ liệu"] == s["data_code"]]
    return df


# 0. tập id của nhóm (đọc dạng chuỗi để không hỏng id dài)
review_ids = set(read_ids(s["reviews"])["review_id"])
ids = read_ids(s["listings"])[["listing_id", "analysis_area"]].copy()
listing_ids = set(ids["listing_id"])
print("review_id:", len(review_ids), "| listing_id:", len(ids),
      "| listing trùng:", ids["listing_id"].duplicated().sum())   # kỳ vọng 5000 | ~1000 | 0

# 1. listings: lọc id của nhóm + ghép analysis_area
for snap in SNAPSHOTS:
    raw = pd.read_csv(DATA / snap / "listings.csv.gz", dtype={"id": str}, low_memory=False)
    sub = raw[raw["id"].isin(listing_ids)].merge(
        ids, left_on="id", right_on="listing_id", how="left").drop(columns="listing_id")
    print("listings", snap, "| raw:", len(raw), "->", sub.shape,
          "| id không thấy:", len(listing_ids - set(sub["id"])))
    sub.to_csv(OUT / f"listings_{snap}.csv.gz", index=False, encoding="utf-8-sig")

# 2. calendar: chỉ đọc các cột cần, lọc id của nhóm
for snap in SNAPSHOTS:
    cal = pd.read_csv(DATA / snap / "calendar.csv.gz",
                      usecols=CAL_COLS, dtype={"listing_id": str}, engine=CAL_ENGINE)
    sub = cal[cal["listing_id"].isin(listing_ids)]
    print("calendar", snap, "| ids:", sub["listing_id"].nunique(), "|", sub.shape)
    sub.to_csv(OUT / f"calendar_{snap}.csv.gz", index=False, encoding="utf-8-sig")

# 3. reviews: lọc theo tập review_id
for snap in SNAPSHOTS:
    rv = pd.read_csv(DATA / snap / "reviews.csv.gz",
                     dtype={"id": str, "listing_id": str, "reviewer_id": str})
    sub = rv[rv["id"].isin(review_ids)]
    print("reviews", snap, sub.shape)                              # kỳ vọng (5000, 6)
    sub.to_csv(OUT / f"reviews_{snap}.csv.gz", index=False, encoding="utf-8-sig")