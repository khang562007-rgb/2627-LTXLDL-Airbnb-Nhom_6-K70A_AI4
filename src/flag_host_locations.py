import argparse
from pathlib import Path

import pandas as pd
import yaml

BOOL_COLS = ["host_is_superhost", "instant_bookable", "host_has_profile_pic", "host_identity_verified"]
BOOL_MAP = {"t": True, "f": False, "true": True, "false": False}
DEFAULT_BBOX = [41.10, 41.25, -8.70, -8.50]
DEFAULT_UNKNOWN = ["", "unknown", "n/a", "na", "none", "nan"]
NEEDED = {"id", "host_id", "host_listings_count", "host_since", "last_scraped", "host_response_rate",
          "latitude", "longitude", "neighbourhood_cleansed", *BOOL_COLS}


def read_listings(folder, snap, need):
    for ext in (".csv.gz", ".csv"):
        path = Path(folder) / f"listings_{snap}{ext}"
        if path.exists():
            break
    else:
        raise FileNotFoundError(f"Thieu listings_{snap}.csv(.gz) trong {folder} - can chay buoc loc truoc")
    lst = pd.read_csv(path, dtype={"id": "str", "host_id": "str"}, low_memory=False,
                      usecols=lambda c: c in need)
    missing = need - set(lst.columns)
    if missing:
        raise ValueError(f"{path.name} thieu cot: {sorted(missing)}")
    return lst


def dup_id(df):
    file = df.copy()
    file["flagged_dup_id"] = file["id"].duplicated(keep=False)
    return file


def host_id_missing(df):
    file = df.copy()
    file["flagged_host_id_missing"] = file["host_id"].isna()
    return file


def host_count_inconsistent(df):
    file = df.copy()
    declared = pd.to_numeric(file["host_listings_count"], errors="coerce")
    in_sample = file.groupby("host_id")["id"].transform("nunique")    # host_id thiếu => NaN => không cờ
    file["flagged_host_count_inconsistent"] = in_sample > declared
    return file


def host_since_invalid(df):
    file = df.copy()
    since = pd.to_datetime(file["host_since"], errors="coerce")
    scraped = pd.to_datetime(file["last_scraped"], errors="coerce")
    file["flagged_host_since_invalid"] = since.isna() | (since > scraped)
    return file


def response_rate(df):
    file = df.copy()
    rate = pd.to_numeric(file["host_response_rate"].astype(str).str.replace("%", "", regex=False).str.strip(),
                         errors="coerce")
    file["host_response_rate_clean"] = rate / 100
    file["flagged_host_rate_type"] = file["host_response_rate"].notna() & rate.isna()
    return file


def bool_clean(df):
    file = df.copy()
    for col in BOOL_COLS:
        file[f"{col}_clean"] = file[col].astype(str).str.lower().map(BOOL_MAP)
    return file


def _coords(df):
    return pd.to_numeric(df["latitude"], errors="coerce"), pd.to_numeric(df["longitude"], errors="coerce")


def coord_invalid(df):
    file = df.copy()
    lat, lon = _coords(file)
    file["flagged_coord_invalid"] = ~(lat.between(-90, 90) & lon.between(-180, 180))
    return file


def coord_outside_porto(df, bbox):
    file = df.copy()
    lat, lon = _coords(file)
    inside = lat.between(bbox[0], bbox[1]) & lon.between(bbox[2], bbox[3])
    file["flagged_coord_outside_porto"] = lat.notna() & lon.notna() & ~inside
    return file


def coord_outside_area(df, area_bounds, area_col):
    file = df.copy()
    lat, lon = _coords(file)
    bounds = pd.DataFrame.from_dict(area_bounds, orient="index", columns=["min_lat", "max_lat", "min_lon", "max_lon"])
    b = bounds.reindex(file[area_col])
    b.index = file.index
    mapped = b["min_lat"].notna()
    inside = (lat >= b["min_lat"]) & (lat <= b["max_lat"]) & (lon >= b["min_lon"]) & (lon <= b["max_lon"])
    file["flagged_area_unmapped"] = ~mapped
    file["flagged_coord_outside_area"] = mapped & lat.notna() & lon.notna() & ~inside
    return file


def neighbourhood_missing(df, unknown):
    file = df.copy()
    nb = file["neighbourhood_cleansed"]
    file["flagged_neighbourhood_missing"] = nb.isna() | nb.astype(str).str.strip().str.lower().isin(unknown)
    return file


def run(cfg, interim=None, out_dir="data/processed", report_dir="reports"):
    q = cfg.get("qa", {}).get("host", {})
    interim = interim or cfg["paths"]["interim"]
    bbox = q.get("porto_bbox", DEFAULT_BBOX)
    area_bounds, area_col = q.get("area_bounds"), q.get("area_col", "analysis_area")
    unknown = {str(u).lower() for u in q.get("unknown_neighbourhoods", DEFAULT_UNKNOWN)}
    need = NEEDED | ({area_col} if area_bounds else set())
    if not area_bounds:
        print("[LUU Y] Chua co qa.host.area_bounds trong config: bo qua kiem tra toa do theo khu")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(report_dir).mkdir(parents=True, exist_ok=True)

    rows = []
    for snap in cfg["snapshots"]:
        lst = read_listings(interim, snap, need)
        lst = dup_id(lst)
        lst = host_id_missing(lst)
        lst = host_count_inconsistent(lst)
        lst = host_since_invalid(lst)
        lst = response_rate(lst)
        lst = bool_clean(lst)
        lst = coord_invalid(lst)
        lst = coord_outside_porto(lst, bbox)
        if area_bounds:
            lst = coord_outside_area(lst, area_bounds, area_col)
        lst = neighbourhood_missing(lst, unknown)

        flag_cols = [c for c in lst.columns if c.startswith("flagged_")]
        clean_cols = [c for c in lst.columns if c.endswith("_clean")]
        lst[["id"] + flag_cols + clean_cols].to_csv(Path(out_dir) / f"flags_host_{snap}.csv", index=False)
        rows.append({"snapshot": snap, "n_listings": len(lst), **{c: int(lst[c].sum()) for c in flag_cols}})

    summary = pd.DataFrame(rows)
    summary.to_csv(Path(report_dir) / "flags_host_summary.csv", index=False)
    print(summary.T.to_string(header=False))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/porto.yaml")
    ap.add_argument("--interim", help="Thu muc chua listings_<mot>; mac dinh lay paths.interim trong config")
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        run(yaml.safe_load(f), args.interim)