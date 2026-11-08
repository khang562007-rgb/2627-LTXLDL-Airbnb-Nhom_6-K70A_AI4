from pathlib import Path

import pandas as pd

from src.audit_flags import audit_table, sample_flagged


ROOT = Path(__file__).resolve().parent
SNAPSHOT = "2026-09-19"

before_path = ROOT / "data" / "interim" / f"listings_{SNAPSHOT}.csv.gz"
flags_path = ROOT / "data" / "processed" / f"listings_property_flags_{SNAPSHOT}.csv.gz"

# Bảng listing trước khi gắn cờ
before = pd.read_csv(before_path, dtype={"id": str}, low_memory=False)

# File cờ QA do bước QA property tạo ra
flags = pd.read_csv(flags_path, dtype={"id": str}, low_memory=False)

# Ghép các cột cờ vào dữ liệu gốc để có bảng sau QA
after = before.merge(
    flags,
    on="id",
    how="left",
    validate="one_to_one",
)

# audit_flags.py hiện nhận diện tên cột bắt đầu bằng "flag_".
# Các cột cờ trong file của project chưa có tiền tố này, nên đổi tên trước khi kiểm tra.
flag_columns = [col for col in flags.columns if col != "id"]
after = after.rename(columns={col: f"flag_{col}" for col in flag_columns})

# Kiểm tra số dòng và các cột gốc; in thống kê cho từng cột cờ
report = audit_table(
    before=before,
    after=after,
    table="listings",
    snap=SNAPSHOT,
    expected_rows=len(before),
)

print("\nTổng hợp cờ QA:")
print(report.to_string(index=False))

# Lấy mẫu cho một cờ để kiểm tra bằng mắt
flag_to_review = "flag_capacity_outlier"

if flag_to_review in after.columns:
    flagged_sample, clean_sample = sample_flagged(
        df=after,
        flag=flag_to_review,
        cols=["id", "accommodates", flag_to_review],
        n=8,
    )

    print(f"\nMẫu bị cờ: {flag_to_review}")
    print(flagged_sample.to_string(index=False))

    print(f"\nMẫu không bị cờ: {flag_to_review}")
    print(clean_sample.to_string(index=False))
else:
    print(f"\nKhông tìm thấy cột {flag_to_review}; hãy kiểm tra tên cột cờ.")