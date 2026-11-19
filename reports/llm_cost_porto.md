# Ước lượng chi phí LLM cho toàn bộ review Porto

**Kết quả tại mốc 19/09/2026.** Có **1.177.598 review hợp lệ, phân biệt theo ID** trong tệp thô Porto. Với một lần phân tích trên mỗi review, chi phí ước lượng cho toàn bộ tập bằng **1.854,485039 × chi phí thực tế của 635 review mẫu**. Nhánh hiện tại có mã cache nhưng chưa có log token, hóa đơn hoặc tổng chi phí gắn với 635 ID. Vì vậy giá trị tiền tệ cuối cùng còn phụ thuộc số đo của lần chạy mẫu. [Mã cache](../src/llm_cache.py)

## Quy mô cần xử lý

Phạm vi là toàn bộ `../2026-09-19/reviews.csv.gz` của bộ dữ liệu Porto tại mốc mới nhất trong cấu hình. Tính một lần tại mốc này tránh cộng lại lịch sử review qua bốn lần chụp. Quy tắc đủ điều kiện lấy từ `flag_text` với ngưỡng 3 ký tự cho văn bản sau làm sạch. Ngoài quy tắc văn bản, phép ước lượng yêu cầu ID có giá trị và chỉ tính một lần cho mỗi ID có nội dung đạt. [Cấu hình](../configs/porto.yaml) · [Hàm làm sạch](../src/qa.py)

| Bước đếm ở mốc 19/09/2026 | Số lượng | Đơn vị |
|---|---:|---|
| Đọc tệp reviews thô của toàn Porto | 1.183.326 | Dòng |
| Loại nội dung rỗng hoặc dưới 3 ký tự sau làm sạch | 5.388 | Dòng bị loại |
| Còn lại sau kiểm tra nội dung | 1.177.938 | Dòng |
| Thiếu ID trong các dòng còn lại | 0 | Dòng bị loại |
| Lượt xuất hiện dư của ID trong các dòng còn lại | 340 | Dòng bị loại |
| **N – quy mô dùng để ngoại suy** | **1.177.598** | **ID review phân biệt** |

Ở cùng mốc, báo cáo QA ghi **4.932** dòng đủ điều kiện trong tập ID được giao cho nhóm. Con số **635** là cỡ mẫu chạy LLM theo yêu cầu bài tập. Đây là hai tập con phục vụ hai mục đích khác nhau. [Báo cáo QA của nhóm](qa_report_reviews.csv)

## Từ lần chạy mẫu đến dự toán

Gọi `C635` là tổng chi phí của lần phân tích đủ 635 review phân biệt, `I635` và `O635` lần lượt là tổng token đầu vào và đầu ra của lần chạy đó. Đối chiếu các request với ID mẫu và tính cả lần gọi lại có phát sinh phí. Khi một request chứa nhiều review, tính chi phí request đúng một lần.

| Đại lượng | Phép tính | Đơn vị |
|---|---|---|
| Hệ số ngoại suy | `F = 1.177.598 / 635 = 1.854,485039…` | Lần |
| Chi phí trung bình mỗi review mẫu | `C635 / 635` | Đồng tiền của hóa đơn/review |
| **Chi phí toàn Porto** | **`C635 × F`** | **Cùng đồng tiền với C635** |
| Token toàn Porto | Đầu vào ≈ `I635 × F`. Đầu ra ≈ `O635 × F`. | Token theo từng loại |

**Nếu log chỉ có số token**, lấy đúng model, gói giá và đơn giá áp dụng lúc chạy mẫu. Khi dịch vụ tính hai loại token với giá trên một triệu token, dùng `C635 = (I635 × giá_vào + O635 × giá_ra) / 1.000.000`. Nếu hóa đơn tách token cache hoặc token suy luận thành mức giá riêng, tính từng nhóm token tính phí một lần theo đơn giá tương ứng rồi cộng lại. Giữ đầy đủ độ chính xác đến khi làm tròn số tiền cuối.

Phép ngoại suy giả định mẫu có độ dài review và đầu ra gần với toàn tập, đồng thời giữ cách gom lô, prompt, model và điều kiện giá. Khi mẫu có cache hit hoặc dùng hạn mức miễn phí, cần ghi rõ chi phí đang trình bày là tiền thực trả theo điều kiện đó hay chi phí tính theo token cho một lượt chạy mới. Với mức giá tính theo token, chi phí biến động theo lượng token trung bình trên mỗi review.

## Tái lập số review hợp lệ

Chạy đoạn Python dưới đây từ gốc dự án, trong môi trường đã cài các thư viện của dự án. Đoạn mã đọc theo khối, giữ ID dạng chuỗi và dùng cùng hàm làm sạch với bước QA. Kết quả dự kiến là `(1183326, 5388, 0, 340, 1177598)`, lần lượt tương ứng với số dòng thô, dòng ngắn, dòng đủ dài thiếu ID, lượt trùng ID và ID hợp lệ.

```python
from pathlib import Path

import pandas as pd
import yaml

from src.qa import flag_text

config = yaml.safe_load(Path("configs/porto.yaml").read_text(encoding="utf-8"))
snapshot = "2026-09-19"
source = Path(config["paths"]["raw"]) / snapshot / "reviews.csv.gz"
valid_ids = set()
rows = short = missing_id = eligible_with_id = 0
for chunk in pd.read_csv(source, usecols=["id", "comments"],
                         dtype={"id": "string"}, chunksize=30_000):
    flagged = flag_text(chunk, config["qa"]["reviews"])
    excluded = flagged["exclude_from_llm_sample"]
    eligible = flagged.loc[~excluded, "id"]
    rows += len(chunk)
    short += int(excluded.sum())
    missing_id += int(eligible.isna().sum())
    ids = eligible.dropna()
    eligible_with_id += len(ids)
    valid_ids.update(ids)

duplicates = eligible_with_id - len(valid_ids)
print(rows, short, missing_id, duplicates, len(valid_ids))
```
