# tên: (loại, bảng, điều kiện, lý do, hành động)
RULES_K7 = {
    # --- trên review, trước khi gắn nhãn / tính K7 ---
    "listing_no_neighbourhood": ("flag", "reviews",
        "listing_id không nối được listings gốc cùng mốc, hoặc neighbourhood_cleansed rỗng",
        "Không xếp được vào khu", "Gắn cờ, loại khỏi K7"),
    "llm_label_invalid": ("flag", "reviews",
        "LLM trả kết quả không đúng schema (không parse được JSON, nhãn ngoài danh sách cho phép)",
        "Không có nhãn dùng được", "Gắn cờ, loại khỏi K7, chạy lại một lần"),
    "llm_evidence_missing": ("flag", "reviews",
        "nhãn có phàn nàn cộng đồng nhưng câu trích làm bằng chứng không nằm trong comment_clean",
        "Nghi LLM bịa nhãn", "Gắn cờ, loại khỏi K7 và đưa vào danh sách kiểm tra tay"),

    # --- trên ô KPI (khu) ---
    "kpi_cell_small_sample": ("flag", "kpi_k07",
        "n_used của ô khu < ngưỡng tối thiểu (đề xuất 30)",
        "Tỷ lệ không ổn định", "Gắn cờ, ghi 'không đủ mẫu', để trống value"),
    "kpi_cell_no_sample": ("flag", "kpi_k07",
        "n_used = 0",
        "Không có review trong ô", "Để value trống, không điền 0"),
}

RULES_K8 = {
    # --- kiểm tra tổng thể, ra số cho K8 ---
    "snapshot_row_count_drop": ("check", "reviews",
        "số dòng của mốc sau < mốc trước",
        "Mất dòng giữa các mốc", "Báo cáo (rows_flagged = số dòng mất)"),
    "date_max_advances": ("check", "reviews",
        "ngày review lớn nhất của mốc sau < ngày mốc trước hoặc không tăng",
        "Review không cập nhật theo mốc", "Báo cáo (rows_flagged = số mốc không tăng)"),
    "listing_join_coverage": ("check", "listings",
        "listing trong file cờ không có trong listings gốc cùng mốc",
        "Không có khu để tính theo khu", "Báo cáo (rows_flagged = số listing không nối được)"),
    "listing_sample_coverage": ("check", "listings",
        "listing trong file cờ không có review nào trong mẫu LLM (không có review hợp lệ để chọn)",
        "Listing không có nhãn LLM", "Báo cáo (rows_flagged = số listing không có review trong mẫu)"),
    "label_coverage": ("check", "reviews",
        "review trong mẫu LLM chưa có nhãn LLM",
        "K7 thiếu mẫu số", "Báo cáo (rows_flagged = số review thiếu nhãn)"),
    "kpi_excluded_share": ("check", "kpi",
        "n_excluded / (n_used + n_excluded) của KPI vượt ngưỡng (đề xuất 20%)",
        "Quá nhiều dòng bị loại, KPI kém tin cậy", "Báo cáo, ghi chú trên KPI"),
}
