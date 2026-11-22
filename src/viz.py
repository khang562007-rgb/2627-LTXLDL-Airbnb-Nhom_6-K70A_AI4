"""Trực quan hóa kết quả QA, KPI (K01-K08) và nhãn LLM cho dự án Inside Airbnb.
Chạy từ gốc repo:
    python src/viz.py [--config configs/porto.yaml] [--out figures]
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
})


def load_csv(path):
    p = Path(path)
    if not p.exists():
        print(f"[SKIP] Không tìm thấy {p}")
        return None
    return pd.read_csv(p)


def get_areas(df):
    vals = df["neighbourhood_cleansed"].dropna().astype(str).unique()
    return sorted(v for v in vals if v != "ALL")


def save_fig(fig, out_dir, filename):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out_path}")


def area_pivot(df, snaps, val_col="value", areas=None):
    areas = areas or get_areas(df)
    sub = df[df["neighbourhood_cleansed"].isin(areas)]
    piv = sub.pivot_table(index="neighbourhood_cleansed", columns="snapshot", values=val_col, aggfunc="first")
    return piv.reindex(index=areas, columns=[s for s in snaps if s in piv.columns])


def plot_grouped_bars(ax, piv, title, ylabel, fmt="{:.1f}", show_legend=True, headroom=0.18):
    x = np.arange(len(piv.index))
    cols = list(piv.columns)
    w = 0.8 / max(len(cols), 1)
    for i, col in enumerate(cols):
        vals = piv[col].fillna(0).values
        offset = (i - (len(cols) - 1) / 2) * w
        bars = ax.bar(x + offset, vals, width=w, label=col, color=PALETTE[i % len(PALETTE)], alpha=0.9)
        if len(cols) <= 2:
            for b, v in zip(bars, vals):
                if v != 0:
                    ax.text(b.get_x() + b.get_width() / 2, b.get_height(), fmt.format(v),
                            ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(piv.index)
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel(ylabel)
    vmax = np.nanmax(piv.values) if piv.size else 0
    vmin = np.nanmin(piv.values) if piv.size else 0
    if vmax > 0 and vmin >= 0:
        ax.set_ylim(0, vmax * (1.0 + headroom))
    if show_legend:
        ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")


def fig_qa_overview(reports_dir, snaps, out_dir):
    modules = {"host_locations": "host", "price_calendar": "price", "property": "property", "reviews": "reviews"}
    rep = load_csv(reports_dir / "qa_report.csv")   # tệp QA gộp (src/qa_report.py)
    parts = []
    if rep is not None and not rep.empty:
        rep = rep[(rep["section"] == "rule") & rep["module"].isin(modules)]
        for module, prefix in modules.items():
            df = rep[rep["module"] == module]
            if not df.empty:
                d = df[df["snapshot"].isin(snaps)].copy()
                d["rate_pct"] = np.where(d["rows_total"] > 0, 100.0 * d["rows_flagged"] / d["rows_total"], 0.0)
                d["label"] = prefix + ": " + d["rule"].astype(str)
                parts.append(d[["label", "snapshot", "rate_pct"]])
    if not parts:
        return

    all_df = pd.concat(parts, ignore_index=True)
    piv = all_df.pivot_table(index="label", columns="snapshot", values="rate_pct", aggfunc="max")
    piv = piv.reindex(columns=[s for s in snaps if s in piv.columns]).fillna(0)
    # Chỉ giữ các rule có ít nhất 1 mốc > 0% để biểu đồ gọn, dễ đọc
    active = piv[piv.max(axis=1) > 0].sort_values(piv.columns[-1], ascending=True)
    if active.empty:
        active = piv

    fig, ax = plt.subplots(figsize=(10, max(5, 0.36 * len(active) + 1.5)))
    im = ax.imshow(active.values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=max(10.0, active.values.max()))
    ax.set_xticks(np.arange(len(active.columns)))
    ax.set_xticklabels(active.columns)
    ax.set_yticks(np.arange(len(active.index)))
    ax.set_yticklabels(active.index, fontsize=9)
    for i in range(active.shape[0]):
        for j in range(active.shape[1]):
            v = active.values[i, j]
            color = "white" if v > active.values.max() * 0.55 else "black"
            txt = "<0.1%" if 0 < v < 0.05 else f"{v:.1f}%"
            ax.text(j, i, txt, ha="center", va="center", color=color, fontsize=8)
    ax.grid(False)
    ax.set_title("QA Data Quality: % Rows Flagged by Rule & Snapshot", fontweight="bold", pad=12)
    fig.colorbar(im, ax=ax, label="% Flagged", shrink=0.8)
    save_fig(fig, out_dir, "fig01_qa_flags_overview.png")


def fig_k1_k2_k3(proc_dir, snaps, out_dir):
    k1 = load_csv(proc_dir / "kpi_k1_area_share.csv")
    k2 = load_csv(proc_dir / "kpi_k2_multi_host_share.csv")
    k3 = load_csv(proc_dir / "kpi_k3_entire_home_share.csv")
    if all(x is None for x in (k1, k2, k3)):
        return

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4))
    specs = [
        (axes[0], k1, "K01: Area Listing Share (%)", "Share (%)"),
        (axes[1], k2, "K02: Multi-Host Listing Share (%)", "Share (%)"),
        (axes[2], k3, "K03: Entire Home/Apt Share (%)", "Share (%)"),
    ]
    legend_handles, legend_labels = None, None
    for ax, df, title, ylabel in specs:
        if df is None:
            ax.set_visible(False)
            continue
        piv = area_pivot(df, snaps)
        plot_grouped_bars(ax, piv, title, ylabel, show_legend=False, headroom=0.14)
        if legend_handles is None:
            legend_handles, legend_labels = ax.get_legend_handles_labels()
        all_row = df[df["neighbourhood_cleansed"] == "ALL"]
        if not all_row.empty:
            latest = all_row.sort_values("snapshot").iloc[-1]["value"]
            line = ax.axhline(latest, color="black", linestyle="--", linewidth=1.1, label=f"ALL ({latest:.1f}%)")
            ax.legend(handles=[line], frameon=False, fontsize=8.5, loc="upper right")
    if legend_handles:
        fig.legend(legend_handles, legend_labels, loc="upper center", ncol=len(legend_labels),
                   frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, 0.96))
    fig.suptitle("Market Structure Across Analysis Areas", fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.91])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fig02_k1_k2_k3_structure.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out_path}")


def fig_k4_supply_change(proc_dir, snaps, out_dir):
    k4 = load_csv(proc_dir / "kpi_k4_supply_change.csv")
    if k4 is None or k4.empty:
        return
    areas = get_areas(k4)
    sub = k4[k4["neighbourhood_cleansed"].isin(areas)]
    piv = area_pivot(sub, snaps, areas=areas)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    plot_grouped_bars(ax1, piv, "K04: Net Supply Change (%) by Area", "Net Change (%)", show_legend=False)
    ax1.axhline(0, color="black", linewidth=0.9)
    ax1.legend(frameon=False, fontsize=8.5, loc="lower right")

    latest_snap = sub["snapshot"].max()
    lat = sub[sub["snapshot"] == latest_snap].set_index("neighbourhood_cleansed").reindex(areas).fillna(0)
    x = np.arange(len(areas))
    ax2.bar(x - 0.18, lat["n_new"], width=0.35, label="New listings", color="#2ca02c", alpha=0.9)
    ax2.bar(x + 0.18, -lat["n_gone"], width=0.35, label="Delisted / Gone", color="#d62728", alpha=0.9)
    ax2.axhline(0, color="black", linewidth=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(areas)
    ax2.set_title(f"K04: Listings Entry vs Exit ({latest_snap})", fontweight="bold")
    ax2.set_ylabel("Number of Listings")
    ax2.legend(frameon=False, fontsize=9, loc="lower right")
    save_fig(fig, out_dir, "fig03_k4_supply_change.png")


def fig_k5_revenue_tax(proc_dir, snaps, out_dir, currency="EUR"):
    k5 = load_csv(proc_dir / "kpi_k5_revenue_tax.csv")
    if k5 is None or k5.empty:
        return
    areas = get_areas(k5)
    latest = max(s for s in snaps if s in set(k5["snapshot"]))
    sub = k5[(k5["snapshot"] == latest) & (k5["neighbourhood_cleansed"].isin(areas))]

    rev_short = sub[sub["kpi_name"] == "estimated_revenue_short_stay"].set_index("neighbourhood_cleansed")["value"].reindex(areas).fillna(0) / 1e6
    rev_long = sub[sub["kpi_name"] == "estimated_revenue_long_stay"].set_index("neighbourhood_cleansed")["value"].reindex(areas).fillna(0) / 1e6
    tax_all = sub[sub["kpi_name"] == "tourist_tax_potential_all"].set_index("neighbourhood_cleansed")["value"].reindex(areas).fillna(0) / 1e3
    tax_lic = sub[sub["kpi_name"] == "tourist_tax_potential_licensed"].set_index("neighbourhood_cleansed")["value"].reindex(areas).fillna(0) / 1e3

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    x = np.arange(len(areas))
    ax1.bar(x, rev_short, label="Short-stay revenue", color="#1f77b4")
    ax1.bar(x, rev_long, bottom=rev_short, label="Long-stay revenue", color="#ff7f0e")
    ax1.set_xticks(x)
    ax1.set_xticklabels(areas)
    ax1.set_ylim(0, max((rev_short + rev_long).max(), 0.1) * 1.15)
    ax1.set_title(f"K05: Estimated Annual Revenue by Area ({latest})", fontweight="bold")
    ax1.set_ylabel(f"Million {currency}")
    ax1.legend(frameon=False, loc="upper right")

    ax2.bar(x - 0.18, tax_all, width=0.35, label="Potential tax (All)", color="#9467bd")
    ax2.bar(x + 0.18, tax_lic, width=0.35, label="Potential tax (Licensed)", color="#2ca02c")
    ax2.set_xticks(x)
    ax2.set_xticklabels(areas)
    ax2.set_ylim(0, max(tax_all.max(), 1.0) * 1.15)
    ax2.set_title(f"K05: Tourist Tax Potential by Area ({latest})", fontweight="bold")
    ax2.set_ylabel(f"Thousand {currency}")
    ax2.legend(frameon=False, loc="upper right")
    save_fig(fig, out_dir, "fig04_k5_revenue_tax.png")


def fig_k6_commercial_share(proc_dir, snaps, out_dir, avail_cap=240):
    k6 = load_csv(proc_dir / "kpi_k6_commercial_share.csv")
    if k6 is None or k6.empty:
        return
    areas = get_areas(k6)
    latest = max(s for s in snaps if s in set(k6["snapshot"]))

    comm = k6[k6["kpi_name"] == "commercial_share"]
    piv_comm = area_pivot(comm, snaps, areas=areas)

    sub_lat = k6[(k6["snapshot"] == latest) & (k6["neighbourhood_cleansed"].isin(areas))]
    val = sub_lat[sub_lat["kpi_name"] == "commercial_share"].set_index("neighbourhood_cleansed")["value"].reindex(areas).fillna(0)
    err = sub_lat[sub_lat["kpi_name"] == "commercial_share_margin95"].set_index("neighbourhood_cleansed")["value"].reindex(areas).fillna(0)
    avail = sub_lat[sub_lat["kpi_name"] == "availability_share"].set_index("neighbourhood_cleansed")["value"].reindex(areas).fillna(0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.2))
    plot_grouped_bars(ax1, piv_comm, "K06: Commercial Share (%) Across Snapshots", "Commercial Share (%)",
                      show_legend=True, headroom=0.22)

    x = np.arange(len(areas))
    ax2.bar(x - 0.18, val, yerr=err, capsize=3, width=0.35, label="Commercial share (±95% CI)", color="#d62728", alpha=0.85)
    ax2.bar(x + 0.18, avail, width=0.35, label=f"Listings with avail_365 > {avail_cap} (%)", color="#1f77b4", alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels(areas)
    ax2.set_ylim(0, max((val + err).max(), avail.max(), 1.0) * 1.18)
    ax2.set_title(f"K06: Commercialization vs High-Availability Share ({latest})", fontweight="bold")
    ax2.set_ylabel("Percentage (%)")
    ax2.legend(frameon=False, fontsize=8.5, loc="upper right")
    save_fig(fig, out_dir, "fig05_k6_commercial_share.png")


def fig_k7_llm_community(proc_dir, interim_dir, snaps, out_dir):
    k7 = load_csv(proc_dir / "kpi_k7_community_complaint.csv")
    labels = load_csv(interim_dir / "k7_labels.csv")
    if k7 is None and labels is None:
        return

    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    if k7 is not None and not k7.empty:
        areas = get_areas(k7)
        latest = max(s for s in snaps if s in set(k7["snapshot"]))
        sub = k7[(k7["snapshot"] == latest) & (k7["neighbourhood_cleansed"].isin(areas))].set_index("neighbourhood_cleansed").reindex(areas)
        vals = sub["value"].fillna(0)
        bars = axes[0].bar(areas, vals, color="#d62728", alpha=0.85)
        for b, v in zip(bars, vals):
            axes[0].text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.1f}%", ha="center", va="bottom", fontsize=8)
        all_v = k7[(k7["snapshot"] == latest) & (k7["neighbourhood_cleansed"] == "ALL")]["value"]
        if not all_v.empty:
            axes[0].axhline(all_v.iloc[0], color="black", linestyle="--", linewidth=1, label=f"ALL ({all_v.iloc[0]:.2f}%)")
            axes[0].legend(frameon=False, loc="upper right")
        axes[0].set_ylim(0, max(vals.max(), 1.0) * 1.18)
        axes[0].set_title(f"K07: Community Complaint Rate ({latest})", fontweight="bold")
        axes[0].set_ylabel("Complaint Rate (%)")
    else:
        axes[0].set_visible(False)

    if labels is not None and not labels.empty:
        valid_lbl = labels[labels["label_valid"] == True]
        sent_counts = valid_lbl["sentiment"].value_counts()
        colors = {"positive": "#2ca02c", "mixed": "#ff7f0e", "negative": "#d62728"}
        axes[1].bar(sent_counts.index, sent_counts.values, color=[colors.get(s, "#1f77b4") for s in sent_counts.index])
        for i, v in enumerate(sent_counts.values):
            axes[1].text(i, v, str(v), ha="center", va="bottom", fontsize=9)
        axes[1].set_ylim(0, max(sent_counts.values.max(), 1) * 1.12)
        axes[1].set_title(f"LLM Sentiment Distribution (n={len(valid_lbl)})", fontweight="bold")
        axes[1].set_ylabel("Number of Reviews")

        def count_aspects(col):
            s = valid_lbl[col].dropna().astype(str).str.split(";").explode()
            return s[s != ""].value_counts()

        praise = count_aspects("aspects_praised")
        crit = count_aspects("aspects_criticized")
        asp_df = pd.DataFrame({"praise": praise, "criticism": crit}).fillna(0)
        asp_df = asp_df.loc[(asp_df["praise"] + asp_df["criticism"]).sort_values(ascending=True).index]
        y = np.arange(len(asp_df))
        axes[2].barh(y, asp_df["praise"], color="#2ca02c", alpha=0.85, label="Praise")
        axes[2].barh(y, -asp_df["criticism"], color="#d62728", alpha=0.85, label="Criticism")
        axes[2].axvline(0, color="black", linewidth=0.8)
        axes[2].set_yticks(y)
        axes[2].set_yticklabels(asp_df.index, fontsize=9)
        axes[2].set_title("LLM Aspect Polarity Breakdown", fontweight="bold")
        axes[2].set_xlabel("← Criticism | Praise →")
        axes[2].legend(frameon=False, fontsize=8, loc="lower right")
    else:
        axes[1].set_visible(False)
        axes[2].set_visible(False)

    save_fig(fig, out_dir, "fig06_k7_community_llm.png")


def fig_k8_reliability(proc_dir, snaps, out_dir):
    k8 = load_csv(proc_dir / "kpi_k8_data_reliability.csv")
    if k8 is None or k8.empty:
        return
    keep = [
        "k08_review_dup_content",
        "k08_review_date_invalid",
        "k08_comment_markup",
        "k08_exclude_from_llm_sample",
        "k08_no_reviews",
        "k08_listing_sample_coverage",
        "k08_kpi_excluded_share",
    ]
    display_names = {
        "k08_listing_sample_coverage": "listings_without_llm_sample",
    }
    sub = k8[k8["kpi_name"].isin(keep)].copy()
    sub["short_name"] = sub["kpi_name"].map(
        lambda x: display_names.get(x, x.replace("k08_", "", 1))
    )
    piv = sub.pivot_table(index="short_name", columns="snapshot", values="value", aggfunc="first")
    piv = piv.reindex(columns=[s for s in snaps if s in piv.columns]).fillna(0)

    fig, ax = plt.subplots(figsize=(10, 5))
    y = np.arange(len(piv.index))
    cols = list(piv.columns)
    h = 0.8 / max(len(cols), 1)
    for i, col in enumerate(cols):
        offset = (i - (len(cols) - 1) / 2) * h
        ax.barh(y + offset, piv[col].values, height=h, label=col, color=PALETTE[i % len(PALETTE)], alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(piv.index)
    ax.set_xlabel("Flagged / Excluded / Uncovered Rate (%)")
    ax.set_title("K08: Review & Sample Reliability Indicators Across Snapshots", fontweight="bold")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    save_fig(fig, out_dir, "fig07_k8_data_reliability.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/porto.yaml")
    ap.add_argument("--out", default="figures")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load(open(root / args.config, encoding="utf-8"))
    snaps = [str(s) for s in cfg["snapshots"]]
    currency = cfg.get("currency", "EUR")
    avail_cap = int(cfg.get("availability_commercial", 240))
    proc_dir = root / cfg["paths"]["processed"]
    interim_dir = root / cfg["paths"]["interim"]
    reports_dir = root / "reports"
    out_dir = root / args.out

    fig_qa_overview(reports_dir, snaps, out_dir)
    fig_k1_k2_k3(proc_dir, snaps, out_dir)
    fig_k4_supply_change(proc_dir, snaps, out_dir)
    fig_k5_revenue_tax(proc_dir, snaps, out_dir, currency=currency)
    fig_k6_commercial_share(proc_dir, snaps, out_dir, avail_cap=avail_cap)
    fig_k7_llm_community(proc_dir, interim_dir, snaps, out_dir)
    fig_k8_reliability(proc_dir, snaps, out_dir)


if __name__ == "__main__":
    main()
