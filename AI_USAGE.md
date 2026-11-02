# AI_USAGE.md

## Công cụ đã dùng (vào việc gì)

AI hỗ trợ viết và rà soát `src/kpi_k3_k4.py`, bổ sung kiểm thử trong
`tests/test_kpi_k3_k4.py`, và ghi hướng dẫn tính K3/K4 vào hai CSV trong
`data/processed/`.

## Prompt then chốt (5-10): bước nào, vào tệp nào

Prompt: viết chương trình Python dễ giải thích bằng chú thích tiếng Việt cho
K3 (tỷ lệ `Entire home/apt`) và K4 (listing mới/biến mất), đọc snapshot và
đường dẫn từ `configs/porto.yaml`, không sửa dữ liệu đầu vào, xử lý khu rỗng,
kiểm tra nhãn `room_type`, tạo pytest với dữ liệu giả, và chỉ thao tác trên
`dung-branch`. Mốc dùng là các mốc trong config; `2026-09-19` thay cho
`2025-12-25`.

- Bước đọc dữ liệu, tính KPI và kiểm tra đầu ra: `src/kpi_k3_k4.py`.
- Các tình huống tính tay cho K3/K4: `tests/test_kpi_k3_k4.py`.
- Kết quả tính từ dữ liệu thật: `data/processed/kpi_k3_entire_home_share.csv`
  và `data/processed/kpi_k4_supply_change.csv`.

## AI sai ở đâu (ví dụ thật)

AI có thể giả định mọi snapshot đủ 1.000 dòng và vì vậy chờ K3 ALL bằng
87,5%. Kiểm tra thực tế cho thấy `2026-09-19` chỉ có 974 dòng, trong đó có
853 `Entire home/apt`; tỷ lệ tính đúng trên dữ liệu hiện có là 87,58%, không
phải 87,5%. AI cũng có thể phân loại sai listing mới/mất nếu so sánh theo
tên thay vì ID, hoặc gộp nhãn `room_type` khác chữ hoa/thường ngoài yêu cầu.

## Nhóm kiểm chứng thế nào

Chạy `pytest tests/test_kpi_k3_k4.py` để kiểm chứng các ca giả đã tính tay,
sau đó chạy `python src/kpi_k3_k4.py --config configs/porto.yaml`. Đối chiếu
snapshot, số dòng, `room_type`, khu và số ID trực tiếp với các tệp trong
`data/interim/`; kiểm tra K3 ALL, tổng theo khu, và K4 ALL ở từng cặp mốc.
Không diễn giải 87,58% ở `2026-09-19` thành 87,5%: mẫu snapshot này thiếu
26 dòng so với 1.000 dòng của ba mốc trước.
