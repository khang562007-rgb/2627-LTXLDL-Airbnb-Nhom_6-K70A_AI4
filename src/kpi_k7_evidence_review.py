#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Xuất bằng chứng review cho KPI K7 (k07_evidence_review.csv) và tạo mẫu gán nhãn tay (--handlabel).

Chạy từ gốc repo:
    # 1. Tạo mẫu gán nhãn tay (data/interim/k7_handlabel_sample.csv):
    python src/kpi_k7_evidence_review.py configs/porto.yaml data/processed/reviews_valid.csv data/processed --handlabel

    # 2. Xuất danh sách ca bằng chứng phàn nàn cộng đồng (k07_evidence_review.csv):
    python src/kpi_k7_evidence_review.py configs/porto.yaml data/processed/reviews_valid.csv data/processed
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml


def parse_llm_aspects(val) -> set[str]:
    if pd.isna(val) or not str(val).strip():
        return set()
    return {x.strip().lower() for x in str(val).split(";") if x.strip()}


def resolve_path(root: Path, raw_path: str | Path) -> Path:
    p = Path(raw_path)
    return p if p.is_absolute() else (root / p)


def load_unique_reviews(reviews_path: Path) -> pd.DataFrame:
    df = pd.read_csv(reviews_path, dtype={"id": str, "listing_id": str})
    if "id" not in df.columns or "comment_clean" not in df.columns:
        raise ValueError(f"Thiếu cột bắt buộc ('id', 'comment_clean') trong {reviews_path}")
    return df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)


def load_valid_llm_labels(labels_path: Path, community_aspects: set[str]) -> pd.DataFrame | None:
    if not labels_path.exists():
        return None
    df = pd.read_csv(labels_path, dtype={"id": str})
    if "label_valid" in df.columns:
        df = df[df["label_valid"] == True].copy()
    df = df.drop_duplicates(subset=["id"], keep="first")
    df["llm_comm"] = df["aspects_criticized"].map(
        lambda v: int(bool(parse_llm_aspects(v) & community_aspects))
    )
    return df


def stratified_sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Lấy mẫu phân tầng ưu tiên giữ đủ các ca negative và community_complaint."""
    if len(df) <= n:
        return df.sample(frac=1, random_state=seed).reset_index(drop=True)

    if "sentiment" not in df.columns or "llm_comm" not in df.columns:
        return df.sample(n=n, random_state=seed).reset_index(drop=True)

    parts = []
    used_ids: set[str] = set()

    # 1. Giữ toàn bộ ca negative (thường rất ít)
    neg = df[df["sentiment"].astype(str).str.lower() == "negative"]
    parts.append(neg)
    used_ids.update(neg["id"])

    # 2. Giữ toàn bộ (hoặc tối đa 40%) ca có phàn nàn cộng đồng
    rem = df[~df["id"].isin(used_ids)]
    comm = rem[rem["llm_comm"] == 1]
    take_comm = min(len(comm), max(1, int(n * 0.35)))
    if take_comm > 0:
        sampled_comm = comm.sample(n=take_comm, random_state=seed)
        parts.append(sampled_comm)
        used_ids.update(sampled_comm["id"])

    # 3. Chia đều phần còn lại giữa mixed và positive (nếu có)
    need = n - len(used_ids)
    if need > 0:
        rem = df[~df["id"].isin(used_ids)]
        mixed = rem[rem["sentiment"].astype(str).str.lower() == "mixed"]
        take_mixed = min(len(mixed), need // 3)
        if take_mixed > 0:
            sampled_mixed = mixed.sample(n=take_mixed, random_state=seed)
            parts.append(sampled_mixed)
            used_ids.update(sampled_mixed["id"])

    # 4. Bù đủ n bằng các review còn lại
    need = n - len(used_ids)
    if need > 0:
        rem = df[~df["id"].isin(used_ids)]
        parts.append(rem.sample(n=min(need, len(rem)), random_state=seed))

    out = pd.concat(parts, ignore_index=True)
    return out.sample(frac=1, random_state=seed).reset_index(drop=True)


def generate_handlabel_sample(
    cfg: dict,
    root: Path,
    reviews_path: Path,
) -> Path:
    k7 = cfg["kpi"]["k7"]
    seed = int(cfg.get("seed", 42))
    n_sample = int(k7["handlabel"].get("n", 150))
    out_path = resolve_path(root, k7["handlabel"]["path"])
    labels_path = resolve_path(root, k7["llm"]["labels_path"])
    community_aspects = {a.lower() for a in k7["aspects"]["community"]}

    reviews = load_unique_reviews(reviews_path)
    llm = load_valid_llm_labels(labels_path, community_aspects)

    if llm is not None and not llm.empty:
        pool = reviews.merge(
            llm[["id", "sentiment", "llm_comm"]],
            on="id",
            how="inner",
        )
        print(f"[handlabel] Tìm thấy {len(pool)} review trùng với {labels_path.name}.")
    else:
        pool = reviews
        print("[handlabel] Không thấy k7_labels.csv hợp lệ; lấy mẫu trực tiếp từ reviews_valid.csv.")

    sampled = stratified_sample(pool, n=n_sample, seed=seed)

    base_cols = [c for c in ["snapshot", "id", "listing_id", "date", "comment_clean"] if c in sampled.columns]
    out_df = sampled[base_cols].copy()
    out_df["hand_language"] = ""
    out_df["hand_sentiment"] = ""
    out_df["hand_community_complaint"] = ""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[handlabel] Đã xuất {len(out_df)} dòng mẫu gán nhãn tay -> {out_path}")
    return out_path


def generate_evidence_review(
    cfg: dict,
    root: Path,
    reviews_path: Path,
    out_dir: Path,
    n_evidence: int = 7,
) -> Path:
    k7 = cfg["kpi"]["k7"]
    seed = int(cfg.get("seed", 42))
    labels_path = resolve_path(root, k7["llm"]["labels_path"])
    community_aspects = {a.lower() for a in k7["aspects"]["community"]}

    reviews = load_unique_reviews(reviews_path)
    llm = load_valid_llm_labels(labels_path, community_aspects)
    if llm is None or llm.empty:
        raise FileNotFoundError(f"Cần có file nhãn LLM hợp lệ tại {labels_path} để xuất bằng chứng K7.")

    merged = reviews.merge(
        llm[["id", "llm_comm", "evidence"]],
        on="id",
        how="inner",
    )
    ev_pool = merged[
        (merged["llm_comm"] == 1)
        & (merged["evidence"].fillna("").astype(str).str.strip() != "")
    ].copy()

    if len(ev_pool) > n_evidence:
        ev_out = ev_pool.sample(n=n_evidence, random_state=seed)
    else:
        ev_out = ev_pool

    ev_out = ev_out[["id", "listing_id", "comment_clean", "evidence"]].reset_index(drop=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "k07_evidence_review.csv"
    ev_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[evidence] Đã xuất {len(ev_out)} ca bằng chứng phàn nàn cộng đồng -> {out_path}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Tạo mẫu gán nhãn tay và xuất bằng chứng review KPI K7")
    ap.add_argument("config", help="Đường dẫn configs/porto.yaml")
    ap.add_argument("reviews_csv", help="Đường dẫn data/processed/reviews_valid.csv")
    ap.add_argument("out_dir", help="Thư mục đầu ra (vd: data/processed)")
    ap.add_argument("--handlabel", action="store_true", help="Sinh file mẫu gán nhãn tay k7_handlabel_sample.csv")
    ap.add_argument("--n-evidence", type=int, default=7, help="Số ca bằng chứng xuất vào k07_evidence_review.csv")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    cfg_path = resolve_path(root, args.config)
    reviews_path = resolve_path(root, args.reviews_csv)
    out_dir = resolve_path(root, args.out_dir)

    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if args.handlabel:
        generate_handlabel_sample(cfg, root, reviews_path)
    else:
        generate_evidence_review(cfg, root, reviews_path, out_dir, n_evidence=args.n_evidence)


if __name__ == "__main__":
    main()