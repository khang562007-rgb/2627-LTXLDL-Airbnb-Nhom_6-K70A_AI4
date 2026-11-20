# AI_USAGE.md

Dự án Inside Airbnb Porto · Nhóm 6 · UET.DSE2049. Bản ghi này dựa trên nhật ký K7 ngày 17/11/2026, các tệp đã lưu và lần kiểm tra nhánh `main` tại commit `56a51f6` ngày 19/11/2026. [Yêu cầu của học phần](https://courses.iaidev.com/programming-for-data-processing/2627-1/projects/project_airbnb.html)

## Công cụ đã dùng (vào việc gì)

- **Codex** hỗ trợ phần K3/K4 và bản thảo tài liệu ở nhánh làm việc. Trong lần kiểm tra `main`, Codex đọc đề, chạy pipeline, so đầu ra với tiêu chí chấm và soạn bản ghi này. Phần xác minh bên dưới ghi các thao tác thực hiện bằng công cụ. Các thành viên cần tự đối chiếu phần mình đã làm trước khi nộp.
- **Mô hình `gpt-4o-mini` qua API tương thích OpenAI** tại `api.shopaikey.com` được cấu hình cho K7, prompt `v1`. K7 chọn một review cho mỗi listing được đại diện trong mẫu, với seed 42. Mô hình trả về ngôn ngữ, cảm xúc, các khía cạnh được khen/chê và dẫn chứng. K7 dùng các lời phàn nàn có dẫn chứng về môi trường xung quanh chỗ ở. [Cấu hình K7](configs/porto.yaml) · [Hàm tạo prompt và xử lý kết quả](src/llm_label.py)
- **Chi phí.** Nhật ký gốc ở cuối tài liệu lưu số lượt xử lý. Cache hiện có trường ID, kết quả, lỗi, lần thử, mô hình và phiên bản prompt. Nhóm còn cần bổ sung hóa đơn hoặc thống kê token và đơn giá của lần chạy để xác nhận chi phí mẫu và ngoại suy cho toàn Porto.

## Prompt then chốt (5–10): bước nào, vào tệp nào

Các yêu cầu dưới đây được diễn đạt lại theo mục đích. Mục 6 tóm tắt prompt thực tế gửi theo lô tới mô hình K7. Có thể đọc nguyên văn prompt tại hàm `build_prompt`.

1. **Lập trình K3/K4.** “Tính tỷ lệ nguyên căn theo khu và theo mốc. So tập ID ở hai mốc liền nhau để đếm listing mới và mất. Kiểm tra bằng trường hợp tính tay.” Bản tích hợp nằm tại [K3](src/kpi_k3_entire_home_share.py) và [K4](src/kpi_k4_supply_change.py).
2. **Viết tài liệu.** “Mô tả các cột listings, calendar, reviews, cờ QA và đầu ra KPI. Dùng số liệu mẫu để giải thích phép ngoại suy chi phí LLM.” Bước này tạo các bản thảo `reports/data_dictionary.md`, `reports/qa_kpi_methods.md` và `reports/llm_cost_porto.md` trên nhánh `dung-branch`. Chúng cần đối chiếu lại với code tích hợp trên `main`.
3. **Đối chiếu với đề chính thức.** “Tạo AI usage trên main, chạy hệ thống một lần và kiểm tra theo yêu cầu của đề bài.” Đầu vào gồm đề học phần, [README](README.md), [orchestrator](run_pipeline.py) và các tệp đã commit. Kết quả của lần chạy được ghi ở mục kiểm chứng.
4. **Rà soát mã của nhánh làm việc.** “Kiểm tra phần của tôi trước.” Nhóm chọn thêm chế độ rà soát bảo mật. Phạm vi khi đó là mã thay đổi trên `dung-branch`, gồm phần K3/K4 và cache. Kết quả của lượt đó chỉ áp dụng cho phiên bản đã kiểm tra.
5. **Soạn bản demo minh bạch AI.** “Soạn thảo demo trước cho tôi một bản AI usage.” Đầu ra là bản nháp `AI_USAGE.md` ở nhánh làm việc. Khi đó chưa có tệp dẫn chứng K7 trên nhánh này nên ví dụ còn để mở. Bản hiện tại đã đối chiếu được một ID thật trên `main`.
6. **Trích xuất nhãn từ review bằng LLM.** Với mỗi ID và văn bản sạch, trả một phần tử JSON gồm mã ngôn ngữ, cảm xúc, các khía cạnh khen/chê và dẫn chứng nguyên văn. Phân biệt vấn đề trong căn hộ với tiếng ồn, hàng xóm, vệ sinh hoặc an toàn của khu vực xung quanh. Giữ nguyên ID và thứ tự đầu vào. [Prompt K7](src/llm_label.py) · [Nhãn theo review](data/interim/k7_labels.csv) · [Dẫn chứng cần kiểm tra](data/processed/k07_evidence_review.csv)

## AI sai ở đâu (ví dụ thật)

**Dẫn chứng K7 bị cắt câu.** Với review `733857091106204293`, mô hình trả “Quite loud at night with music playing in bar/restaurant below.”. Trong văn bản gốc, ngay sau “below” là dấu phẩy rồi đến “it didn’t bother us at all”. Phép kiểm tra của K7 chuẩn hóa chữ hoa/thường và khoảng trắng nhưng giữ dấu câu, nên trích dẫn có dấu chấm trượt kiểm tra. Phần bị lược cũng cho biết khách nghe thấy tiếng ồn nhưng vẫn chấp nhận được. Pipeline đưa ID vào danh sách rà soát và loại dòng khỏi mẫu tính K7. Khi kiểm chứng lại bằng tay, cần đọc cả mệnh đề sau trước khi quyết định nhãn. [Review và dẫn chứng đặt cạnh nhau](data/processed/k07_evidence_review.csv) · [Điều kiện loại](src/kpi_k7_evidence_review.py)

**Mô hình bỏ sót ID hoặc trả khía cạnh sai danh mục.** Trong 676 lượt xử lý đã lưu, 36 lượt có lỗi `missing_in_response` và 7 lượt có lỗi `aspect`. Code lưu lỗi theo ID và cho phép thử lại. Sau khi giữ bản ghi cuối của mỗi ID, 633/635 ID có nhãn hợp lệ về cấu trúc, 2 ID còn lỗi. Con số 43 ở log là số lượt lỗi, gồm cả lần thử trước khi thành công. [Cache theo lần thử](data/interim/k7_llm_cache.jsonl) · [Bảng nhãn cuối](data/interim/k7_labels.csv)

**Bản thảo do Codex viết từng đề xuất sai ý nghĩa KPI.** Khi nhánh làm việc mới có K3/K4, bản thảo đề xuất K1 là giá trung vị và K8 là tỷ lệ review tiêu cực. Đối chiếu với `main` cho thấy K1 đo tỷ trọng nguồn cung theo khu và K8 đo độ tin cậy dữ liệu. Bản thảo cũ cần cập nhật trước khi đưa vào báo cáo nhóm. [K1 trên main](src/kpi_k1_area_share.py) · [K8 trên main](src/kpi_k8_data_reliability.py)

## Nhóm kiểm chứng thế nào

1. **Đếm lại mẫu và kiểm tra trích dẫn.** Từ kết quả đã commit, đếm được 635 ID review phân biệt trong cache. Chạy lại hàm kiểm tra dẫn chứng trên 7 ID trong tệp rà soát cho kết quả trượt 7/7. Ở mốc 21/09/2025, sau khi loại 2 nhãn sai cấu trúc và 7 dẫn chứng trượt, K7 dùng 626 review. [Báo cáo QA của K7](data/processed/kpi_k07_report.csv) · [KPI đã lưu](data/processed/kpi_k07_community_complaint.csv)
2. **Chạy từ bản sao các tệp đã commit.** Ngày 19/11/2026, chạy `python run_pipeline.py --config configs/porto.yaml` trong thư mục tạm, dùng dữ liệu trung gian đã commit và không cấp khóa API. Máy kiểm tra dùng Python 3.13.5, khác phiên bản 3.14.7 trong README. Bốn bước QA, bước tổng kiểm cờ, K1–K6 và K8 lượt đầu chạy xong. K8 ghi 19.932 dòng review theo mốc. Baseline chuyển sang bộ nhận diện ngôn ngữ dự phòng do thiếu `langdetect`, sau đó dừng vì yêu cầu cột `comments` trong khi K8 xuất `comment_clean`. Lệnh toàn trình trả mã 1. [Điểm nối giữa hai bước](run_pipeline.py) · [Bộ đọc baseline](src/baseline.py)
3. **Kiểm tra độc lập các bước phía sau.** Chạy riêng K7 với cache đã commit và không cấp khóa. Cả 635 ID cần xử lý đều có trong cache. Hàm `run_labeling` vẫn khởi tạo client và dừng khi thiếu `OPENAI_COMPAT_API_KEY`. Lần kiểm tra này không phát sinh request gán nhãn. Chạy riêng `src/viz.py` trên các CSV đã lưu tạo lại được 7 hình PNG, gồm hình K7 dùng nhãn LLM. [Mã cache](src/llm_label.py) · [Mã vẽ hình](src/viz.py)
4. **Kiểm tra cơ sở để báo cáo accuracy/F1.** Chạy riêng `src/evaluate.py` cho thấy thiếu tệp nhãn tay ở đường dẫn cấu hình. Bảng baseline đã commit có 43 dòng và số ID giao với bảng nhãn LLM bằng 0. Lệnh kết thúc mà không sinh bảng điểm. Trước khi báo cáo độ chính xác, cần gán tay ít nhất 100 review, cho cả hai phương pháp dự đoán trên cùng ID và đối chiếu các trường hợp sai. [Mã đánh giá](src/evaluate.py)

**Kiểm tra lại sau khi nhóm xác nhận mốc Porto (19/11/2026).** Nhóm cho biết mốc 25/12/2025 gặp lỗi dữ liệu và đã thay bằng 19/09/2026. Bốn mốc dùng để đối chiếu là 21/09/2025, 26/03/2026, 23/06/2026 và 19/09/2026. Chạy lệnh trong README trên hai bản sao cùng commit bằng Python 3.13.14 và 3.14.3. Sáu CSV K1–K6 và tệp `reviews_valid.csv` giống nhau từng byte giữa hai lần chạy. Số dòng review lần lượt là 5.000, 5.000, 5.000 và 4.932. Cả hai đều dừng ở baseline do đầu vào có `comment_clean` nhưng bộ đọc yêu cầu `comments`. Chưa chạy thử trên đúng Python 3.14.7.

### Nhật ký tự động của bước K7

- 2026-11-17 | openai_compat gpt-4o-mini | prompt v1 | 24 yêu cầu | 676 review | 43 lỗi
