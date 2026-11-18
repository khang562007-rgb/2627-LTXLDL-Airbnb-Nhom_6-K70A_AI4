# Thư viện sử dụng trong project

Project sử dụng Python để xử lý, lọc và kiểm tra dữ liệu Airbnb. Các thư viện bên thứ ba được dùng trong mã nguồn gồm:

| Thư viện | Phiên bản khai báo | Tác dụng trong project |
|---|---:|---|
| [NumPy](https://numpy.org/) (`numpy`) | 2.3.3 | Hỗ trợ tính toán số học và thao tác với mảng. Được dùng trong các bước gắn cờ/đặc trưng dữ liệu như vị trí host và thuộc tính listing. |
| [pandas](https://pandas.pydata.org/) (`pandas`) | 2.3.3 | Đọc, làm sạch, lọc, biến đổi và kiểm tra dữ liệu dạng bảng; là thư viện xử lý chính cho dữ liệu listing và calendar. |
| [PyArrow](https://arrow.apache.org/docs/python/) (`pyarrow`) | 26.0.0 | Cung cấp hỗ trợ định dạng Apache Arrow/Parquet và tăng tốc đọc, ghi dữ liệu cho pandas. Project có kiểm tra sự hiện diện của PyArrow làm engine cho bước xử lý calendar. |
| [PyYAML](https://pyyaml.org/) (`yaml`) | 6.0.3 | Đọc cấu hình pipeline từ các file YAML, ví dụ `configs/porto.yaml`. Tên cài đặt là `PyYAML`, còn tên import trong Python là `yaml`. |
| [Requests](https://requests.readthedocs.io/) (`requests`) | 2.34.2 | Gửi HTTP GET để tải dữ liệu từ URL trong `src/download.py`. |
| [langdetect](https://pypi.org/project/langdetect/) (`langdetect`) | 1.0.9 | Nhận diện ngôn ngữ cho phương pháp baseline phân tích review trong `src/baseline.py`. |

## Cài đặt

```bash
pip install -r requirements.txt
```

Lệnh trên cài đầy đủ các thư viện bên thứ ba đã khai báo trong `requirements.txt`.

Các module còn lại được import trong project như `argparse`, `json`, `pathlib` và `re` thuộc thư viện chuẩn Python, không cần cài thêm bằng pip.
