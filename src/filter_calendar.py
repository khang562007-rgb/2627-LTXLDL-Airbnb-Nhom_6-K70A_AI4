from pathlib import Path
import pandas as pd

KEEP_COLS = ["listing_id", "date", "available"]


def filter_calendar(path, ids):
    ids = {str(int(x)) for x in ids}                     # chuẩn hóa ID về chuỗi
    cal = pd.read_csv(path, usecols=KEEP_COLS, dtype={"listing_id": "str"})
    return cal[cal["listing_id"].isin(ids)]


def run(cfg, ids, raw_dir="data/raw", out_dir="data/processed"):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for snap in cfg["snapshots"]:
        cal = filter_calendar(Path(raw_dir) / str(snap) / "calendar.csv.gz", ids)
        cal.to_csv(Path(out_dir) / f"calendar_{snap}.csv", index=False)
        print(snap, "| ids:", cal["listing_id"].nunique(), "| rows:", len(cal))