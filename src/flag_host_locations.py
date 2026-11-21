"""QA cờ host và location trên listings đã lọc; tạo báo cáo cùng schema với qa.py.

Chạy từ gốc repo: python src/flag_host_locations.py [--config configs/porto.yaml]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit_flags import audit_table, check_collisions, sample_flagged
import pandas as pd
import yaml
RULES = {
    "dup_id_in_snapshot": ("flag", "listings", "id xuất hiện từ 2 lần trở lên", "Khóa listing trùng", "Gắn cờ"),
    "host_id_missing": ("flag", "listings", "host_id bị thiếu", "Không xác định được chủ nhà", "Gắn cờ"),
    "host_count_inconsistent": ("flag", "listings", "số listing mẫu của host lớn hơn host_listings_count", "Thông tin số lượng không khớp", "Gắn cờ"),
    "host_since_invalid": ("flag", "listings", "host_since thiếu hoặc sau last_scraped", "Mốc thời gian không hợp lệ", "Gắn cờ"),
    "host_rate_type": ("flag", "listings", "host_response_rate có giá trị nhưng không parse được", "Sai định dạng tỷ lệ phản hồi", "Gắn cờ; giữ giá trị gốc"),
    "coord_missing_or_invalid": ("flag", "listings", "latitude/longitude thiếu hoặc ngoài miền hợp lệ", "Toạ độ không hợp lệ", "Gắn cờ"),
    "coord_outside_porto": ("flag", "listings", "toạ độ ngoài khung Porto cấu hình", "Vị trí ngoài khu vực nghiên cứu", "Gắn cờ"),
    "coord_outside_area": ("flag", "listings", "toạ độ ngoài khung analysis_area cấu hình", "Khu vực phân tích không khớp", "Gắn cờ"),
    "neighbourhood_missing_or_unknown": ("flag", "listings", "neighbourhood_cleansed bị thiếu", "Không phân loại được khu vực", "Gắn cờ"),
}
report = []


def add(rule, snap, total, flagged, note=""):
    kind, table, cond, why, act = RULES[rule]
    report.append(dict(rule=rule, kind=kind, table=table, snapshot=snap,
                       condition=cond, reason=why, action=act,
                       rows_total=int(total), rows_flagged=int(flagged), note=note))


def find_file(folder, snap):
    for ext in (".csv.gz", ".csv"):
        path = folder / f"listings_{snap}{ext}"
        if path.exists():
            return path
    raise FileNotFoundError(f"Thiếu listings_{snap}.csv(.gz) trong {folder}; hãy chạy filter_all.py trước")


def _bounds_mask(df, bounds):
    lat = pd.to_numeric(df.get("latitude"), errors="coerce")
    lon = pd.to_numeric(df.get("longitude"), errors="coerce")
    return ~lat.between(bounds[0], bounds[1]) | ~lon.between(bounds[2], bounds[3])


def flag_host_location(df, q):
    """Trả về bản sao có cờ; cột nguồn không bị sửa."""
    out = df.copy()
    out["dup_id_in_snapshot"] = out["id"].duplicated(keep=False)
    out["host_id_missing"] = out["host_id"].isna()
    declared = pd.to_numeric(out["host_listings_count"], errors="coerce")
    sample_count = out["host_id"].map(out["host_id"].value_counts())
    out["host_count_inconsistent"] = sample_count.gt(declared).fillna(False)
    since = pd.to_datetime(out["host_since"], errors="coerce")
    scraped = pd.to_datetime(out["last_scraped"], errors="coerce")
    out["host_since_invalid"] = since.isna() | (since > scraped)
    rate = out["host_response_rate"].astype("string").str.replace("%", "", regex=False).str.strip()
    rate_clean = pd.to_numeric(rate, errors="coerce")
    out["host_rate_type"] = out["host_response_rate"].notna() & rate_clean.isna()
    lat = pd.to_numeric(out["latitude"], errors="coerce")
    lon = pd.to_numeric(out["longitude"], errors="coerce")
    out["coord_missing_or_invalid"] = ~lat.between(-90, 90) | ~lon.between(-180, 180)
    porto = q.get("porto_bounds", [41.10, 41.25, -8.70, -8.50])
    out["coord_outside_porto"] = _bounds_mask(out, porto)
    bounds = q.get("area_bounds", {})
    if bounds and "analysis_area" in out.columns:
        b_df = pd.DataFrame.from_dict(bounds, orient="index", columns=["min_lat", "max_lat", "min_lon", "max_lon"])
        mapped = out[["analysis_area"]].join(b_df, on="analysis_area")
        in_area = (
            lat.between(mapped["min_lat"], mapped["max_lat"])
            & lon.between(mapped["min_lon"], mapped["max_lon"])
        )
        out["coord_outside_area"] = ~in_area
    else:
        out["coord_outside_area"] = False
    out["neighbourhood_missing_or_unknown"] = out["neighbourhood_cleansed"].isna()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/porto.yaml")
    cfg = yaml.safe_load((ROOT / ap.parse_args().config).open(encoding="utf-8"))
    q = cfg.get("qa", {}).get("host", {})
    interim, processed = ROOT / cfg["paths"]["interim"], ROOT / cfg["paths"]["processed"]
    processed.mkdir(parents=True, exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    report.clear()
    for snap in cfg["snapshots"]:
        df = pd.read_csv(find_file(interim, snap), dtype={"id": str, "host_id": str}, low_memory=False)
        flagged = flag_host_location(df, q)
        since_null = int(pd.to_datetime(df.get("host_since"), errors="coerce").isna().sum())
        for rule in RULES:
            note = ""
            if rule == "host_since_invalid" and since_null:
                note = f"host_since thiếu: {since_null}/{len(df)}"
            elif rule == "coord_outside_area" and not q.get("area_bounds"):
                note = "chưa cấu hình area_bounds"
            add(rule, snap, len(flagged), flagged[rule].sum(), note)
        flags = list(RULES)
        flagged[["id"] + flags].to_csv(processed / f"listings_host_location_flags_{snap}.csv.gz",
                                         index=False, encoding="utf-8-sig")
    rep = pd.DataFrame(report)
    rep.to_csv(ROOT / "reports" / "qa_report_host_locations.csv", index=False, encoding="utf-8-sig")
    print(rep[["rule", "snapshot", "rows_total", "rows_flagged"]].to_string(index=False))


if __name__ == "__main__":
    main()