# Từ điển dữ liệu Airbnb Porto

Mã nhóm `DSE2049-C04-G06-porto`. Bốn mốc trong cấu hình là 21/09/2025, 26/03/2026, 23/06/2026 và 19/09/2026. Mỗi tệp có hậu tố `<mốc>` chứa một ngày chụp dữ liệu, viết theo dạng `YYYY-MM-DD`. Các kiểu dưới đây là kiểu dùng khi phân tích CSV. Đọc mã định danh dưới dạng chuỗi để giữ nguyên các ID dài. [Cấu hình](../configs/porto.yaml)

## Bảng đầu vào

| Bảng trong `data/interim/` | Một dòng biểu diễn | Khóa dự kiến trong từng mốc | Phạm vi |
|---|---|---|---|
| `listings_<mốc>.csv.gz` | Một chỗ ở được quan sát | `id` | Các ID listing được giao có mặt trong dữ liệu thô. Ghép `analysis_area` từ bảng phân khu của nhóm. |
| `calendar_<mốc>.csv.gz` | Trạng thái lịch của một chỗ ở trong một ngày | `listing_id`, `date` | Lọc theo ID listing được giao, giữ năm cột ở bảng dưới. |
| `reviews_<mốc>.csv.gz` | Một lượt đánh giá của khách | `id` | Lọc theo danh sách ID review được giao. Một review có thể xuất hiện lại ở nhiều mốc. |

Khi nối bảng, dùng cùng mốc và nối `calendar.listing_id` hoặc `reviews.listing_id` với `listings.id`. Trong bảng giao mẫu, `review_id` tương ứng với `reviews.id`. Dữ liệu thô toàn Porto dùng để ước lượng chi phí nằm ở `../<mốc>/reviews.csv.gz` tính từ gốc dự án. [Bước lọc dữ liệu](../src/filter_all.py)

### Listings

Tệp đã lọc có 80 cột ở mốc đầu và 91 cột ở ba mốc sau. Bảng dưới mô tả các cột chính dùng để nối bảng, kiểm tra chất lượng và tính chỉ số.

| Cột | Kiểu | Đơn vị hoặc miền giá trị | Ý nghĩa |
|---|---|---|---|
| `id`, `host_id` | Chuỗi ID | Mã | Lần lượt định danh chỗ ở và chủ nhà. Một chủ có thể có nhiều chỗ ở. |
| `name` | Chuỗi | Văn bản | Tên hiển thị của chỗ ở. |
| `last_scraped` | Ngày | YYYY-MM-DD | Ngày thu thập listing, làm mốc trên để đối chiếu ngày review. |
| `host_since` | Ngày, có thể thiếu | YYYY-MM-DD | Ngày chủ nhà hiện tại tham gia Airbnb. QA cho phép review sớm hơn ngày này tối đa 30 ngày trước khi gắn cờ. |
| `analysis_area` | Chuỗi phân loại | A01–A08 trong mẫu | Khu nhóm dùng để tính KPI, lấy từ bảng giao ID. |
| `neighbourhood_cleansed` | Chuỗi phân loại | Tên địa bàn | Địa bàn đã chuẩn hóa trong bộ dữ liệu nguồn. |
| `latitude`, `longitude` | Số thực | Độ vĩ, độ kinh | Tọa độ chỗ ở, dùng để đối chiếu vị trí qua các mốc. |
| `room_type` | Chuỗi phân loại | `Entire home/apt`, `Private room`, `Shared room`, `Hotel room` | Hình thức cho thuê. K3 đếm nhãn khớp chính xác `Entire home/apt`. |
| `property_type` | Chuỗi phân loại | Loại hình | Loại bất động sản chi tiết. QA tính tỷ trọng từng loại trong mốc. |
| `accommodates` | Số nguyên | Khách | Sức chứa công bố. |
| `bedrooms`, `beds` | Số đếm, có thể thiếu | Phòng ngủ, giường | Số phòng ngủ và số giường. |
| `bathrooms`, `bathrooms_text` | Số thực, chuỗi | Phòng tắm, mô tả | Số phòng tắm nguồn và mô tả dùng để khôi phục số, kể cả nửa phòng tắm. |
| `amenities` | Chuỗi JSON | Danh sách tiện nghi | QA kiểm tra chuỗi có giải mã thành danh sách được hay không. |
| `price` | Chuỗi tiền tệ, có thể thiếu | EUR/đêm theo cấu hình Porto | Giá niêm yết. Nguồn có giá trị như `$73.00`. Khi tính giá, tách ký hiệu và dấu phân nhóm trước khi chuyển sang số. |
| `minimum_nights`, `maximum_nights` | Số nguyên | Đêm/lượt ở | Giới hạn thời gian lưu trú công bố. |
| `availability_30`, `availability_60`, `availability_90`, `availability_365` | Số nguyên | Ngày mở lịch | Số ngày còn mở trong cửa sổ lần lượt 30, 60, 90, 365 ngày. |
| `number_of_reviews`, `number_of_reviews_ltm`, `number_of_reviews_l30d` | Số nguyên | Review | Lần lượt là số review tích lũy, trong 12 tháng gần nhất và trong 30 ngày gần nhất theo nguồn. |
| `first_review`, `last_review` | Ngày, có thể thiếu | YYYY-MM-DD | Ngày review đầu tiên và gần nhất của listing. |
| `review_scores_rating` | Số thực, có thể thiếu | Điểm, QA chấp nhận [0, 5] | Điểm đánh giá tổng thể của listing. |
| `review_scores_accuracy`, `review_scores_cleanliness`, `review_scores_checkin`, `review_scores_communication`, `review_scores_location`, `review_scores_value` | Số thực, có thể thiếu | Điểm, QA chấp nhận [0, 5] | Điểm theo độ chính xác, vệ sinh, nhận phòng, giao tiếp, vị trí và tương xứng với giá. |

### Calendar và reviews

| Bảng | Cột | Kiểu | Đơn vị hoặc miền giá trị | Ý nghĩa |
|---|---|---|---|---|
| calendar | `listing_id` | Chuỗi ID | Mã | Chỗ ở có ngày lịch này. |
| calendar | `date` | Ngày | YYYY-MM-DD | Ngày lưu trú được quan sát trên lịch. |
| calendar | `available` | Cờ dạng ký tự | `t` / `f` | `t` là mở để đặt, `f` là đóng. Ngày đóng có thể do chủ chặn hoặc do đã được đặt. |
| calendar | `minimum_nights`, `maximum_nights` | Số nguyên, có thể thiếu | Đêm/lượt ở | Số đêm tối thiểu và tối đa áp dụng cho listing ở ngày lịch đó. |
| reviews | `id`, `listing_id`, `reviewer_id` | Chuỗi ID | Mã | Lần lượt định danh review, chỗ ở được đánh giá và người viết. |
| reviews | `date` | Ngày | YYYY-MM-DD | Ngày đăng review. |
| reviews | `reviewer_name`, `comments` | Chuỗi, có thể thiếu | Văn bản | Tên hiển thị của người viết và nội dung review gốc. |

## Tệp cờ QA trong `data/processed/`

Các cột cờ có kiểu logic, nhận `True` khi thỏa điều kiện gắn cờ. QA giữ các dòng gốc. Ghép từng tệp cờ listing bằng `id` trong cùng mốc. Tệp review đã gắn cờ giữ sáu cột nguồn nêu trên. [Quy tắc QA review](../src/flag_reviews.py) · [QA thuộc tính](../src/flag_property_cross.py) · [QA chủ nhà và vị trí](../src/flag_host_locations.py) · [QA giá và lịch](../src/flag_price_calendar.py)

| Tệp | Cột | Kiểu và đơn vị | Ý nghĩa |
|---|---|---|---|
| `listings_property_flags_<mốc>.csv.gz` | `id` | Chuỗi ID, mã listing | Khóa nối với listings. |
| Như trên | `room_type_category`, `property_type_rare` | Logic | Nhãn loại phòng lạ/thiếu hoặc loại bất động sản hiếm, tương ứng. |
| Như trên | `capacity_outlier`, `bedrooms_beds_inconsistent` | Logic | Sức chứa ngoài giới hạn hoặc số phòng ngủ/giường bất nhất. |
| Như trên | `bathrooms_type`, `bathrooms_clean` | Logic, số thực (phòng tắm) | Cờ đánh dấu số gốc thiếu/sai kiểu và số sau khi bổ sung từ mô tả. Cờ vẫn đúng khi bổ sung thành công. |
| Như trên | `amenities_parse`, `calendar_vs_listing` | Logic | Lỗi đọc danh sách tiện nghi hoặc listing thiếu lịch cùng mốc. |
| Như trên | `attr_changed`, `coord_drift`, `reviews_decrease` | Logic | Thay đổi thuộc tính, dao động tọa độ hoặc giảm tổng review qua các mốc. |
| `listings_review_flags_<mốc>.csv.gz` | `id` | Chuỗi ID, mã listing | Khóa nối với listings. |
| Như trên | `no_reviews`, `reviews_inconsistent`, `review_score_range` | Logic | Tổng review bằng 0, thông tin review mâu thuẫn, hoặc có điểm ngoài khoảng cấu hình. |
| `reviews_flagged_<mốc>.csv.gz` | `review_dup_id`, `review_dup_content`, `review_orphan` | Logic | Trùng mã, trùng bộ khóa nội dung, hoặc thiếu listing liên kết trong mẫu cùng mốc. |
| Như trên | `days_before_host_since`, `review_date_invalid` | Số (ngày, có thể thiếu), logic | Ngày chủ tham gia trừ ngày review. Giá trị dương nghĩa là review có trước. Cờ tổng hợp các bất thường về ngày. |
| Như trên | `comment_markup`, `comment_clean` | Logic, chuỗi văn bản | Phát hiện thẻ trong nội dung gốc và văn bản sau làm sạch. |
| Như trên | `comment_empty_or_short`, `exclude_from_llm_sample` | Logic | Nội dung sạch dưới ngưỡng độ dài và quyết định loại khỏi tập đủ điều kiện LLM. Hai cột trùng giá trị theo cấu hình hiện tại. |

### Báo cáo QA tổng hợp

Mỗi dòng trong bốn báo cáo `qa_report_property.csv`, `qa_report_reviews.csv`, `qa_report_host_locations.csv` và `qa_report_price_calendar.csv` thuộc `reports/` mô tả một quy tắc ở một mốc hoặc một cặp mốc.

| Cột | Kiểu | Đơn vị hoặc miền giá trị | Ý nghĩa |
|---|---|---|---|
| `rule`, `table` | Chuỗi | Tên quy tắc, tên bảng | Đọc cùng nhau vì `key_unique` và `id_set_consistent` xuất hiện ở cả listings và reviews. |
| `kind` | Chuỗi phân loại | `flag`, `check`, `impact` | Lần lượt là gắn cờ, kiểm tra tổng hợp và đo tác động lên mẫu. |
| `snapshot` | Chuỗi | Ngày hoặc `ngày_trước->ngày_sau` | Mốc quan sát hoặc kỳ so sánh. |
| `condition`, `reason`, `action` | Chuỗi | Văn bản | Điều kiện kích hoạt, lý do kiểm tra và cách xử lý. |
| `rows_total`, `rows_flagged` | Số nguyên | Dòng hoặc ID, tùy quy tắc | Quy mô kiểm tra và số trường hợp thỏa điều kiện. Với so sánh tập ID, mẫu số là số ID ở mốc trước. |
| `note` | Chuỗi, có thể trống | Văn bản | Chi tiết đối chiếu, ví dụ số ID mới, số dòng đủ điều kiện, số giá trị còn thiếu. |

## Kết quả KPI trong `data/processed/`

Một dòng ghi một phép đo (`kpi_id`, `kpi_name`) tại mốc `snapshot` và khu `neighbourhood_cleansed`. Trong kết quả theo khu của nhóm, cột này chứa mã phân tích như `A01`. Dòng `ALL`, khi có, tổng hợp trên mẫu của nhóm. Đọc `value` cùng `unit` và `currency`. Với K5–K8, dùng thêm `period` và `kpi_name` khi lọc dữ liệu vì cùng khu và mốc có thể có nhiều phép đo.

| Tệp | Ý nghĩa của `value` | Cách đọc các cột liên quan |
|---|---|---|
| `kpi_k1_area_share.csv` | Tỷ trọng listing của khu trong mẫu tại mốc (%). | 100 × `n_listings_area` / `n_listings_city`. |
| `kpi_k2_multi_host_share.csv` | Tỷ lệ listing trong khu thuộc chủ đạt ngưỡng nhiều listing (%). Cấu hình Porto đếm listing của mỗi chủ trên toàn mẫu của mốc. | 100 × `n_multi_host_listings` / `n_listings`. |
| `kpi_k3_entire_home_share.csv` | Tỷ lệ nguyên căn sau khi áp dụng cờ QA (%). | 100 × `n_entire_after_qa` / `n_total_after_qa`. Các cột `value_before_qa`, `n_entire_before_qa` và `n_total_before_qa` cho biết tỷ lệ, tử số và mẫu số trước lọc. |
| `kpi_k4_supply_change.csv` | Biến động nguồn cung ròng giữa hai mốc (%). | 100 × (`n_new` − `n_gone`) / `n_prev`. `comparison_period` ghi cặp mốc, `snapshot` là mốc sau. |
| `kpi_k05_revenue_tax.csv` | Ước tính số đêm đã đặt, công suất, doanh thu, thuế du lịch và ảnh hưởng của giá ngoại lệ. | Chọn `kpi_name` rồi đọc `unit` tương ứng (đêm/năm, %, EUR/năm hoặc số listing). |
| `kpi_k06_commercial_share.csv` | Tỷ lệ hoặc số listing thuộc nhóm thương mại/trung hạn theo ngưỡng ngày mở lịch hoặc thời gian lưu trú tối thiểu. | `commercial_share` tính bằng %, `commercial_share_margin95` là biên sai số theo điểm phần trăm. |
| `kpi_k07_community_complaint.csv` | Tỷ lệ review đủ điều kiện có phàn nàn về cộng đồng (%). Review mang nhãn phàn nàn cần có dẫn chứng hợp lệ. | `n_used` là mẫu số, `n_excluded` là số bị loại. Ô thiếu cỡ mẫu tối thiểu để trống `value`. |
| `kpi_k8_data_reliability.csv` | Tỷ lệ vi phạm hoặc thiếu độ phủ (%) theo quy tắc ghi ở `kpi_name`. | `n_used` là số trường hợp kiểm tra, `n_excluded` đếm trường hợp bị gắn cờ theo phép đo. Tệp `kpi_k08_data_reliability.csv` có nội dung giống tệp này ở phiên bản hiện tại. |

Cả tám nhóm có `n_used` và `n_excluded` theo phạm vi từng phép đo. K1–K4 xuất thêm `numerator` (tử số) và `denominator` (mẫu số). Với K1/K2, `share_delta_pp` là chênh lệch tỷ trọng so với mốc trước, `rising_streak` đếm số kỳ tăng liên tiếp, còn `flag_rising_share` (K1) và `flag_rising` (K2) đánh dấu xu hướng tăng theo cấu hình.

Hai tệp `kpi_k07_report.csv` và `kpi_k08_report.csv` ghi kết quả kiểm tra theo quy tắc. Tệp `k07_evidence_review.csv` lưu các trường hợp cần kiểm tra dẫn chứng với các cột `id`, `listing_id`, `comment_clean`, `evidence`.

## Văn bản đầu vào của baseline

`comments` là nguyên văn review trong dữ liệu nguồn và tệp mẫu. Bước QA giải mã HTML, bỏ thẻ và chuẩn hóa khoảng trắng để tạo `comment_clean`. Pipeline truyền `reviews_valid.csv` có cột `id` và `comment_clean` cho baseline. Tệp mẫu `data/samples/reviews_sample.csv` dùng dấu tab và có hai cột `review_id`, `comments`.

Baseline chọn cột một lần theo tiêu đề tệp. Khi có `comment_clean`, baseline dùng giá trị ở cột này, kể cả ô rỗng (trạng thái `excluded_empty`). Khi chỉ có `comments`, văn bản gốc đi qua cùng hàm xử lý của baseline. [Bước QA review](../src/flag_reviews.py) · [Baseline](../src/baseline.py)

Hai tài liệu tại commit `e152bc1` ghi lại phương pháp và giả định ở thời điểm đó. [Bảng phương pháp QA/KPI cũ](https://github.com/khang562007-rgb/2627-LTXLDL-Airbnb-Nhom_6-K70A_AI4/blob/e152bc1/reports/qa_kpi_methods.md) · [Ước lượng chi phí LLM cũ](https://github.com/khang562007-rgb/2627-LTXLDL-Airbnb-Nhom_6-K70A_AI4/blob/e152bc1/reports/llm_cost_porto.md)
