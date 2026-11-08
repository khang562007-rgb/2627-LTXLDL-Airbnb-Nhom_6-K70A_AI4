import argparse
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
UNKNOWN_AREA = "(không rõ)"


def load_listings(path, area_col):
    need = {"id", "host_id", area_col}
    df = pd.read_csv(path, usecols=lambda c: c in need, dtype=str)
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} thiếu cột: {sorted(missing)}")
    df = df.drop_duplicates("id").rename(columns={area_col: "area"})
    df["area"] = df["area"].fillna(UNKNOWN_AREA)
    return df


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
    counts = (pd.DataFrame({s: d["area"].value_counts() for s, d in by_snap.items()})
                .fillna(0).astype(int))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/porto.yaml")
    ap.add_argument("--area-col", help="Cột xác định khu (mặc định kpi.area_col, rồi neighbourhood_cleansed)")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(ROOT / args.config, encoding="utf-8"))
    kc = cfg.get("kpi", {})

    area_col = args.area_col or kc.get("area_col", "neighbourhood_cleansed")
    pattern = kc.get("listings_file", cfg["listings"]["raw_file"])
    scope = kc.get("host_scope", "city")
    if scope not in ("city", "area"):
        raise ValueError("kpi.host_scope phải là 'city' hoặc 'area'")

    by_snap = {}
    for snap in sorted(cfg["snapshots"]):
        path = ROOT / pattern.format(snap=snap)
        if not path.exists():
            raise FileNotFoundError(f"Thiếu {path} - cần tải dữ liệu thô trước (python src/download.py)")
        by_snap[snap] = load_listings(path, area_col)
        n_no_host = int(by_snap[snap]["host_id"].isna().sum())
        if n_no_host:
            print(f"[CANH BAO] {snap}: {n_no_host} listing thiếu host_id, không tính là host đa listing")

    k1 = kpi_k1(by_snap, kc.get("k1", {}).get("rising_streak", 2),
                kc.get("k1", {}).get("overload_share_pct"))
    k2 = kpi_k2(by_snap, kc.get("multi_host_min", 3), scope,
                kc.get("k2", {}).get("tolerance_pp", 0))

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    k1.to_csv(reports / "kpi_k1_concentration.csv", index=False, encoding="utf-8-sig")
    k2.to_csv(reports / "kpi_k2_multi_host.csv", index=False, encoding="utf-8-sig")

    last = max(by_snap)
    print(f"\n== K1 tại mốc {last} (top 10 thị phần) ==")
    print(k1[k1["snapshot"] == last].nlargest(10, "share_pct")
            [["area", "n_listings_area", "share_pct", "share_delta_pp", "rising_streak", "flag_rising_share"]]
            .to_string(index=False))
    print(f"\n== K2 tại mốc {last} (top 10 tỷ lệ) ==")
    print(k2[k2["snapshot"] == last].nlargest(10, "multi_host_share_pct")
            [["area", "n_listings", "multi_host_share_pct", "share_delta_pp", "flag_rising"]]
            .to_string(index=False))


if __name__ == "__main__":
    main()