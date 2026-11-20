# Phân tích dữ liệu Inside Airbnb — Thành phố Porto (`DSE2049-C04-G06-porto`)

Dự án học phần **Lập trình xử lý dữ liệu (UET.DSE2049)** phân tích thị trường lưu trú ngắn hạn Airbnb tại Porto (tiền tệ `EUR`) qua 4 mốc dữ liệu (`2025-09-21`, `2026-03-26`, `2026-06-23`, `2026-09-19`) gồm các bước: kiểm tra chất lượng & gắn cờ dữ liệu (QA), tính 8 chỉ số KPI (`K01`–`K08`), phân tích review bằng Baseline NLP & LLM, đánh giá đối chiếu và trực quan hóa biểu đồ.

---

## 1. Yêu cầu Python & Cài đặt môi trường

Phiên bản Python đã kiểm thử của dự án được khai báo trong tệp [`.python-version`](.python-version): **`3.14.7`**.

### Các thư viện sử dụng ([`requirements.txt`](requirements.txt))

| Thư viện | Phiên bản | Tác dụng trong project |
|---|---:|---|
| [NumPy](https://numpy.org/) (`numpy`) | 2.3.3 | Hỗ trợ tính toán số học và thao tác mảng trong các bước QA/KPI. |
| [pandas](https://pandas.pydata.org/) (`pandas`) | 2.3.3 | Đọc, lọc, làm sạch, biến đổi và tổng hợp dữ liệu bảng (`listings`, `calendar`, `reviews`). |
| [PyArrow](https://arrow.apache.org/docs/python/) (`pyarrow`) | 26.0.0 | Tăng tốc đọc/ghi dữ liệu cho `pandas` khi xử lý `calendar` và file nén. |
| [PyYAML](https://pyyaml.org/) (`yaml`) | 6.0.3 | Đọc cấu hình pipeline từ tệp YAML (`configs/porto.yaml`). |
| [langdetect](https://pypi.org/project/langdetect/) (`langdetect`) | 1.0.9 | Nhận diện ngôn ngữ cho phương pháp Baseline NLP (`src/baseline.py`). |
| [Requests](https://requests.readthedocs.io/) (`requests`) | 2.34.2 | Gửi HTTP request tải mẫu (`src/download.py`) và gọi API LLM (`src/llm_label.py`). |
| [Matplotlib](https://matplotlib.org/) (`matplotlib`) | 3.11.1 | Vẽ biểu đồ trực quan hóa QA, KPI và phân tích LLM (`src/viz.py`). |
| [python-dotenv](https://pypi.org/project/python-dotenv/) (`dotenv`) | 1.2.4 | Nạp biến môi trường API key từ tệp `.env` (`src/llm_label.py`). |

### Các bước cài đặt

```bash
# 1. Tạo và kích hoạt môi trường ảo (khuyên dùng)
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# 2. Cài đặt toàn bộ thư viện
pip install -r requirements.txt
```

---

## 2. Cấu hình & Biến môi trường API Key

- Toàn bộ tham số thành phố, mốc dữ liệu, ngưỡng QA, tham số KPI và cấu hình LLM đều nằm trong [`configs/porto.yaml`](configs/porto.yaml).
- Tên biến môi trường cho bước gọi API LLM (khai báo mẫu tại [`.env.example`](.env.example)):

  ```env
  OPENAI_COMPAT_API_KEY=your_api_key_here
  ```

- Nếu muốn tự chạy lại bước gọi LLM, sao chép `.env.example` thành `.env` ở thư mục gốc và điền API key của bạn (tệp `.env` đã được đưa vào `.gitignore`).
- Kết quả gọi LLM của nhóm đã được lưu sẵn trong cache tại [`data/interim/k7_llm_cache.jsonl`](data/interim/k7_llm_cache.jsonl) và [`data/interim/k7_labels.csv`](data/interim/k7_labels.csv).

---

## 3. Lệnh chạy toàn bộ pipeline

Chạy từ thư mục gốc của repository:

```bash
python run_pipeline.py --config configs/porto.yaml
```

Các tùy chọn hỗ trợ:
- `--skip-llm`: Bỏ qua bước gọi LLM (`K07`) và `K08` lượt 2 khi máy không cài đặt API key.
- `--steps qa kpi reviews viz`: Chỉ chạy các giai đoạn mong muốn.
- `--with-filter`: Chạy thêm bước lọc dữ liệu thô từ `data/raw/` (`src/filter_all.py` → `src/check_counts.py`).
- `--dry-run`: In danh sách các lệnh sẽ thực thi mà không chạy thật.

---

## 4. Các tệp đầu ra cần kiểm tra sau khi chạy

### Báo cáo QA (`reports/`)
- [`reports/qa_report_host_locations.csv`](reports/qa_report_host_locations.csv)
- [`reports/qa_report_price_calendar.csv`](reports/qa_report_price_calendar.csv)
- [`reports/qa_report_property.csv`](reports/qa_report_property.csv)
- [`reports/qa_report_reviews.csv`](reports/qa_report_reviews.csv)
- [`reports/k05_checks.csv`](reports/k05_checks.csv) & [`reports/k05_sensitivity.csv`](reports/k05_sensitivity.csv)

### Dữ liệu KPI, Review & LLM (`data/processed/` & `data/interim/`)
- **KPI K01–K08**:
  - `data/processed/kpi_k1_area_share.csv`
  - `data/processed/kpi_k2_multi_host_share.csv`
  - `data/processed/kpi_k3_entire_home_share.csv`
  - `data/processed/kpi_k4_supply_change.csv`
  - `data/processed/kpi_k05_revenue_tax.csv`
  - `data/processed/kpi_k06_commercial_share.csv`
  - `data/processed/kpi_k07_community_complaint.csv` (cùng `kpi_k07_report.csv`, `k07_evidence_review.csv`)
  - `data/processed/kpi_k8_data_reliability.csv` (cùng `kpi_k08_report.csv`)
- **Review & NLP / LLM**:
  - `data/processed/reviews_valid.csv`
  - `data/processed/baseline_reviews.csv`
  - `data/interim/k7_llm_cache.jsonl` & `data/interim/k7_labels.csv`

### Biểu đồ trực quan (`figures/`)
- `figures/fig01_qa_flags_overview.png` — Tổng hợp tỷ lệ gắn cờ QA theo rule và snapshot
- `figures/fig02_k1_k2_k3_structure.png` — Cơ cấu thị trường K01–K03 theo khu phân tích (`A01`–`A08`)
- `figures/fig03_k4_supply_change.png` — Biến động nguồn cung ròng K04
- `figures/fig04_k5_revenue_tax.png` — Doanh thu ước tính và thuế du lịch tiềm năng K05
- `figures/fig05_k6_commercial_share.png` — Tỷ lệ thương mại hóa K06 và khoảng tin cậy 95%
- `figures/fig06_k7_community_llm.png` — Tỷ lệ phàn nàn cộng đồng K07, cảm xúc và khía cạnh từ LLM
- `figures/fig07_k8_data_reliability.png` — Các chỉ số độ tin cậy dữ liệu K08

---

## 5. Cấu trúc thư mục chính

```text
├── configs/porto.yaml          # Cấu hình toàn bộ pipeline cho Porto
├── data/
│   ├── raw/                    # Dữ liệu thô Inside Airbnb (gitignored)
│   ├── samples/                # Danh sách ID mẫu nhóm & từ điển baseline
│   ├── interim/                # Dữ liệu đã lọc theo mẫu nhóm & cache nhãn LLM
│   └── processed/              # Dữ liệu gắn cờ QA và các bảng KPI (K01–K08)
├── src/                        # Mã nguồn xử lý theo từng module (QA, KPI, Baseline, LLM, Evaluate, Viz)
├── reports/                    # Báo cáo QA, kiểm tra K05, đánh giá và báo cáo cuối kỳ
├── figures/                    # Biểu đồ PNG do src/viz.py tạo tự động
├── run_pipeline.py             # Lệnh chạy toàn bộ pipeline
├── run_audits.py               # Kiểm tra tính nhất quán các cột cờ QA
├── requirements.txt            # Danh sách thư viện Python cố định phiên bản
├── .python-version             # Phiên bản Python sử dụng (3.14.7)
├── .env.example                # Mẫu tên biến môi trường API key
└── AI_USAGE.md                 # Nhật ký sử dụng và kiểm chứng AI
```
