"""Phần dùng chung cho K7 và K8."""
import pandas as pd

OUT_COLS = ["kpi_id", "kpi_name", "snapshot", "neighbourhood_cleansed", "period",
            "value", "unit", "currency", "n_used", "n_excluded"]


def usecols(*groups):
    return list(dict.fromkeys(c for g in groups for c in g))   # bỏ trùng, giữ thứ tự


def pick_sample(valid, seed, per_listing=1):
    """Mẫu LLM: mỗi listing chọn ngẫu nhiên `per_listing` review (theo seed). Trả về tập id review."""
    u = valid.drop_duplicates("id")[["id", "listing_id"]]
    s = u.sample(frac=1, random_state=seed).groupby("listing_id").head(per_listing)
    return set(s["id"])


def pct(n_flag, n_used):
    return round(n_flag / n_used * 100, 4) if n_used else None


def kpi_row(kpi_id, name, snap, n_used, n_flag, area="ALL", period=None, value=None, unit="%"):
    return {"kpi_id": kpi_id, "kpi_name": name, "snapshot": snap,
            "neighbourhood_cleansed": area, "period": period or snap,
            "value": pct(n_flag, n_used) if value is None else value,
            "unit": unit, "currency": "", "n_used": int(n_used), "n_excluded": int(n_flag)}


class Recorder:
    """Ghi rule theo bảng rules của một KPI: dòng báo cáo, và (tuỳ chọn) dòng KPI."""

    def __init__(self, kpi_id, rules):
        self.kpi_id, self.rules = kpi_id, rules
        self.kpi_rows, self.report = [], []

    def add(self, rule, snap, n_used, n_flag, note="", to_kpi=True):
        kind, table, cond, why, act = self.rules[rule]      # rule không có trong bảng thì báo lỗi ngay
        if to_kpi:
            self.kpi_rows.append(kpi_row(self.kpi_id, f"{self.kpi_id}_{rule}", snap, n_used, n_flag))
        self.report.append(dict(rule=rule, kind=kind, table=table, snapshot=snap,
                                condition=cond, reason=why, action=act,
                                rows_total=int(n_used), rows_flagged=int(n_flag), note=note))

    def save_report(self, path):
        pd.DataFrame(self.report).to_csv(path, index=False, encoding="utf-8-sig")