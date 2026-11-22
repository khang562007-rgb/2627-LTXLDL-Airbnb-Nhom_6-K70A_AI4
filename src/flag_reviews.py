"""QA cho bảng reviews và các cờ review của listings, chỉ trên dữ liệu nhóm được giao.
Cần có sẵn trong data/interim/ (do bước lọc tạo ra):
    reviews_<mốc>.csv(.gz)   và   listings_<mốc>.csv(.gz)
Chạy từ gốc repo:  python src/qa.py [--config configs/porto.yaml]
"""
import argparse
import html
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
TAG = r"<[a-zA-Z/][^>]*>"
BR = r"<br\s*/?>"
LS_COLS = {"id", "last_scraped", "number_of_reviews", "last_review"}
LS_NEEDED = LS_COLS - {"last_review"}          # last_review thiếu thì vẫn chạy được

# tên: (loại, bảng, điều kiện, lý do, hành động)
RULES = {
    "review_dup_id": ("flag", "reviews", "id review xuất hiện từ 2 lần trở lên trong cùng mốc",
                      "Đếm trùng", "Gắn cờ"),
    "review_dup_content": ("flag", "reviews", "Cùng (listing_id, reviewer_id, date, comments)",
                           "Review lặp", "Gắn cờ"),
    "review_orphan": ("flag", "reviews", "listing_id không có trong listings của nhóm cùng mốc",
                      "Review mồ côi", "Gắn cờ"),
    "review_date_invalid": ("flag", "reviews",
                        "Ngày null hoặc sau last_scraped",
                        "Ngày vô lý",
                        "Gắn cờ, vẫn giữ trong mẫu LLM"),
    "comment_markup": ("flag", "reviews", "comments chứa thẻ HTML (như <br/>)",
                       "Làm nhiễu LLM", "Tạo cột comment_clean, giữ nguyên cột gốc"),
    "comment_empty_or_short": ("flag", "reviews", "comment_clean rỗng hoặc dưới min_comment_len ký tự",
                               "Không phân tích được", "Gắn cờ, loại khỏi mẫu LLM nhưng vẫn giữ dòng"),
    "llm_sample_size": ("impact", "reviews", "Số review bị loại khỏi mẫu LLM (exclude_from_llm_sample)",
                        "Tác động của QA lên mẫu LLM", "Báo cáo"),
    "zero_review_count": ("flag", "listings", "number_of_reviews = 0",
                          "Số kiểm tra riêng cho nhóm ở bảng tính", "Gắn cờ no_reviews, đối chiếu bảng tính"),
    "reviews_inconsistent": ("flag", "listings",
                             "number_of_reviews = 0 nhưng có review_scores_*/last_review, hoặc ngược lại",
                             "Mâu thuẫn", "Gắn cờ"),
    "review_score_range": ("flag", "listings", "review_scores_* ngoài [score_min, score_max]",
                           "Vô lý", "Gắn cờ"),
    "key_unique": ("check", "reviews", "id duy nhất trong mỗi mốc",
                   "Khóa chính", "Báo cáo (rows_flagged = số id lặp, 0 là đạt)"),
    "id_set_consistent": ("check", "reviews", "review_id của mốc trước còn có ở mốc sau",
                          "Review biến mất giữa các mốc", "Báo cáo (rows_flagged = số id biến mất)"),
}
REVIEW_FLAGS = ["review_dup_id", "review_dup_content", "review_orphan", "review_date_invalid"]
report = []


def add(rule, snap, total, flagged, note=""):
    kind, table, cond, why, act = RULES[rule]
    report.append(dict(rule=rule, kind=kind, table=table, snapshot=snap,
                       condition=cond, reason=why, action=act,
                       rows_total=int(total), rows_flagged=int(flagged), note=note))


def find_file(folder, prefix, snap):
    """File đã lọc ở bước trước (nhận .csv.gz và .csv). Thiếu thì dừng, không dùng dữ liệu thô."""
    for ext in (".csv.gz", ".csv"):
        p = folder / f"{prefix}_{snap}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Thiếu {prefix}_{snap}.csv(.gz) trong {folder} - cần chạy bước lọc (filter_all.py) trước")


def read_listings(folder, snap):
    ls = pd.read_csv(find_file(folder, "listings", snap), dtype={"id": str}, low_memory=False,
                     usecols=lambda c: c in LS_COLS or c.startswith("review_scores_"))
    missing = LS_NEEDED - set(ls.columns)
    if missing:
        raise ValueError(f"listings_{snap} thiếu cột: {sorted(missing)}")
    if not any(c.startswith("review_scores_") for c in ls.columns):
        raise ValueError(f"listings_{snap} không có cột review_scores_*")
    return ls

def flag_review_table(rv, ls, q):
    rv = rv.copy()
    rv["review_dup_id"] = rv["id"].duplicated(keep=False)
    rv["review_dup_content"] = rv.duplicated(q["dup_content_keys"], keep=False)
    rv["review_orphan"] = ~rv["listing_id"].isin(set(ls["id"]))

    info = ls.drop_duplicates("id").set_index("id")
    d = pd.to_datetime(rv["date"], errors="coerce")
    scraped = pd.to_datetime(rv["listing_id"].map(info["last_scraped"]), errors="coerce")

    rv["_date_null"] = d.isna()
    rv["_after_scrape"] = d > scraped
    rv["review_date_invalid"] = rv["_date_null"] | rv["_after_scrape"]
    return rv


def date_note(rv, ls):
    return (f"ngày null={int(rv['_date_null'].sum())}; "
            f"sau last_scraped={int(rv['_after_scrape'].sum())}")



def flag_text(rv, q):
    rv = rv.copy()
    c = rv["comments"].fillna("")
    rv["comment_markup"] = c.str.contains(TAG, regex=True)
    rv["comment_clean"] = (c.map(html.unescape)
                            .str.replace(BR, " ", regex=True, case=False)
                            .str.replace(TAG, "", regex=True)
                            .str.replace("\xa0", " ", regex=False)
                            .str.replace(r"\s+", " ", regex=True)
                            .str.strip())
    rv["comment_empty_or_short"] = rv["comment_clean"].str.len() < q["min_comment_len"]
    rv["exclude_from_llm_sample"] = rv["comment_empty_or_short"]
    return rv


def flag_listings(ls, q):
    score_cols = [c for c in ls.columns if c.startswith("review_scores_")]
    n = pd.to_numeric(ls["number_of_reviews"], errors="coerce")
    scores = ls[score_cols].apply(pd.to_numeric, errors="coerce")
    has_last = ls["last_review"].notna() if "last_review" in ls.columns else False
    has_info = scores.notna().any(axis=1) | has_last

    out = pd.DataFrame({"id": ls["id"]})
    out["no_reviews"] = n.eq(0)
    out["reviews_inconsistent"] = (n.eq(0) & has_info) | (n.gt(0) & ~has_info)
    out["review_score_range"] = ((scores < q["score_min"]) | (scores > q["score_max"])).any(axis=1)

    notes = {
        "zero_review_count": f"number_of_reviews null: {int(n.isna().sum())}",
        "reviews_inconsistent": (f"n=0 nhưng có điểm/last_review: {int((n.eq(0) & has_info).sum())}; "
                                 f"n>0 nhưng không có: {int((n.gt(0) & ~has_info).sum())}"),
        "review_score_range": (f"thang quan sát: min={scores.min().min()}, max={scores.max().max()}; "
                               f"thang cấu hình: [{q['score_min']}, {q['score_max']}]"),
    }
    return out, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/porto.yaml")
    cfg = yaml.safe_load(open(ROOT / ap.parse_args().config, encoding="utf-8"))
    q = cfg["qa"]["reviews"]
    interim = ROOT / cfg["paths"]["interim"]
    processed = ROOT / cfg["paths"]["processed"]
    processed.mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "interim" / "qa_parts").mkdir(parents=True, exist_ok=True)
    ids_by_snap = {}

    for snap in cfg["snapshots"]:
        rv = pd.read_csv(find_file(interim, "reviews", snap),
                         dtype={"id": str, "listing_id": str, "reviewer_id": str})
        ls = read_listings(interim, snap)

        # --- reviews ---
        ids_by_snap[snap] = set(rv["id"])
        add("key_unique", snap, len(rv), rv["id"].duplicated().sum())
        rv = flag_review_table(rv, ls, q)
        for r in REVIEW_FLAGS:
            add(r, snap, len(rv), rv[r].sum(), date_note(rv, ls) if r == "review_date_invalid" else "")

        rv = flag_text(rv, q)
        for r in ["comment_markup", "comment_empty_or_short"]:
            add(r, snap, len(rv), rv[r].sum())
        ex = int(rv["exclude_from_llm_sample"].sum())
        add("llm_sample_size", snap, len(rv), ex, f"đủ điều kiện vào mẫu LLM: {len(rv) - ex}")

        rv.drop(columns=[c for c in rv.columns if c.startswith("_")]).to_csv(
            processed / f"reviews_flagged_{snap}.csv.gz", index=False, encoding="utf-8-sig",
            compression={"method": "gzip", "mtime": 0})

        # --- cờ review của listings nhóm ---
        lf, notes = flag_listings(ls, q)
        for r, col in [("zero_review_count", "no_reviews"),
                       ("reviews_inconsistent", "reviews_inconsistent"),
                       ("review_score_range", "review_score_range")]:
            add(r, snap, len(lf), lf[col].sum(), notes[r])
        lf.to_csv(processed / f"listings_review_flags_{snap}.csv.gz", index=False, encoding="utf-8-sig",
                  compression={"method": "gzip", "mtime": 0})

    # --- giữa các mốc ---
    snaps = cfg["snapshots"]
    for a, b in zip(snaps, snaps[1:]):
        gone, new = len(ids_by_snap[a] - ids_by_snap[b]), len(ids_by_snap[b] - ids_by_snap[a])
        add("id_set_consistent", f"{a}->{b}", len(ids_by_snap[a]), gone, f"mới ở mốc sau: {new}")

    rep = pd.DataFrame(report)
    rep.to_csv(ROOT / "data" / "interim" / "qa_parts" / "qa_report_reviews.csv", index=False, encoding="utf-8-sig")
    print(rep[["rule", "snapshot", "rows_total", "rows_flagged"]].to_string(index=False))


if __name__ == "__main__":
    main()