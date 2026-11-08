import argparse
from pathlib import Path

import pandas as pd
import yaml


def rise_streak(wide, tol=0.0):
    up = wide.diff(axis=1).gt(tol)
    streak = up.astype(int)
    cols = list(wide.columns)
    for prev, cur in zip(cols, cols[1:]):
        streak[cur] = (streak[prev] + 1).where(up[cur], 0)
    return streak


def to_long(frames):
    out = None
    for name, wide in frames.items():
        m = (wide.rename_axis(index="area", columns="snapshot")
                 .reset_index().melt(id_vars="area", var_name="snapshot", value_name=name))
        out = m if out is None else out.merge(m, on=["area", "snapshot"])
    return out.sort_values(["area", "snapshot"]).reset_index(drop=True)


def kpi_k1(by_snap, rising_streak, overload_pct=None):
    counts = (pd.DataFrame({s: d["area"].value_counts() for s, d in by_snap.items()}).fillna(0).astype(int))
    share = counts / counts.sum() * 100
    delta = share.diff(axis=1)
    streak = rise_streak(share)
    city = pd.DataFrame(counts.sum().to_dict(), index=counts.index)
    out = to_long({"n_listings_area": counts, "n_listings_city": city,
                   "share_pct": share, "share_delta_pp": delta, "rising_streak": streak})
    out["flag_rising_share"] = out["rising_streak"] >= rising_streak
    if overload_pct is not None:
        out["flag_overload"] = out["share_pct"] > overload_pct
    out["share_pct"] = out["share_pct"].round(4)
    out["share_delta_pp"] = out["share_delta_pp"].round(4)
    return out


def kpi_k2(by_snap, min_listings, scope, tolerance_pp):
    key = ["host_id"] if scope == "city" else ["area", "host_id"]
    n_all, n_multi = {}, {}
    for snap, d in by_snap.items():
        listings_of_host = d.groupby(key)["id"].transform("size")
        d = d.assign(multi=listings_of_host >= min_listings)
        g = d.groupby("area").agg(n_listings=("id", "size"), n_multi=("multi", "sum"))
        n_all[snap], n_multi[snap] = g["n_listings"], g["n_multi"]
    n_all = pd.DataFrame(n_all).fillna(0).astype(int)
    n_multi = pd.DataFrame(n_multi).reindex(n_all.index).fillna(0).astype(int)

    share = n_multi / n_all.where(n_all > 0) * 100
    delta = share.diff(axis=1)
    streak = rise_streak(share, tolerance_pp)
    out = to_long({"n_listings": n_all, "n_multi_host_listings": n_multi,
                   "multi_host_share_pct": share, "share_delta_pp": delta, "rising_streak": streak})
    out["flag_rising"] = out["share_delta_pp"] > tolerance_pp
    out["multi_host_share_pct"] = out["multi_host_share_pct"].round(4)
    out["share_delta_pp"] = out["share_delta_pp"].round(4)
    return out