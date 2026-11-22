"""Đánh giá mô hình Baseline NLP và LLM trên tập nhãn tay (và đối chiếu chéo Baseline vs LLM).

Chạy từ gốc repo:
    python src/evaluate.py [--config configs/porto.yaml]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

BASELINE_COMMUNITY_ASPECTS = {"độ ồn", "an toàn", "noise", "safety", "neighbours", "area_hygiene"}


def parse_baseline_aspects(val):
    if pd.isna(val) or not str(val).strip():
        return set()
    s = str(val).strip()
    if s.startswith("["):
        try:
            return {str(x).strip().lower() for x in json.loads(s) if str(x).strip()}
        except Exception:
            pass
    return {x.strip().lower() for x in s.replace(";", ",").split(",") if x.strip()}


def parse_llm_aspects(val):
    if pd.isna(val) or not str(val).strip():
        return set()
    return {x.strip().lower() for x in str(val).split(";") if x.strip()}


def to_bool_label(series):
    truthy = {"1", "true", "yes", "y", "x", "có", "co"}
    falsy = {"0", "false", "no", "n", "không", "khong"}

    def conv(v):
        if pd.isna(v):
            return np.nan
        s = str(v).strip().lower()
        if s in truthy:
            return 1
        if s in falsy:
            return 0
        return np.nan

    return series.map(conv)


def macro_f1(y_true, y_pred):
    labels = sorted(set(y_true) | set(y_pred))
    f1s = []
    for lb in labels:
        tp = sum((yt == lb and yp == lb) for yt, yp in zip(y_true, y_pred))
        fp = sum((yt != lb and yp == lb) for yt, yp in zip(y_true, y_pred))
        fn = sum((yt == lb and yp != lb) for yt, yp in zip(y_true, y_pred))
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * p * r / (p + r) if (p + r) else 0.0)
    return round(float(np.mean(f1s)), 4) if f1s else np.nan


def binary_metrics(y_true, y_pred):
    tp = sum((yt == 1 and yp == 1) for yt, yp in zip(y_true, y_pred))
    fp = sum((yt == 0 and yp == 1) for yt, yp in zip(y_true, y_pred))
    fn = sum((yt == 1 and yp == 0) for yt, yp in zip(y_true, y_pred))
    acc = sum(yt == yp for yt, yp in zip(y_true, y_pred)) / len(y_true) if len(y_true) else np.nan
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "accuracy": round(acc, 4),
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f1, 4),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
    }


def load_baseline(path):
    p = Path(path)
    if not p.exists():
        return None
    df = pd.read_csv(p, dtype={"review_id": str})
    df = df.rename(columns={"review_id": "id"}).drop_duplicates("id")
    df["base_lang"] = df["language"].fillna("").astype(str).str.strip().str.lower()
    df["base_sent"] = df["sentiment"].fillna("").astype(str).str.strip().str.lower()
    neg = df["aspects_negative"].map(parse_baseline_aspects)
    df["base_comm"] = neg.map(lambda s: int(bool(s & BASELINE_COMMUNITY_ASPECTS)))
    return df[["id", "base_lang", "base_sent", "base_comm"]]


def load_llm(path, community_aspects):
    p = Path(path)
    if not p.exists():
        return None
    df = pd.read_csv(p, dtype={"id": str})
    df = df[df["label_valid"] == True].drop_duplicates("id").copy()
    df["llm_lang"] = df["language"].fillna("").astype(str).str.strip().str.lower()
    df["llm_sent"] = df["sentiment"].fillna("").astype(str).str.strip().str.lower()
    crit = df["aspects_criticized"].map(parse_llm_aspects)
    df["llm_comm"] = crit.map(lambda s: int(bool(s & community_aspects)))
    return df[["id", "llm_lang", "llm_sent", "llm_comm"]]


def eval_against_handlabel(hl, base, llm, out_dir):
    df = hl.copy()
    df["id"] = df["id"].astype(str)
    df["hand_lang"] = df["hand_language"].fillna("").astype(str).str.strip().str.lower()
    df["hand_sent"] = df["hand_sentiment"].fillna("").astype(str).str.strip().str.lower()
    df["hand_comm"] = to_bool_label(df["hand_community_complaint"])

    if base is not None:
        df = df.merge(base, on="id", how="left")
    if llm is not None:
        df = df.merge(llm, on="id", how="left")

    rows = []
    models = []
    if base is not None:
        models.append(("baseline", "base_lang", "base_sent", "base_comm"))
    if llm is not None:
        models.append(("llm", "llm_lang", "llm_sent", "llm_comm"))

    for model, col_l, col_s, col_c in models:
        sub_l = df[(df["hand_lang"] != "") & (df[col_l].fillna("") != "")]
        if not sub_l.empty:
            acc = (sub_l["hand_lang"] == sub_l[col_l]).mean()
            rows.append(dict(model=model, task="language", n=len(sub_l), accuracy=round(float(acc), 4),
                             macro_f1=np.nan, precision=np.nan, recall=np.nan, f1=np.nan))

        sub_s = df[(df["hand_sent"] != "") & (df[col_s].fillna("") != "")]
        if not sub_s.empty:
            acc = (sub_s["hand_sent"] == sub_s[col_s]).mean()
            mf1 = macro_f1(sub_s["hand_sent"].tolist(), sub_s[col_s].tolist())
            rows.append(dict(model=model, task="sentiment", n=len(sub_s), accuracy=round(float(acc), 4),
                             macro_f1=mf1, precision=np.nan, recall=np.nan, f1=np.nan))

        sub_c = df[df["hand_comm"].notna() & df[col_c].notna()]
        if not sub_c.empty:
            m = binary_metrics(sub_c["hand_comm"].astype(int).tolist(), sub_c[col_c].astype(int).tolist())
            rows.append(dict(model=model, task="community_complaint", n=len(sub_c),
                             accuracy=m["accuracy"], macro_f1=np.nan,
                             precision=m["precision"], recall=m["recall"], f1=m["f1"]))

    summary = pd.DataFrame(rows)
    summary.to_csv(out_dir / "eval_summary.csv", index=False, encoding="utf-8-sig")
    print("\n=== Đánh giá so với nhãn tay ===")
    print(summary.to_string(index=False))

    llm_mismatch = pd.Series(False, index=df.index)
    if llm is not None:
        llm_mismatch |= (df["hand_lang"] != "") & df["llm_lang"].notna() & (df["hand_lang"] != df["llm_lang"])
        llm_mismatch |= (df["hand_sent"] != "") & df["llm_sent"].notna() & (df["hand_sent"] != df["llm_sent"])
        llm_mismatch |= df["hand_comm"].notna() & df["llm_comm"].notna() & (df["hand_comm"] != df["llm_comm"])
    base_mismatch = pd.Series(False, index=df.index)
    if base is not None:
        base_mismatch |= (df["hand_lang"] != "") & df["base_lang"].notna() & (df["hand_lang"] != df["base_lang"])
        base_mismatch |= (df["hand_sent"] != "") & df["base_sent"].notna() & (df["hand_sent"] != df["base_sent"])
        base_mismatch |= df["hand_comm"].notna() & df["base_comm"].notna() & (df["hand_comm"] != df["base_comm"])
    df["llm_mismatch"] = llm_mismatch
    df["base_mismatch"] = base_mismatch
    df.loc[llm_mismatch | base_mismatch].to_csv(out_dir / "eval_mismatches.csv", index=False, encoding="utf-8-sig")


def eval_cross_agreement(base, llm, out_dir, write_mismatches=True):
    if base is None or llm is None:
        print("[SKIP] Thiếu baseline_reviews.csv hoặc k7_labels.csv để đối chiếu chéo.")
        return
    m = base.merge(llm, on="id", how="inner")
    if m.empty:
        print(
            "[WARN] baseline_reviews.csv hiện chưa có review ID nào trùng với k7_labels.csv "
            "(cần chạy baseline.py trên data/processed/reviews_valid.csv)."
        )
        return

    rows = []
    sub_l = m[(m["base_lang"] != "") & (m["llm_lang"] != "")]
    if not sub_l.empty:
        rows.append(dict(comparison="baseline_vs_llm", task="language", n=len(sub_l),
                         agreement=round(float((sub_l["base_lang"] == sub_l["llm_lang"]).mean()), 4)))
    sub_s = m[(m["base_sent"] != "") & (m["llm_sent"] != "")]
    if not sub_s.empty:
        rows.append(dict(comparison="baseline_vs_llm", task="sentiment", n=len(sub_s),
                         agreement=round(float((sub_s["base_sent"] == sub_s["llm_sent"]).mean()), 4),
                         macro_f1_rel=macro_f1(sub_s["llm_sent"].tolist(), sub_s["base_sent"].tolist())))
    sub_c = m[m["base_comm"].notna() & m["llm_comm"].notna()]
    if not sub_c.empty:
        bm = binary_metrics(sub_c["llm_comm"].astype(int).tolist(), sub_c["base_comm"].astype(int).tolist())
        rows.append(dict(comparison="baseline_vs_llm", task="community_complaint", n=len(sub_c),
                         agreement=bm["accuracy"], f1_rel=bm["f1"]))

    res = pd.DataFrame(rows)
    res.to_csv(out_dir / "eval_baseline_vs_llm.csv", index=False, encoding="utf-8-sig")
    if write_mismatches:
        m[(m["base_sent"] != m["llm_sent"]) | (m["base_comm"] != m["llm_comm"])].to_csv(
            out_dir / "eval_mismatches.csv", index=False, encoding="utf-8-sig"
        )
    print("\n=== Đối chiếu chéo Baseline vs LLM ===")
    print(res.to_string(index=False))


def main():
    ap = argparse.ArgumentParser(description="Đánh giá Baseline và LLM")
    ap.add_argument("--config", default="configs/porto.yaml")
    ap.add_argument("--handlabel", default=None)
    ap.add_argument("--baseline", default="data/processed/baseline_reviews.csv")
    ap.add_argument("--llm", default=None)
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load(open(root / args.config, encoding="utf-8"))
    k7 = cfg["kpi"]["k7"]
    hl_path = root / (args.handlabel or k7["handlabel"]["path"])
    llm_path = root / (args.llm or k7["llm"]["labels_path"])
    base_path = root / args.baseline
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    community = {a.lower() for a in k7["aspects"]["community"]}
    base = load_baseline(base_path)
    llm = load_llm(llm_path, community)

    ran_handlabel = False
    if hl_path.exists():
        hl = pd.read_csv(hl_path, dtype={"id": str})
        has_filled = any(
            col in hl.columns and hl[col].dropna().astype(str).str.strip().ne("").any()
            for col in ("hand_language", "hand_sentiment", "hand_community_complaint")
        )
        if has_filled:
            eval_against_handlabel(hl, base, llm, out_dir)
            ran_handlabel = True
        else:
            print(f"[INFO] File {hl_path} tồn tại nhưng chưa điền nhãn tay (hand_*).")
    else:
        print(
            f"[INFO] Chưa có file nhãn tay {hl_path}. "
            "Tạo mẫu bằng: python src/kpi_k7_community_complaint.py configs/porto.yaml data/processed/reviews_valid.csv data/processed --handlabel"
        )

    eval_cross_agreement(base, llm, out_dir, write_mismatches=not ran_handlabel)


if __name__ == "__main__":
    main()