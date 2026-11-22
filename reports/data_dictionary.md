# Từ điển dữ liệu Airbnb Porto

Mã nhóm `DSE2049-C04-G06-porto`. Nguồn dữ liệu: **Inside Airbnb** (giấy phép **CC BY 4.0**). Bốn mốc chụp trong cấu hình là `2025-09-21`, `2026-03-26`, `2026-06-23` và `2026-09-19`. Mỗi tệp có hậu tố `<mốc>` chứa ngày chụp theo dạng `YYYY-MM-DD`. Khi phân tích CSV, đọc các mã định danh (`id`, `listing_id`, `host_id`, `reviewer_id`) dưới dạng chuỗi để giữ nguyên ID dài. [Cấu hình](../configs/porto.yaml)

## 1. Bảng đầu vào đã lọc (`data/interim/`)

| Tệp trong `data/interim/` | Một dòng biểu diễn | Khóa chính trong mốc | Phạm vi |
|---|---|---|---|
| `listings_<mốc>.csv.gz` | Một chỗ ở được quan sát | `id` | Các ID listing mẫu nhóm (1.000 ở 3 mốc đầu, 974 ở mốc 2026-09-19), đã ghép `analysis_area` (`A01`–`A08`). |
| `calendar_<mốc>.csv.gz` | Trạng thái lịch của chỗ ở trong một ngày | `(listing_id, date)` | Lọc theo ID listing mẫu, giữ 5 cột (365.000 dòng/mốc ở 3 mốc đầu, 355.510 dòng ở mốc cuối). |
| `reviews_<mốc>.csv.gz` | Một lượt đánh giá của khách | `id` | Lọc theo danh sách 5.000 ID review mẫu (5.000 ở 3 mốc đầu, 4.932 ở mốc 2026-09-19). |

Khi nối bảng, dùng cùng mốc và nối `calendar.listing_id` hoặc `reviews.listing_id` với `listings.id`. Dữ liệu thô toàn Porto (gitignored) nằm tại `data/raw/<mốc>/`. [Bước lọc dữ liệu](../src/filter_all.py)

### Listings

Tệp đã lọc có 80 cột ở mốc đầu và 91 cột ở ba mốc sau (do thay đổi schema từ Inside Airbnb; ngoài ra `host_since` trống hoàn toàn ở 3 mốc sau và `bathrooms` trống hoàn toàn ở mốc 2026-09-19).

| Cột | Kiểu | Đơn vị / miền giá trị | Ý nghĩa |
|---|---|---|---|
| `id`, `host_id` | Chuỗi ID | Mã | Định danh chỗ ở và chủ nhà. Một chủ nhà có thể sở hữu nhiều chỗ ở. |
| `name` | Chuỗi | Văn bản | Tên hiển thị của chỗ ở. |
| `last_scraped` | Ngày | `YYYY-MM-DD` | Ngày thu thập listing, làm mốc trên để đối chiếu ngày review. |
| `host_since` | Ngày (có thể thiếu) | `YYYY-MM-DD` | Ngày chủ nhà tham gia Airbnb (thiếu 100% ở 3 mốc 2026). |
| `analysis_area` | Chuỗi phân loại | `A01`–`A08` | Khu phân tích nhóm dùng để tính KPI, ghép từ `data/samples/porto-listings.csv`. |
| `neighbourhood_cleansed` | Chuỗi phân loại | Tên địa bàn | Tên khu vực hành chính chuẩn hóa trong dữ liệu nguồn. |
| `latitude`, `longitude` | Số thực | Độ vĩ, độ kinh | Tọa độ chỗ ở, dùng kiểm tra phạm vi Porto và độ trôi tọa độ giữa các mốc. |
| `room_type` | Chuỗi phân loại | `Entire home/apt`, `Private room`, `Shared room`, `Hotel room` | Hình thức cho thuê. K03 đếm khớp chính xác `Entire home/apt`. |
| `property_type` | Chuỗi phân loại | Loại hình | Loại bất động sản chi tiết (QA gắn cờ loại hiếm `< 0,5%`). |
| `accommodates` | Số nguyên | Khách | Sức chứa tối đa công bố (QA kiểm tra `1..16`). |
| `bedrooms`, `beds` | Số nguyên (có thể thiếu) | Phòng ngủ, giường | Số phòng ngủ và số giường. |
| `bathrooms`, `bathrooms_text` | Số thực, chuỗi | Phòng tắm, mô tả | Số phòng tắm gốc và chuỗi mô tả dùng parse `bathrooms_clean` (quy đổi `Half-bath` = `0.5`). |
| `amenities` | Chuỗi JSON | Danh sách tiện nghi | QA kiểm tra chuỗi có giải mã được thành JSON list hay không. |
| `price` | Chuỗi tiền tệ (có thể thiếu) | `EUR`/đêm | Giá niêm yết gốc (vd. `$73.00`), làm sạch thành `price_clean` dạng số thực. |
| `minimum_nights`, `maximum_nights` | Số nguyên | Đêm/lượt ở | Số đêm lưu trú tối thiểu/tối đa công bố. |
| `availability_30/60/90/365` | Số nguyên | Ngày mở lịch | Số ngày còn mở trong cửa sổ 30, 60, 90, 365 ngày tới. |
| `number_of_reviews`, `number_of_reviews_ltm`, `number_of_reviews_l30d` | Số nguyên | Review | Số review tích lũy, 12 tháng gần nhất (dùng cho K05) và 30 ngày gần nhất. |
| `first_review`, `last_review` | Ngày (có thể thiếu) | `YYYY-MM-DD` | Ngày review đầu tiên và gần nhất của listing. |
| `review_scores_*` | Số thực (có thể thiếu) | Điểm `[0, 5]` | Điểm đánh giá tổng thể và 6 khía cạnh con (accuracy, cleanliness, checkin, communication, location, value). |
| `license` | Chuỗi (có thể thiếu) | Mã AL / `exempt` | Tình trạng giấy phép Alojamento Local (dùng tách thuế nhóm có giấy phép ở K05). |

### Calendar và Reviews

| Bảng | Cột | Kiểu | Đơn vị / miền giá trị | Ý nghĩa |
|---|---|---|---|---|
| `calendar` | `listing_id`, `date` | Chuỗi ID, Ngày | Mã, `YYYY-MM-DD` | Khóa chính theo chỗ ở và ngày lịch. |
| `calendar` | `available` | Ký tự | `t` / `f` | `t`: mở đặt, `f`: đóng (đã đặt hoặc chủ khóa lịch). |
| `calendar` | `minimum_nights`, `maximum_nights` | Số nguyên | Đêm/lượt ở | Giới hạn số đêm áp dụng tại ngày lịch đó. |
| `reviews` | `id`, `listing_id`, `reviewer_id` | Chuỗi ID | Mã | Định danh review, chỗ ở và người đánh giá. |
| `reviews` | `date` | Ngày | `YYYY-MM-DD` | Ngày đăng review. |
| `reviews` | `reviewer_name`, `comments` | Chuỗi | Văn bản | Tên người viết và nguyên văn bình luận gốc. |

---

## 2. Tệp cờ QA & báo cáo QA

QA chỉ gắn cờ (`True`/`False`) và tạo cột sạch (`price_clean`, `bathrooms_clean`, `comment_clean`), **giữ nguyên toàn bộ cột và dòng gốc**. [QA host & vị trí](../src/flag_host_locations.py) · [QA giá & lịch](../src/flag_price_calendar.py) · [QA thuộc tính](../src/flag_property_cross.py) · [QA review](../src/flag_reviews.py) · [Gộp báo cáo QA](../src/qa_report.py)

| Tệp trong `data/processed/` | Các cột cờ / cột làm sạch chính |
|---|---|
| `listings_host_location_flags_<mốc>.csv.gz` | `id`, `dup_id_in_snapshot`, `host_id_missing`, `host_count_inconsistent`, `host_since_invalid`, `host_rate_type`, `coord_missing_or_invalid`, `coord_outside_porto`, `coord_outside_area`, `neighbourhood_missing_or_unknown` |
| `listings_price_flags_<mốc>.csv.gz` | `id`, `price_type`, `price_missing`, `price_outlier`, `min_nights_outlier`, `long_stay_listing`, `availability_out_of_range`, `price_jump`, `price_clean` |
| `listings_property_flags_<mốc>.csv.gz` | `id`, `room_type_category`, `property_type_rare`, `capacity_outlier`, `bedrooms_beds_inconsistent`, `bathrooms_type`, `amenities_parse`, `calendar_vs_listing`, `attr_changed`, `coord_drift`, `reviews_decrease`, `bathrooms_clean` |
| `listings_review_flags_<mốc>.csv.gz` | `id`, `no_reviews`, `reviews_inconsistent`, `review_score_range` |
| `reviews_flagged_<mốc>.csv.gz` | 6 cột nguồn + `review_dup_id`, `review_dup_content`, `review_orphan`, `review_date_invalid`, `comment_markup`, `comment_clean`, `comment_empty_or_short`, `exclude_from_llm_sample` |

**Báo cáo QA tổng hợp** nằm tại [reports/qa_report.csv](qa_report.csv) (gộp từ 4 tệp thành phần trong `data/interim/qa_parts/`, `kpi_k7_report.csv`, `kpi_k8_report.csv` và tác động trước/sau QA lên các KPI) với 3 loại dòng theo cột `section`: `rule` (chi tiết quy tắc và `%` bị gắn cờ), `rows` (số dòng trước/sau lọc QA), và `kpi_impact` (giá trị KPI cấp thành phố/khu trước và sau QA, kèm `delta`).

---

## 3. Bảng KPI (`data/processed/kpi_*.csv`)

Mỗi dòng biểu diễn một phép đo (`kpi_id`, `kpi_name`) tại mốc `snapshot` và khu `neighbourhood_cleansed` (`A01`–`A08` hoặc `ALL`). Đọc `value` đi kèm `unit`, `currency`, `n_used` và `n_excluded`.

| Tệp | Nội dung `value` | Ghi chú đọc cột |
|---|---|---|
| `kpi_k1_area_share.csv` | Tỷ trọng listing của khu trong mẫu (`%`). | `100 × n_listings_area / n_listings_city`, có `share_delta_pp`, `rising_streak`, `flag_rising_share`. |
| `kpi_k2_multi_host_share.csv` | Tỷ lệ listing thuộc chủ có `≥ 2` listing (`%`). | Đếm theo `host_id` toàn mẫu mốc; có `n_multi_host_listings`, `share_delta_pp`, `flag_rising`. |
| `kpi_k3_entire_home_share.csv` | Tỷ lệ nguyên căn (`Entire home/apt`) sau lọc QA (`%`). | Có kèm `value_before_qa`, `n_entire_before_qa`, `n_total_before_qa`, `n_entire_after_qa`, `n_total_after_qa`. |
| `kpi_k4_supply_change.csv` | Biến động nguồn cung ròng giữa 2 mốc liên tiếp (`%`). | `100 × (n_new - n_gone) / n_prev`; `comparison_period` ghi cặp mốc. |
| `kpi_k5_revenue_tax.csv` | Số đêm đặt, công suất (`%`), doanh thu và thuế du lịch tiềm năng (`EUR/năm`), nhóm outlier giá. | Lọc theo `kpi_name` (11 chỉ số/khu/mốc); xem thêm `reports/k5_sensitivity.csv` và `reports/k5_checks.csv`. |
| `kpi_k6_commercial_share.csv` | Tỷ lệ listing thương mại/trung hạn (`availability_365 > 240` hoặc `minimum_nights >= 30`) và biên CI 95% (`pp`). | 5 chỉ số/khu/mốc (`commercial_share`, `commercial_share_margin95`, `commercial_listings`, `availability_share`, `long_stay_share`). |
| `kpi_k7_community_complaint.csv` | Tỷ lệ review hợp lệ có phàn nàn cộng đồng (`noise`, `neighbours`, `area_hygiene`, `safety`) có dẫn chứng nguyên văn (`%`). | Có `value_before_qa` và `n_before_qa`; ô có `n_used < 30` để trống `value`. |
| `kpi_k8_data_reliability.csv` | Tỷ lệ gắn cờ / thiếu độ phủ / loại trừ (`%`) theo từng quy tắc kiểm định. | `n_used` là quy mô kiểm tra, `n_excluded` là số ca bị cờ/loại. |

---

## 4. Tệp Baseline NLP, LLM và Đánh giá

| Tệp | Các cột chính & ý nghĩa |
|---|---|
| `data/processed/reviews_valid.csv` | Review hợp lệ sau QA (`snapshot`, `id`, `listing_id`, `date`, `comment_clean`) làm đầu vào cho Baseline và K07. |
| `data/processed/baseline_reviews.csv` | Kết quả phân tích không dùng LLM: `review_id`, `language`, `sentiment`, `aspects_positive`, `aspects_negative`, `status`, `lang_confidence`, `pos_score`, `neg_score`. [Mã baseline](../src/baseline.py) |
| `data/interim/k7_llm_cache.jsonl` | Nhật ký cache từng lượt gọi LLM theo `id` và `attempt` (`ok`, `result`, `error`, `model`, `prompt_version`). [Mã LLM](../src/llm_label.py) |
| `data/interim/k7_labels.csv` | Bảng nhãn LLM cuối cùng (635 ID duy nhất: 633 `label_valid=True`, 2 `False`): `id`, `sentiment`, `language`, `aspects_praised`, `aspects_criticized`, `evidence`, `label_valid`, `error`. |
| `data/processed/k7_evidence_review.csv` | Danh sách 7 review bị cờ `llm_evidence_missing` (trích dẫn không khớp nguyên văn) để kiểm tra tay. |
| `data/interim/k7_handlabel_sample.csv` | Tập 150 review gán nhãn tay (`hand_language`, `hand_sentiment`, `hand_community_complaint`). |
| `reports/eval_summary.csv` | Độ chính xác (`accuracy`), `macro_f1`, `precision`, `recall`, `f1` của cả Baseline và LLM so với 150 nhãn tay. [Mã đánh giá](../src/evaluate.py) |
| `reports/eval_baseline_vs_llm.csv` | Mức đồng thuận chéo giữa Baseline và LLM trên toàn bộ mẫu 633 review có nhãn hợp lệ. |
| `reports/eval_mismatches.csv` | Danh sách chi tiết các ca Baseline hoặc LLM dự đoán lệch so với nhãn tay để phân tích lỗi. |
