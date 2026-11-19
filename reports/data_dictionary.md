# Từ điển dữ liệu Airbnb Porto

Mã nhóm `DSE2049-C04-G06-porto`. Bốn mốc trong cấu hình là 21/09/2025, 26/03/2026, 23/06/2026 và 19/09/2026. Mỗi tệp có hậu tố `<mốc>` chứa một ngày chụp dữ liệu, viết theo dạng `YYYY-MM-DD`. Các kiểu dưới đây là kiểu dùng khi phân tích CSV. Đọc mã định danh dưới dạng chuỗi để giữ nguyên các ID dài. [Cấu hình](../configs/porto.yaml)

## Bảng đầu vào

| Bảng trong `data/interim/` | Một dòng biểu diễn | Khóa dự kiến trong từng mốc | Phạm vi |
|---|---|---|---|
| `listings_<mốc>.csv.gz` | Một chỗ ở được quan sát | `id` | Các ID listing được giao có mặt trong dữ liệu thô. Ghép `analysis_area` từ bảng phân khu của nhóm. |
| `calendar_<mốc>.csv.gz` | Trạng thái lịch của một chỗ ở trong một ngày | `listing_id`, `date` | Lọc theo ID listing được giao, giữ ba cột. |
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
| reviews | `id`, `listing_id`, `reviewer_id` | Chuỗi ID | Mã | Lần lượt định danh review, chỗ ở được đánh giá và người viết. |
| reviews | `date` | Ngày | YYYY-MM-DD | Ngày đăng review. |
| reviews | `reviewer_name`, `comments` | Chuỗi, có thể thiếu | Văn bản | Tên hiển thị của người viết và nội dung review gốc. |

## Tệp cờ QA trong `data/processed/`

Các cột cờ có kiểu logic, nhận `True` khi thỏa điều kiện gắn cờ. QA giữ các dòng gốc. Ghép hai tệp cờ listing bằng `id` trong cùng mốc. Tệp review đã gắn cờ giữ sáu cột nguồn nêu trên. [Quy tắc, ngưỡng và hành động theo từng cờ](qa_kpi_methods.md)

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

Mỗi dòng trong `reports/qa_report_property.csv` và `reports/qa_report_reviews.csv` mô tả một quy tắc ở một mốc hoặc một cặp mốc.

| Cột | Kiểu | Đơn vị hoặc miền giá trị | Ý nghĩa |
|---|---|---|---|
| `rule`, `table` | Chuỗi | Tên quy tắc, tên bảng | Đọc cùng nhau vì `key_unique` và `id_set_consistent` xuất hiện ở cả listings và reviews. |
| `kind` | Chuỗi phân loại | `flag`, `check`, `impact` | Lần lượt là gắn cờ, kiểm tra tổng hợp và đo tác động lên mẫu. |
| `snapshot` | Chuỗi | Ngày hoặc `ngày_trước->ngày_sau` | Mốc quan sát hoặc kỳ so sánh. |
| `condition`, `reason`, `action` | Chuỗi | Văn bản | Điều kiện kích hoạt, lý do kiểm tra và cách xử lý. |
| `rows_total`, `rows_flagged` | Số nguyên | Dòng hoặc ID, tùy quy tắc | Quy mô kiểm tra và số trường hợp thỏa điều kiện. Với so sánh tập ID, mẫu số là số ID ở mốc trước. |
| `note` | Chuỗi, có thể trống | Văn bản | Chi tiết đối chiếu, ví dụ số ID mới, số dòng đủ điều kiện, số giá trị còn thiếu. |

## Các tệp `kpi_*.csv` đã xuất

Hai tệp cùng nằm trong `data/processed/`. Một dòng ứng với một cặp `(snapshot, khu)`. `ALL` gộp các khu trong **mẫu của nhóm**. Giá trị phần trăm được làm tròn đến hai chữ số thập phân, mẫu số bằng 0 cho ô trống.

| Tệp | Cột | Kiểu và đơn vị | Ý nghĩa |
|---|---|---|---|
| Cả K3 và K4 | `snapshot`, `khu` | Ngày ISO, chuỗi phân loại | Với K4, ngày là mốc sau của cặp mốc liền nhau trong cấu hình. Khu thiếu mang nhãn `(thiếu)`. |
| `kpi_k3_entire_home_share.csv` | `n_entire`, `n_total` | Số nguyên, listing | Số nguyên căn và tổng số listing trước khi xét cờ. |
| K3 | `value_pct` | Số thực, % | Tỷ lệ nguyên căn trên toàn nhóm dòng. |
| K3 | `n_skipped`, `n_total_ok`, `n_entire_ok` | Số nguyên, listing | Số dòng bỏ do cờ đã chọn, tổng dòng giữ và số nguyên căn trong phần giữ. |
| K3 | `value_pct_ok` | Số thực, % | Tỷ lệ nguyên căn sau khi áp dụng `kpi.skip_flags.k3`. |
| `kpi_k4_supply_change.csv` | `n_new`, `n_gone`, `n_prev` | Số nguyên, listing | Số ID xuất hiện mới, số ID biến mất và số ID ở mốc trước. |
| K4 | `value_pct` | Số thực có dấu, % | Thay đổi nguồn cung ròng tính trên số listing ở mốc trước. |
