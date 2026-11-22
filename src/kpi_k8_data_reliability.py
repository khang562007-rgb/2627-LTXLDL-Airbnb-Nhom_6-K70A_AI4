"""K8 - độ tin cậy dữ liệu.
Lượt 1:  python -m src.kpi8
Lượt 2:  python -m src.kpi8 configs/porto.yaml data/processed <labels.csv> <kpi_k07.csv>
"""
import sys
from pathlib import Path

import pandas as pd
import yaml

if __package__:
    from .kpi_common import OUT_COLS, Recorder, kpi_row, pick_sample, usecols
    from .kpi_rules import RULES_K8
else:
    from kpi_common import OUT_COLS, Recorder, kpi_row, pick_sample, usecols
    from kpi_rules import RULES_K8

K = "k08"


def main(
    config_path="configs/porto.yaml",
    out_dir=None,
    labels_path=None,
    k07_path=None,
):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    processed = Path(cfg["paths"]["processed"])
    out_dir = Path(out_dir) if out_dir else processed
    out_dir.mkdir(parents=True, exist_ok=True)
    kcfg = cfg["kpi"]
    cols, flags, excl = kcfg["columns"], kcfg["columns"]["flags"], kcfg["exclude_rules"]
    use_rev = usecols(cols["reviews"]["k7"], cols["reviews"]["k8"], flags["review_exclude"], flags["review_warn"])
    use_lst = usecols(["id"], flags["listing_warn"])
    areas_path = Path(cols["areas"]["path"])
    area_ids = set(pd.read_csv(areas_path, usecols=["listing_id"])["listing_id"]) if areas_path.exists() else None

    rec = Recorder(K, RULES_K8)
    valid_parts, prev, lst_ids = [], None, {}
    for snap in cfg["snapshots"]:
        rev = pd.read_csv(processed / f"reviews_flagged_{snap}.csv.gz", usecols=use_rev)
        lst = pd.read_csv(processed / f"listings_review_flags_{snap}.csv.gz", usecols=use_lst)
        n_rev, n_lst = len(rev), len(lst)
        lst_ids[snap] = set(lst["id"])

        # cờ của QA: chỉ đếm (mô tả nằm ở báo cáo QA)
        for rule in flags["review_exclude"] + flags["review_warn"]:
            rec.kpi_rows.append(kpi_row(K, f"{K}_{rule}", snap, n_rev, rev[rule].sum()))
        for rule in flags["listing_warn"]:
            rec.kpi_rows.append(kpi_row(K, f"{K}_{rule}", snap, n_lst, lst[rule].sum()))
        is_excl = rev[excl].any(axis=1)
        rec.kpi_rows.append(kpi_row(K, f"{K}_excluded_total", snap, n_rev, is_excl.sum()))
        rec.kpi_rows.append(kpi_row(K, f"{K}_key_unique", snap, n_rev, rev["id"].duplicated().sum()))

        # rule của K8 (RULES_K8)
        if area_ids is not None:
            rec.add("listing_join_coverage", snap, n_lst, (~lst["id"].isin(area_ids)).sum())
        if prev is not None:
            rec.kpi_rows.append(kpi_row(K, f"{K}_id_set_consistent", snap, len(prev["ids"]),
                                        len(prev["ids"] - set(rev["id"]))))
            rec.add("snapshot_row_count_drop", snap, prev["n"], max(prev["n"] - n_rev, 0))
            rec.add("date_max_advances", snap, 1, int(rev["date"].max() <= prev["dmax"]),
                    note=f"mốc trước: {prev['snap']}")
        prev = {"ids": set(rev["id"]), "n": n_rev, "snap": snap, "dmax": rev["date"].max()}

        v = rev.loc[~is_excl, cols["reviews"]["k7"]].copy()
        v.insert(0, "snapshot", snap)
        valid_parts.append(v)

    valid = pd.concat(valid_parts)
    valid.to_csv(out_dir / "reviews_valid.csv", index=False, encoding="utf-8")

    # mẫu LLM: mỗi listing 1 review ngẫu nhiên theo seed (cùng hàm với k07.py)
    per = kcfg["k7"]["llm"].get("sample", {}).get("per_listing", 1)
    sample_ids = pick_sample(valid, cfg.get("seed", 42), per)
    vs = valid[valid["id"].isin(sample_ids)]
    for snap, g in vs.groupby("snapshot"):
        rec.add("listing_sample_coverage", snap, len(lst_ids[snap]), len(lst_ids[snap] - set(g["listing_id"])))

    # ---- lượt 2: cần nhãn LLM và K7 ----
    if labels_path:
        labeled = set(pd.read_csv(labels_path, usecols=["id"])["id"])
        for snap, g in vs.groupby("snapshot"):
            rec.add("label_coverage", snap, len(g), (~g["id"].isin(labeled)).sum())
    if k07_path:
        k7 = pd.read_csv(k07_path)
        k7 = k7[k7[kcfg["output_area_col"]] != "ALL"]               # bỏ dòng toàn thành phố, tránh đếm lặp
        for snap, g in k7.groupby("snapshot"):
            tot = g.n_used.sum() + g.n_excluded.sum()
            share = g.n_excluded.sum() / tot if tot else 0
            over = share > kcfg["max_excluded_share"]
            rec.add("kpi_excluded_share", snap, tot, g.n_excluded.sum(),
                    note=f"{'VƯỢT' if over else 'trong'} ngưỡng {kcfg['max_excluded_share']:.0%}")

    pd.DataFrame(rec.kpi_rows)[OUT_COLS].to_csv(out_dir / "kpi_k8_data_reliability.csv", index=False, encoding="utf-8")
    rec.save_report(out_dir / "kpi_k8_report.csv")
    print(f"ok K8: {len(rec.kpi_rows)} dòng KPI, {len(valid)} dòng review hợp lệ")


if __name__ == "__main__":
    main(*sys.argv[1:])