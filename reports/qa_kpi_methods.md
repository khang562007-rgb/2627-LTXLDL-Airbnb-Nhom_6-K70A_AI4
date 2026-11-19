# Phương pháp QA và KPI của mẫu Airbnb Porto

## Quy tắc QA

Các ngưỡng dưới đây lấy từ cấu hình Porto. Mỗi quy tắc được đối chiếu với điều kiện thực thi và các cột đã xuất. Một dòng có thể mang nhiều cờ. Khi tính số dòng bị ảnh hưởng, lấy hợp các dòng thỏa điều kiện để tránh đếm lặp. [Cấu hình](../configs/porto.yaml) · [Từ điển cột](data_dictionary.md)

### Reviews và thông tin đánh giá của listing

| Tên | Điều kiện | Lý do | Hành động |
|---|---|---|---|
| `key_unique` (reviews) | ID review lặp trong một mốc. | Kiểm tra khóa. | Đếm số lần xuất hiện dư sau lần đầu trong báo cáo. |
| `review_dup_id` | Cùng ID review xuất hiện ít nhất hai lần trong mốc. | Có thể đếm cùng review nhiều lần. | Gắn cờ **tất cả** các dòng trùng ID. |
| `review_dup_content` | Trùng cả `listing_id`, `reviewer_id`, `date`, `comments` gốc. | Hai bản ghi có thể là cùng một đánh giá. | Gắn cờ tất cả các dòng trong nhóm trùng. |
| `review_orphan` | `listing_id` vắng trong bảng listings của nhóm ở cùng mốc. | Thiếu thông tin chỗ ở để nối bảng. | Gắn cờ review. |
| `review_date_invalid` | Ngày review thiếu/không đọc được, sau `last_scraped`, hoặc sớm hơn `host_since` trên 30 ngày. | Ngày có thể sai hoặc listing đã đổi chủ. | Gắn cờ, ghi chi tiết trong `note`. Review vẫn có thể vào mẫu LLM. Khi thiếu ngày tham chiếu, phép so sánh tương ứng không kích hoạt cờ. |
| `comment_markup` | `comments` gốc khớp biểu thức nhận diện thẻ HTML. | Thẻ và xuống dòng làm nhiễu nội dung. | Tạo `comment_clean` cho mọi dòng bằng cách giải mã HTML, thay thẻ xuống dòng bằng khoảng trắng, bỏ thẻ còn lại và chuẩn hóa khoảng trắng. Giữ văn bản gốc. |
| `comment_empty_or_short` | `comment_clean` có ít hơn 3 ký tự, kể cả rỗng. | Thiếu văn bản để phân tích. | Gắn cờ và đặt `exclude_from_llm_sample=True`. |
| `llm_sample_size` | Đếm các dòng có `exclude_from_llm_sample=True`. | Đo tác động của QA lên tập ứng viên. | Ghi số bị loại vào `rows_flagged`, số đủ điều kiện vào `note`. Số thực sự đưa đi gán nhãn cần lấy từ lần chạy LLM. |
| `zero_review_count` | `number_of_reviews = 0`. | Đối chiếu số listing chưa có đánh giá. | Ghi cờ `no_reviews` ở cấp listing và tổng số vào báo cáo. |
| `reviews_inconsistent` | Tổng review bằng 0 nhưng có điểm số hoặc `last_review`, hoặc tổng dương nhưng thiếu cả điểm lẫn ngày cuối. | Thông tin đánh giá mâu thuẫn trong cùng listing. | Gắn cờ listing, ghi số trường hợp từng chiều. |
| `review_score_range` | Có ít nhất một điểm `review_scores_*` đọc được nằm ngoài [0, 5]. | Điểm vượt thang cấu hình. | Gắn cờ listing. Điểm thiếu/sai kiểu được chuyển thành giá trị thiếu khi so khoảng. |
| `id_set_consistent` (reviews) | ID có ở mốc trước, vắng ở mốc sau liền kề. | Theo dõi thay đổi độ phủ mẫu. | Báo số ID mất ở `rows_flagged` và số ID mới ở `note`. |

[Mã QA reviews](../src/qa.py) · [Kết quả từng mốc](qa_report_reviews.csv)

### Thuộc tính listing, lịch và thay đổi qua mốc

| Tên | Điều kiện | Lý do | Hành động |
|---|---|---|---|
| `key_unique` (listings) | ID thiếu, hoặc ID có giá trị trùng với một dòng trước đó. | Khóa nối QA/KPI cần duy nhất. | Báo số dòng thiếu cộng số lần xuất hiện dư của ID có giá trị. |
| `room_type_category` | `room_type` thiếu hoặc ngoài bốn nhãn cho phép trong từ điển. | Phân loại phòng không hợp lệ. | Gắn cờ. K3 loại các dòng này khi tính `value_pct_ok`. |
| `property_type_rare` | Loại có tỷ trọng dưới 0,5% trên các `property_type` có giá trị của mốc. | Loại ít quan sát, khó so sánh. | Gắn cờ các dòng thuộc loại hiếm. |
| `capacity_outlier` | `accommodates` thiếu, dưới 1 hoặc trên 16. | Sức chứa bất thường. | Gắn cờ. |
| `bedrooms_beds_inconsistent` | `bedrooms > accommodates` hoặc `beds = 0`. | Phòng ngủ hoặc số giường cần đối chiếu. | Gắn cờ. |
| `bathrooms_type` | `bathrooms` gốc thiếu hoặc không chuyển được sang số. | Thiếu số phòng tắm để phân tích. | Gắn cờ nguồn. Tạo `bathrooms_clean` từ số gốc hoặc trích số trong `bathrooms_text`; mô tả chứa “half” và không có số cho giá trị 0,5. |
| `amenities_parse` | `amenities` thiếu, lỗi JSON hoặc kết quả giải mã khác kiểu danh sách. | Không thể đếm tiện nghi nhất quán. | Gắn cờ. |
| `calendar_vs_listing` | Listing không có dòng lịch nào cùng mốc. | Đối chiếu độ phủ của lịch. | Gắn cờ listing. Ghi riêng số dòng lịch có ID thiếu liên kết trong `note`. |
| `attr_changed` | Cùng ID có nhiều hơn một giá trị qua các mốc ở ít nhất một trong ba cột `room_type`, `property_type`, `bedrooms`. Giá trị thiếu được tính là một trạng thái. | Thay đổi có thể ảnh hưởng so sánh theo thời gian. | Gắn cờ ở mọi mốc có ID đó. |
| `coord_drift` | Đường chéo khung bao tọa độ qua các mốc vượt 200 m. Code đổi chênh vĩ độ sang mét bằng hệ số 111.000 và hiệu chỉnh chênh kinh độ bằng cosin vĩ độ trung bình. | Phát hiện listing có vị trí dao động đáng kể. | Gắn cờ ở mọi mốc có ID đó. Đây là khoảng cách xấp xỉ từ các cực trị. |
| `reviews_decrease` | Tổng review thấp hơn lần quan sát có số liệu gần nhất trước đó của cùng ID. | Tổng tích lũy giảm cần được giải thích. | Gắn cờ tại mốc ghi nhận mức giảm. |
| `id_set_consistent` (listings) | ID thuộc mốc trước và vắng ở mốc liền sau. | Định lượng biến động nguồn cung của mẫu. | Báo số ID mất và ghi thêm số ID mới để đối chiếu K4. |

[Mã QA thuộc tính và lịch](../src/flag_property_cross.py) · [Kết quả từng mốc](qa_report_property.csv)

## Bảng phương pháp cho 8 KPI

**Trạng thái của bảng.** K3 và K4 đã đối chiếu với mã và CSV của nhánh `dung-branch`. Nhánh này chưa có đặc tả hoặc đầu ra cho sáu mã còn lại. Các dòng ghi **đề xuất** là phương án để nhóm đối chiếu với đề gốc trước khi chốt mã, công thức và tên gọi. Ảnh giao việc chỉ nhắc đến `evidence_review` ở K7. [Mã tính K3/K4](../src/kpi_k3_k4.py)

| Tên | Mục tiêu | Công thức | Đơn vị |
|---|---|---|---|
| **K1 · Giá niêm yết trung vị** (đề xuất) | So sánh mức giá điển hình giữa các khu, theo mốc. | Trung vị `price` sau chuyển sang số, trên các listing có giá dương trong khu. | EUR/đêm |
| **K2 · Tỷ lệ ngày mở lịch** (đề xuất) | Đo phần lịch khách còn có thể đặt. | 100 × số ngày-listing có `available=t` / số ngày-listing có `available` là `t` hoặc `f`. Mỗi cặp listing–ngày được tính một lần trong mốc, trên cửa sổ 365 ngày của lịch. | % ngày-listing |
| **K3 · Tỷ lệ nguyên căn** (đã kiểm chứng) | Đo cơ cấu loại phòng theo khu và toàn mẫu tại một mốc. | Trước QA: 100 × `n_entire / n_total`. Sau lọc cờ: 100 × `n_entire_ok / n_total_ok`. Tử số đếm nhãn chính xác `Entire home/apt`. Bản trước lọc giữ cả dòng thiếu nhãn trong mẫu số. | % listing |
| **K4 · Thay đổi nguồn cung ròng** (đã kiểm chứng) | Đo tác động ròng của listing xuất hiện và biến mất trong mẫu giữa hai mốc liên tiếp. | 100 × `(n_new − n_gone) / n_prev`. So sánh tập ID trên toàn mẫu. Khi chia khu, ID mới thuộc khu ở mốc sau, ID mất thuộc khu ở mốc trước. ID có mặt ở cả hai mốc không tính là mới/mất. | % so với số listing mốc trước |
| **K5 · Tỷ lệ listing có review trong 30 ngày** (đề xuất) | Đo mức độ hoạt động đánh giá gần mốc thu thập. | 100 × số listing có `number_of_reviews_l30d > 0` / số listing có số review 30 ngày hợp lệ (số nguyên ≥ 0). | % listing |
| **K6 · Điểm tổng thể trung bình** (đề xuất) | So sánh trải nghiệm khách giữa các khu theo mốc. | Trung bình `review_scores_rating` của các listing có review và điểm tổng thể trong [0, 5]. Mỗi listing có một trọng số bằng nhau. | Điểm trên thang 0–5 |
| **K7 · Tỷ lệ review nhắc đến một chủ đề** (đề xuất) | Định lượng mức phổ biến của từng chủ đề và giữ dẫn chứng để kiểm tra nhãn. | Với từng chủ đề: 100 × số ID review được gán chủ đề / số ID review đã gán nhãn hợp lệ. Một ID tính tối đa một lần cho mỗi chủ đề. Lưu ID cùng trích dẫn `evidence_review` khớp văn bản nguồn. | % review đã gán nhãn, theo chủ đề |
| **K8 · Tỷ lệ review có cảm xúc tiêu cực** (đề xuất) | Đo mức độ xuất hiện phản hồi tiêu cực trong tập đã gán nhãn. | 100 × số ID review mang nhãn tiêu cực / số ID review có nhãn cảm xúc hợp lệ. Chốt bộ nhãn trước khi tính. | % review có nhãn cảm xúc |

Mỗi chỉ số dùng đúng mẫu số ghi trong công thức. Khi mẫu số bằng 0 hoặc không có quan sát hợp lệ, để trống kết quả. Với K3, tổng các khu theo số đếm rồi mới tính tỷ lệ `ALL`. Với K4, giữ toàn bộ ID của mẫu ở từng mốc.

### Hai phép đối chiếu có thể tính tay

- **K3 ngày 19/09/2026** có 853 nguyên căn trên 974 listing, tương ứng **87,58%**. Số dòng bị bỏ theo `room_type_category` bằng 0 nên tỷ lệ sau QA cũng là 87,58%. [CSV K3](../data/processed/kpi_k3_entire_home_share.csv)
- **K4 từ 23/06 đến 19/09/2026** có 0 ID mới, 26 ID biến mất và 1.000 ID ở mốc trước. Biến động ròng là **−2,60%**. Hai cặp mốc trước đều cho 0%. Các số này mô tả tập ID của nhóm. [CSV K4](../data/processed/kpi_k4_supply_change.csv)
