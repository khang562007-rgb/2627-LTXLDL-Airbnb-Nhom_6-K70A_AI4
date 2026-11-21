"""
Kiểm tra chất lượng các cột cờ (flag_*) do các thành viên viết.

Cách dùng (ví dụ):
    from audit_flags import audit_table, check_collisions, sample_flagged

    # before: bảng đã lọc, chưa gắn cờ. after: bảng sau khi gắn cờ
    rep = audit_table(before, after, table="listings", snap="2025-09-21", expected_rows=1000)
    print(rep)

Không sửa dữ liệu, chỉ đọc và báo cáo.
"""
import numpy as np
import pandas as pd

LOW_PCT = 0.0      # cờ không bắt dòng nào
HIGH_PCT = 50.0    # cờ bắt quá nửa số dòng


def flag_cols(df):
    return [c for c in df.columns if c.startswith("flag_")]


def audit_table(before, after, table, snap, expected_rows=None):
    """Trả về bảng tóm tắt từng cờ + in các lỗi cấu trúc."""
    problems = []

    # 1) Số dòng không đổi
    if len(after) != len(before):
        problems.append(f"số dòng đổi: {len(before)} -> {len(after)}")
    if expected_rows is not None and len(after) != expected_rows:
        problems.append(f"số dòng {len(after)} khác kỳ vọng {expected_rows}")

    # 2) Cột gốc không bị sửa (so sánh theo vị trí dòng, bỏ qua cột mới)
    orig = [c for c in before.columns if c in after.columns]
    if len(after) == len(before):
        b = before[orig].reset_index(drop=True)
        a = after[orig].reset_index(drop=True)
        changed = [c for c in orig if not b[c].equals(a[c])]
        if changed:
            problems.append(f"cột gốc bị thay đổi: {changed}")
    missing = [c for c in before.columns if c not in after.columns]
    if missing:
        problems.append(f"cột gốc bị mất: {missing}")

    # 3) Từng cột cờ
    rows = []
    for c in flag_cols(after):
        s = after[c]
        n_null = int(s.isna().sum())
        is_bool = s.dtype == bool
        n_true = int(s.fillna(False).astype(bool).sum())
        pct = round(100 * n_true / max(len(s), 1), 2)
        note = []
        if not is_bool:
            note.append(f"dtype={s.dtype} (nên là bool)")
        if n_null:
            note.append(f"{n_null} ô trống")
        if n_true == 0:
            note.append("0 dòng bị cờ: điều kiện sai hay không có lỗi?")
        if pct >= HIGH_PCT:
            note.append(f">= {HIGH_PCT}% dòng bị cờ: nghi điều kiện sai")
        rows.append({"snap": snap, "table": table, "flag": c,
                     "n_flagged": n_true, "pct": pct, "ghi_chu": "; ".join(note)})

    for p in problems:
        print(f"[LOI] {snap} {table}: {p}")
    if not problems:
        print(f"[OK] {snap} {table}: số dòng và cột gốc nguyên vẹn")
    return pd.DataFrame(rows)


def check_collisions(before, outputs):
    """outputs: dict tên_người -> bảng sau khi chạy hàm cờ của người đó (từ cùng một `before`).
    Báo nếu hai người tạo cùng tên cột cờ (khi ghép sẽ ghi đè nhau)."""
    seen = {}
    for who, df in outputs.items():
        for c in df.columns:
            if c not in before.columns:
                seen.setdefault(c, []).append(who)
    dup = {c: w for c, w in seen.items() if len(w) > 1}
    if dup:
        for c, w in dup.items():
            print(f"[LOI] cột '{c}' do nhiều người cùng tạo: {w}")
    else:
        print("[OK] không có cột cờ nào bị trùng tên giữa các người")
    return dup


def sample_flagged(df, flag, cols, n=8, seed=42):
    """Lấy mẫu n dòng bị cờ và n dòng không bị cờ để đọc bằng mắt."""
    t = df[df[flag].fillna(False).astype(bool)]
    f = df[~df[flag].fillna(False).astype(bool)]
    return (t.sample(min(n, len(t)), random_state=seed)[cols],
            f.sample(min(n, len(f)), random_state=seed)[cols])