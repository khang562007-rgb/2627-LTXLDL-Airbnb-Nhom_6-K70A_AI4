# Phân tích thị trường Airbnb - Porto

Bài tập lớn môn Lập trình xử lý dữ liệu (UET.DSE2049).

## Cài đặt

Yêu cầu Python theo phiên bản trong `.python-version`. Từ thư mục gốc của project, tạo môi trường và cài các thư viện:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Nếu PowerShell không cho phép kích hoạt môi trường, có thể gọi trực tiếp `.\.venv\Scripts\python.exe` thay cho `python`.

## Dữ liệu đầu vào

Project đọc dữ liệu thô từ thư mục `DATA` nằm cạnh thư mục project. Thư mục này cần có các snapshot `listings.csv.gz`, `calendar.csv.gz`, `reviews.csv.gz` tương ứng với các ngày trong `configs/porto.yaml`.

Các danh sách ID của nhóm nằm trong `data/samples/`. Nếu file chưa có, bước lọc sẽ tải từ các đường dẫn được cấu hình trong YAML và lưu bản sao tại chỗ.

## Cách chạy

Chạy toàn bộ pipeline từ thư mục gốc của project:

```powershell
python run_pipeline.py
```

Pipeline chạy theo thứ tự:

1. `src/filter_all.py` lọc dữ liệu theo ID nhóm và lưu dữ liệu đã lọc, chưa gắn cờ vào `data/interim/`.
2. `src/qa.py` kiểm tra reviews và tạo cờ review.
3. `src/flag_property_cross.py` tạo cờ chất lượng listings và đối chiếu calendar.

Kết quả đã gắn cờ nằm trong `data/processed/`; báo cáo QA nằm trong `reports/`. Có thể chạy riêng từng bước theo thứ tự trên nếu cần.

Kiểm tra số dòng và ID sau khi chạy pipeline:

```powershell
python check_counts.py
```

## Biến môi trường

Pipeline hiện tại không cần API key. Chỉ thêm biến môi trường khi triển khai một chức năng bên ngoài cần xác thực.
