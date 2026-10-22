import yaml
import pandas as pd
from src import filter_calendar

cfg = yaml.safe_load(open("configs/porto.yaml", encoding="utf-8"))
# cfg["snapshots"] = ["2026-06-23"]     # bỏ dấu # nếu chỉ muốn thử một mốc cho nhanh

ids = set(pd.read_csv("data/raw/id_listing.csv")["listing_id"])   # đổi tên cột nếu khác
print("so id doc duoc:", len(ids))

filter_calendar.run(cfg, ids)