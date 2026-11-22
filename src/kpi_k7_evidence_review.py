#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Xuất bằng chứng review cho KPI K7 (k7_evidence_review.csv) và tạo mẫu gán nhãn tay (--handlabel).

Chạy từ gốc repo:
    # 1. Tạo mẫu gán nhãn tay (data/interim/k7_handlabel_sample.csv):
    python src/kpi_k7_evidence_review.py configs/porto.yaml data/processed/reviews_valid.csv data/processed --handlabel

    # 2. Xuất danh sách ca bằng chứng phàn nàn cộng đồng (k7_evidence_review.csv):
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


def norm(s) -> str:
    return " ".join(str(s).lower().split())


def evidence_ok(ev, comment) -> bool:
    parts = [p for p in str(ev).split(" | ") if p.strip()]
    return bool(parts) and all(norm(p) in norm(comment) for p in parts)


def blind_area_stratified_sample(df: pd.DataFrame, area_col: str, n: int, seed: int) -> pd.DataFrame:
    """Lấy mẫu mù phân tầng theo khu vực (không dùng nhãn dự đoán của LLM để tránh thiên lệch)."""
    if len(df) <= n:
        return df.sample(frac=1, random_state=seed).reset_index(drop=True)

    valid_area = df[df[area_col].notna()].copy()
    areas = sorted(valid_area[area_col].astype(str).unique())
    if not areas:
        return df.sample(n=n, random_state=seed).reset_index(drop=True)

    per = max(1, n // len(areas))
    parts = []
    used_ids: set[str] = set()
    for area in areas:
        g = valid_area[valid_area[area_col].astype(str) == area]
        take = min(len(g), per)
        if take > 0:
            s = g.sample(n=take, random_state=seed)
            parts.append(s)
            used_ids.update(s["id"])

    out = pd.concat(parts, ignore_index=True) if parts else df.iloc[0:0].copy()
    need = n - len(out)
    if need > 0:
        rem = df[~df["id"].isin(used_ids)]
        if not rem.empty:
            out = pd.concat([out, rem.sample(n=min(need, len(rem)), random_state=seed)], ignore_index=True)

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
    area_col = cfg["kpi"]["area_col"]
    areas_cfg = cfg["kpi"]["columns"]["areas"]
    areas_path = resolve_path(root, areas_cfg["path"])

    reviews = load_unique_reviews(reviews_path)
    areas = pd.read_csv(
        areas_path,
        usecols=areas_cfg["cols"],
        dtype={"listing_id": str},
    ).drop_duplicates(subset=["listing_id"], keep="first")
    reviews = reviews.merge(areas, on="listing_id", how="left")

    llm = load_valid_llm_labels(labels_path, community_aspects)
    if llm is not None and not llm.empty:
        pool = reviews.merge(llm[["id"]], on="id", how="inner")
        print(f"[handlabel] Tìm thấy {len(pool)} review trùng với {labels_path.name}.")
    else:
        pool = reviews
        print("[handlabel] Không thấy k7_labels.csv hợp lệ; lấy mẫu trực tiếp từ reviews_valid.csv.")

    sampled = blind_area_stratified_sample(pool, area_col=area_col, n=n_sample, seed=seed)

    base_cols = [c for c in ["snapshot", "id", "listing_id", area_col, "date", "comment_clean"] if c in sampled.columns]
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
    n_evidence: int | None = None,
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
    bad = pd.Series(
        [
            not evidence_ok(ev, comment)
            for ev, comment in zip(merged["evidence"].fillna(""), merged["comment_clean"].fillna(""))
        ],
        index=merged.index,
    )
    ev_pool = merged[(merged["llm_comm"] == 1) & bad].copy()

    if n_evidence is not None and len(ev_pool) > n_evidence:
        ev_out = ev_pool.sample(n=n_evidence, random_state=seed)
    else:
        ev_out = ev_pool

    ev_out = ev_out[["id", "listing_id", "comment_clean", "evidence"]].drop_duplicates("id").reset_index(drop=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "k7_evidence_review.csv"
    ev_out.to_csv(out_path, index=False, encoding="utf-8")
    print(f"[evidence] Đã xuất {len(ev_out)} ca bằng chứng thiếu/không khớp (llm_evidence_missing) -> {out_path}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Tạo mẫu gán nhãn tay và xuất bằng chứng review KPI K7")
    ap.add_argument("config", help="Đường dẫn configs/porto.yaml")
    ap.add_argument("reviews_csv", help="Đường dẫn data/processed/reviews_valid.csv")
    ap.add_argument("out_dir", help="Thư mục đầu ra (vd: data/processed)")
    ap.add_argument("--handlabel", action="store_true", help="Sinh file mẫu gán nhãn tay k7_handlabel_sample.csv")
    ap.add_argument("--n-evidence", type=int, default=None, help="Giới hạn số ca xuất vào k7_evidence_review.csv (mặc định xuất hết)")
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