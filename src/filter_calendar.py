"""M3: lọc calendar thô theo danh sách ids, lưu data/processed/calendar_<mốc>.csv.

Chạy từ gốc repo:
    python src/filter_calendar.py --config configs/porto.yaml
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml
KEEP_COLS = ["listing_id", "date", "available","minimum_nights","maximum_nights"]
CHUNKSIZE = 1_000_000          # calendar thô có hàng triệu dòng nên đọc theo khối


def load_ids(path):
    ids = pd.read_csv(path, dtype={"listing_id": "str"})["listing_id"]
    return set(ids.dropna())


def filter_calendar(path, id_set):
    parts = []
    for chunk in pd.read_csv(path, usecols=KEEP_COLS, dtype={"listing_id": "str"}, chunksize=CHUNKSIZE):
        parts.append(chunk[chunk["listing_id"].isin(id_set)])
    return pd.concat(parts, ignore_index=True)


def run(cfg, out_dir="data/processed"):
    id_set = load_ids(cfg["ids"])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for snap in cfg["snapshots"]:
        path = Path(cfg["calendar_raw"].format(snap=snap))
        if not path.exists():
            raise FileNotFoundError(f"Thieu {path} (chay src/download.py truoc, hoac kiem tra calendar_raw trong config)")
        cal = filter_calendar(path, id_set)
        cal.to_csv(Path(out_dir) / f"calendar_{snap}.csv", index=False)
        n_ids = cal["listing_id"].nunique()
        print(snap, "| ids:", n_ids, "/", len(id_set), "| rows:", len(cal))
        if n_ids < len(id_set):
            print(f"[CANH BAO] {snap}: {len(id_set) - n_ids} id khong co trong calendar cua mot nay")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        run(yaml.safe_load(f))