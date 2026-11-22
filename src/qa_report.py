#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qa_report.py - gộp mọi báo cáo QA thành MỘT tệp reports/qa_report.csv.

Đầu vào (do các bước trước sinh ra):
  data/interim/qa_parts/qa_report_*.csv     quy tắc QA của 4 mô-đun flag_*.py
  data/processed/kpi_k7_report.csv         quy tắc QA cho nhãn LLM (K07)
  data/processed/kpi_k8_report.csv         kiểm tra độ tin cậy dữ liệu (K08)
  data/processed/kpi_*.csv                  KPI (để tính tác động trước/sau QA)
  data/processed/*_flags_<snap>.csv.gz, reviews_flagged_<snap>.csv.gz, reviews_valid.csv

Đầu ra: reports/qa_report.csv, mỗi dòng thuộc một trong 3 phần (cột `section`):
  rule        tên quy tắc -> điều kiện -> lý do -> hành động, số dòng bị gắn cờ
  rows        tác động lên số dòng: trước QA, sau QA, số dòng bị loại
  kpi_impact  giá trị KPI cấp thành phố trước và sau QA

Chạy: python src/qa_report.py --config configs/porto.yaml
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent

COLS = ["section", "module", "rule", "kind", "table", "snapshot", "condition", "reason", "action",
        "rows_total", "rows_flagged", "flagged_pct",
        "kpi_id", "kpi_name", "unit", "n_before_qa", "n_after_qa",
        "value_before_qa", "value_after_qa", "delta", "note"]

RULE_PARTS = [  # (module, tệp, thư mục: "parts" | "processed")
    ("host_locations", "qa_report_host_locations.csv", "parts"),
    ("price_calendar", "qa_report_price_calendar.csv", "parts"),
    ("property", "qa_report_property.csv", "parts"),
    ("reviews", "qa_report_reviews.csv", "parts"),
    ("k07_llm", "kpi_k7_report.csv", "processed"),
    ("k08_reliability", "kpi_k8_report.csv", "processed"),
]

NO_DROP = "QA chỉ gắn cờ, không loại dòng nào khỏi KPI -> trước = sau"


def read(path):
    p = Path(path)
    return pd.read_csv(p, low_memory=False) if p.exists() else None


def find(proc, prefix, snap):
    for ext in (".csv.gz", ".csv"):
        p = proc / f"{prefix}_{snap}{ext}"
        if p.exists():
            return p
    return None


# --------------------------------------------------------------------------- 1. quy tắc
def rule_section(parts_dir, proc):
    out = []
    for module, fname, where in RULE_PARTS:
        df = read((parts_dir if where == "parts" else proc) / fname)
        if df is None:
            print(f"[qa_report] bỏ qua (chưa có): {fname}")
            continue
        df = df.assign(section="rule", module=module)
        tot = pd.to_numeric(df["rows_total"], errors="coerce")
        flg = pd.to_numeric(df["rows_flagged"], errors="coerce")
        df["flagged_pct"] = (100 * flg / tot.where(tot > 0)).round(2)
        out.append(df)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS)


# --------------------------------------------------------------------------- 2. số dòng
def rows_section(cfg, proc, snaps):
    out = []
    valid = read(proc / "reviews_valid.csv")
    k05 = read(proc / "kpi_k5_revenue_tax.csv")
    for s in snaps:
        p = find(proc, "listings_price_flags", s)
        if p is not None and k05 is not None:
            n = len(pd.read_csv(p, usecols=["id"]))
            row = k05[(k05.snapshot == s) & (k05.neighbourhood_cleansed == "ALL")].head(1)
            used = int(row.n_used.iloc[0]) if len(row) else np.nan
            out.append(dict(table="listings", snapshot=s, rule="kpi_k05_used_listings",
                            n_before_qa=n, n_after_qa=used,
                            note="K05: loại listing thiếu giá hoặc giá <= 0; các listing khác chỉ gắn cờ"))
        p = find(proc, "reviews_flagged", s)
        if p is not None and valid is not None:
            n = len(pd.read_csv(p, usecols=["id"]))
            used = int((valid["snapshot"].astype(str) == s).sum())
            out.append(dict(table="reviews", snapshot=s, rule="reviews_valid",
                            n_before_qa=n, n_after_qa=used,
                            note="review bị loại khỏi reviews_valid.csv (trùng, mồ côi, rỗng/quá ngắn, tự động...)"))
    df = pd.DataFrame(out)
    if df.empty:
        return pd.DataFrame(columns=COLS)
    df["section"], df["module"], df["kind"] = "rows", "impact", "impact"
    df["rows_total"] = df["n_before_qa"]
    df["rows_flagged"] = df["n_before_qa"] - df["n_after_qa"]
    df["flagged_pct"] = (100 * df["rows_flagged"] / df["rows_total"]).round(2)
    df["action"] = "Loại khỏi tính toán"
    return df


# --------------------------------------------------------------------------- 3. KPI trước/sau
def _city_rows(df):
    """Giá trị cấp thành phố: dùng dòng ALL nếu có, nếu không thì cộng tử/mẫu số các khu."""
    if "ALL" in set(df["neighbourhood_cleansed"].astype(str)):
        return df[df["neighbourhood_cleansed"].astype(str) == "ALL"].copy()
    if not {"numerator", "denominator"} <= set(df.columns):
        return pd.DataFrame()
    agg = {c: "sum" for c in ["numerator", "denominator", "n_used", "n_excluded",
                              "n_entire_before_qa", "n_total_before_qa"] if c in df}
    g = df.groupby(["kpi_id", "kpi_name", "snapshot", "unit"], as_index=False).agg(agg)
    g["value"] = (100 * g["numerator"] / g["denominator"].where(g["denominator"] > 0)).round(4)
    if {"n_entire_before_qa", "n_total_before_qa"} <= set(g.columns):
        g["value_before_qa"] = (100 * g["n_entire_before_qa"] / g["n_total_before_qa"]).round(4)
        g["n_before_qa"] = g["n_total_before_qa"]
    return g


def kpi_section(proc):
    out = []
    for path in sorted(proc.glob("kpi_*.csv")):
        if path.name.endswith("_report.csv") or "k8_data_reliability" in path.name:
            continue  # báo cáo quy tắc / K08 đã nằm trong phần rule
        df = read(path)
        if df is None or df.empty or "value" not in df:
            continue
        if path.name.startswith("kpi_k1_"):   # tỷ trọng theo khu: cộng lại luôn = 100%, giữ từng khu
            city = df.copy()
        else:
            city = _city_rows(df)
        if city.empty:
            continue
        city["n_after_qa"] = city["n_used"]
        city["value_after_qa"] = city["value"]
        if "n_before_qa" not in city:
            city["n_before_qa"] = city["n_used"] + city["n_excluded"]
        if "value_before_qa" in city:
            city["note"] = "giá trị trước QA tính lại trên cả các dòng bị QA loại"
        else:
            no_drop = city["n_excluded"].fillna(0).eq(0)
            city["value_before_qa"] = np.where(no_drop, city["value"], np.nan)
            city["note"] = np.where(no_drop, NO_DROP,
                                    "dòng bị loại thiếu dữ liệu đầu vào (vd. thiếu giá) nên không tính được trước QA")
        if path.name.startswith("kpi_k1_"):
            city["rule"] = city["neighbourhood_cleansed"].astype(str)   # ghi khu vào cột rule
        out.append(city)

        # độ nhạy K05: QA giữ listing price_outlier; nếu loại thì doanh thu đổi bao nhiêu
        if path.name.startswith("kpi_k5_"):
            rev = city[city.kpi_name == "estimated_revenue"].set_index("snapshot")
            outl = city[city.kpi_name == "price_outlier_revenue"].set_index("snapshot")
            outl_n = city[city.kpi_name == "price_outlier_listings"].set_index("snapshot")
            both = rev.index.intersection(outl.index)
            if len(both):
                s = rev.loc[both].copy()
                s["kpi_name"] = "estimated_revenue_if_drop_price_outlier"
                s["n_before_qa"] = rev.loc[both, "n_used"]
                if len(both.intersection(outl_n.index)) == len(both):
                    s["n_after_qa"] = rev.loc[both, "n_used"] - outl_n.loc[both, "value"]
                s["value_before_qa"] = rev.loc[both, "value"]
                s["value_after_qa"] = (rev.loc[both, "value"] - outl.loc[both, "value"]).round(2)
                s["note"] = "độ nhạy: QA chỉ gắn cờ price_outlier (giữ lại); dòng này cho thấy KPI nếu loại chúng"
                out.append(s.reset_index())
    if not out:
        return pd.DataFrame(columns=COLS)
    df = pd.concat(out, ignore_index=True)
    df["section"], df["module"], df["kind"], df["table"] = "kpi_impact", "impact", "impact", "kpi"
    df["kpi_id"] = df["kpi_id"].astype(str).str.upper()
    df["delta"] = (pd.to_numeric(df["value_after_qa"], errors="coerce")
                   - pd.to_numeric(df["value_before_qa"], errors="coerce")).round(4)
    return df


def main():
    ap = argparse.ArgumentParser(description="Gộp báo cáo QA thành reports/qa_report.csv")
    ap.add_argument("--config", default="configs/porto.yaml")
    ap.add_argument("--out", default="reports/qa_report.csv")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(ROOT / args.config if not Path(args.config).exists() else args.config,
                              encoding="utf-8"))
    snaps = [str(s) for s in cfg["snapshots"]]
    proc = ROOT / cfg["paths"]["processed"]
    parts_dir = ROOT / cfg["paths"]["interim"] / "qa_parts"

    rep = pd.concat([rule_section(parts_dir, proc), rows_section(cfg, proc, snaps), kpi_section(proc)],
                    ignore_index=True)
    snap_pairs = {f"{a}->{b}" for a, b in zip(snaps, snaps[1:])}
    valid_snaps = set(snaps) | snap_pairs
    rep = rep[rep["snapshot"].astype(str).isin(valid_snaps)]
    for c in COLS:
        if c not in rep:
            rep[c] = np.nan
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    rep[COLS].to_csv(out, index=False, encoding="utf-8-sig")
    print(f"ok qa_report: {len(rep)} dòng -> {out.relative_to(ROOT)}  "
          + ", ".join(f"{k}={v}" for k, v in rep["section"].value_counts().items()))


if __name__ == "__main__":
    main()
