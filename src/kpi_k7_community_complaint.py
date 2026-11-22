"""K7 - tỷ lệ review có phàn nàn cộng đồng, theo khu.
Mẫu LLM: mỗi listing 1 review ngẫu nhiên theo seed (từ reviews_valid.csv).
python src/kpi_k7_community_complaint.py configs/porto.yaml data/processed/reviews_valid.csv data/processed
python src/kpi_k7_community_complaint.py configs/porto.yaml data/processed/reviews_valid.csv data/processed --handlabel   (chỉ làm mẫu gán tay)
python src/kpi_k7_community_complaint.py configs/porto.yaml data/processed/reviews_valid.csv data/processed --skip-llm    (chỉ dùng cache, không gọi LLM)
Nhãn LLM lưu cache; chạy lại thì chỉ gọi LLM cho review chưa có nhãn.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from kpi_common import OUT_COLS, Recorder, pick_sample
from kpi_rules import RULES_K7
from llm_label import handlabel_sample, run_labeling

K = "k07"


def norm(s):
    return " ".join(str(s).lower().split())


def evidence_ok(ev, comment):
    parts = [p for p in str(ev).split(" | ") if p.strip()]
    return bool(parts) and all(norm(p) in norm(comment) for p in parts)


def main(config_path, valid_path, out_dir, handlabel=False, skip_llm=False):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    kcfg = cfg["kpi"]
    if skip_llm:                                  # chỉ dùng nhãn đã có trong cache, không gọi API
        kcfg["k7"]["llm"]["skip_llm"] = True
    area_col, out_area = kcfg["area_col"], kcfg["output_area_col"]
    community = set(kcfg["k7"]["aspects"]["community"])
    min_n, out_dir = kcfg["min_cell_n"], Path(out_dir)

    valid = pd.read_csv(valid_path)
    areas = pd.read_csv(kcfg["columns"]["areas"]["path"], usecols=kcfg["columns"]["areas"]["cols"])

    # mẫu LLM: mỗi listing 1 review ngẫu nhiên theo seed; K7 chỉ tính trên mẫu này
    per = kcfg["k7"]["llm"].get("sample", {}).get("per_listing", 1)
    valid = valid[valid["id"].isin(pick_sample(valid, cfg.get("seed", 42), per))]
    uniq = valid.drop_duplicates("id")[["id", "listing_id", "comment_clean"]].merge(areas, on="listing_id", how="left")
    print(f"Mẫu LLM: {len(uniq)} review từ {uniq['listing_id'].nunique()} listing")

    if handlabel:
        h = kcfg["k7"]["handlabel"]
        handlabel_sample(uniq, area_col, h["n"], cfg.get("seed", 42), h["path"])
        return
    skip_llm = skip_llm or bool(kcfg["k7"]["llm"].get("skip", False))
    labels = run_labeling(uniq, cfg, skip_llm=skip_llm)   # có cache thì chỉ gọi LLM cho review chưa có nhãn
    if labels.empty:
        raise SystemExit("Chưa có nhãn LLM nào (cache rỗng hoặc lỗi API). Chạy lại không có --skip-llm khi đã có key.")

    labels = labels.assign(has_label=True)
    df = (valid.merge(areas, on="listing_id", how="left")
               .merge(labels, on="id", how="left"))
    df["has_area"] = df[area_col].notna()
    df["has_label"] = df["has_label"].fillna(False).astype(bool)
    df["label_valid"] = df["label_valid"].fillna(False).astype(bool)
    crit = df["aspects_criticized"].fillna("").map(lambda s: set(filter(None, str(s).split(";"))))
    df["is_complaint"] = crit.map(lambda s: bool(community & s))
    bad = pd.Series([not evidence_ok(e, c) for e, c in zip(df["evidence"].fillna(""), df["comment_clean"])],
                    index=df.index)
    df["evidence_missing"] = df["is_complaint"] & bad
    # --- cờ review (RULES_K7) ---
    df["f_no_area"] = ~df["has_area"]
    df["f_label_invalid"] = df["has_label"] & ~df["label_valid"]
    df["f_evidence"] = df["has_label"] & df["label_valid"] & df["evidence_missing"]
    df["ok"] = df["has_area"] & df["has_label"] & df["label_valid"] & ~df["evidence_missing"]

    rec = Recorder(K, RULES_K7)
    for snap, g in df.groupby("snapshot"):
        rec.add("listing_no_neighbourhood", snap, len(g), g.f_no_area.sum(), to_kpi=False)
        rec.add("llm_label_invalid", snap, len(g), g.f_label_invalid.sum(), to_kpi=False)
        rec.add("llm_evidence_missing", snap, len(g), g.f_evidence.sum(), to_kpi=False,
                note="danh sách kiểm tra tay: k7_evidence_review.csv")

    # --- ô KPI: khu x mốc, và toàn thành phố (ALL) ---
    d = df[df.has_area].assign(**{area_col: lambda x: x[area_col]})
    by_area = d.groupby(["snapshot", area_col]).agg(n_used=("ok", "sum"), n_total=("ok", "size")).reset_index()
    k_area = d[d.ok].groupby(["snapshot", area_col]).is_complaint.sum().rename("k").reset_index()
    by_area = by_area.merge(k_area, on=["snapshot", area_col], how="left").rename(columns={area_col: out_area})
    allc = d.groupby("snapshot").agg(n_used=("ok", "sum"), n_total=("ok", "size")).reset_index()
    k_all = d[d.ok].groupby("snapshot").is_complaint.sum().rename("k").reset_index()
    allc = allc.merge(k_all, on="snapshot", how="left").assign(**{out_area: "ALL"})
    res = pd.concat([by_area, allc], ignore_index=True).fillna({"k": 0})
    # trước QA: giữ cả review bị cờ llm_evidence_missing (nhãn LLM hợp lệ nhưng bằng chứng không khớp)
    pre = d[d.has_label & d.label_valid]
    keys = ["snapshot", area_col]
    b_area = pre.groupby(keys).agg(n_before_qa=("is_complaint", "size"), k_before=("is_complaint", "sum")).reset_index()
    b_all = pre.groupby("snapshot").agg(n_before_qa=("is_complaint", "size"), k_before=("is_complaint", "sum")).reset_index()
    before = pd.concat([b_area.rename(columns={area_col: out_area}), b_all.assign(**{out_area: "ALL"})],
                       ignore_index=True)
    res = res.merge(before, on=["snapshot", out_area], how="left").fillna({"n_before_qa": 0, "k_before": 0})
    res["n_excluded"] = res.n_total - res.n_used
    res["value"] = np.where(res.n_used >= min_n, 100 * res.k / res.n_used.where(res.n_used > 0), np.nan)
    res["value_before_qa"] = np.where(res.n_before_qa >= min_n,
                                      100 * res.k_before / res.n_before_qa.where(res.n_before_qa > 0), np.nan)
    res["period"] = res["snapshot"]

    cells = res[res[out_area] != "ALL"]
    for snap, g in cells.groupby("snapshot"):
        rec.add("kpi_cell_no_sample", snap, len(g), (g.n_used == 0).sum(), to_kpi=False)
        rec.add("kpi_cell_small_sample", snap, len(g), ((g.n_used > 0) & (g.n_used < min_n)).sum(),
                to_kpi=False, note=f"ngưỡng {min_n}")

    res.insert(0, "kpi_name", "k07_community_complaint_rate")
    res.insert(0, "kpi_id", K)
    res["unit"], res["currency"] = "%", ""
    out_dir.mkdir(parents=True, exist_ok=True)
    res[OUT_COLS + ["value_before_qa", "n_before_qa"]].to_csv(out_dir / "kpi_k7_community_complaint.csv", index=False, encoding="utf-8")
    rec.save_report(out_dir / "kpi_k7_report.csv")
    show = [c for c in ["id", "listing_id", "comment_clean", "evidence"] if c in df]
    df.loc[df.evidence_missing, show].drop_duplicates("id").to_csv(
        out_dir / "k7_evidence_review.csv", index=False, encoding="utf-8")
    print(f"ok K7: {len(res)} ô KPI")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(*args, handlabel="--handlabel" in sys.argv, skip_llm="--skip-llm" in sys.argv)