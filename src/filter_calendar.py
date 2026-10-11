from pathlib import Path
import pandas as pd
#Giữ các cột nào lại
KEEP_COLS = ["listing_id","date","available"]
ids = set(pd.read_csv("data/raw/id_listing.csv")["listing_id"])
#Lọc các calendar theo các cột trong KEEP_COLS
def filter_calendar(path,ids,keep_cols=KEEP_COLS,chunksize=1_000_000):
    header = pd.read_csv(path, nrows=0).columns
    missing = [c for c in keep_cols if c not in header]
    #Nếu cột thiếu trong header thì in ra
    if missing:
        raise ValueError(f"{path}: thieu cot {missing}; cot hien co: {list(header)}")
    ids=set(ids)
    parts = []
    for chunk in pd.read_csv(path,usecols=keep_cols,dtype={"listing_id":"int64"},chunksize=chunksize):
        parts.append(chunk[chunk["listing_id"].isin(ids)])
    return pd.concat(parts,ignore_index=True) 
#Check xem từng id có các ngày tháng không bị trùng lặp với nhau không
def check(cal,ids,snap,expected_days=365):
    days=cal.groupby("listing_id")["date"].nunique() 
    return {
        "snapshot": snap,
        "ids_requested": len(ids),
        "ids_found": cal["listing_id"].nunique(),
        "rows": len(cal),
        "rows_expected": len(ids) * expected_days,
        "listings_days_not_365": int((days != expected_days).sum()),
        "duplicate_rows": int(cal.duplicated(["listing_id", "date"]).sum()),
        "date_min": cal["date"].min(),
        "date_max": cal["date"].max(),
    }
#Pipline đọc file,lọc file,ghi file đã lọc
def run(cfg,ids,raw_dir="data/raw",out_dir="data/processed"):
    Path(out_dir).mkdir(parents=True,exist_ok=True)
    result = []
    for s in cfg["snapshots"]:
        cal = filter_calendar(Path(raw_dir)/s/"calendar.csv.gz",ids)
        result.append(check(cal,ids,s))
        cal.to_csv(Path(out_dir)/f"calendar_{s}.csv.gz",index=False)
    summary = pd.DataFrame(result)
    print(summary.to_string(index=False))
    return summary  
