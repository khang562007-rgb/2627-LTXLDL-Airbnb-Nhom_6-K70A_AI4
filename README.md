# Thư viện sử dụng trong project

Project sử dụng Python để xử lý, lọc và kiểm tra dữ liệu Airbnb. Các thư viện bên thứ ba được dùng trong mã nguồn gồm:

| Thư viện | Phiên bản khai báo | Tác dụng trong project |
|---|---:|---|
| [NumPy](https://numpy.org/) (`numpy`) | 2.3.3 | Hỗ trợ tính toán số học và thao tác với mảng. Được dùng trong các bước gắn cờ/đặc trưng dữ liệu như vị trí host và thuộc tính listing. |
| [pandas](https://pandas.pydata.org/) (`pandas`) | 2.3.3 | Đọc, làm sạch, lọc, biến đổi và kiểm tra dữ liệu dạng bảng; là thư viện xử lý chính cho dữ liệu listing và calendar. |
| [PyArrow](https://arrow.apache.org/docs/python/) (`pyarrow`) | 26.0.0 | Cung cấp hỗ trợ định dạng Apache Arrow/Parquet và tăng tốc đọc, ghi dữ liệu cho pandas. Project có kiểm tra sự hiện diện của PyArrow làm engine cho bước xử lý calendar. |
| [PyYAML](https://pyyaml.org/) (`yaml`) | 6.0.3 | Đọc cấu hình pipeline từ các file YAML, ví dụ `configs/porto.yaml`. Tên cài đặt là `PyYAML`, còn tên import trong Python là `yaml`. |
| [Requests](https://requests.readthedocs.io/) (`requests`) | Chưa khai báo | Gửi HTTP GET để tải dữ liệu từ URL trong `src/download.py`. Thư viện này được import trong mã nguồn nhưng hiện chưa có trong `requirements.txt`; cần bổ sung vào file dependency để cài đặt đầy đủ môi trường. |

## Cài đặt

```bash
pip install -r requirements.txt
```

Lệnh trên cài các thư viện đã khai báo trong `requirements.txt`. Vì `requests` hiện chưa được liệt kê tại đó, cần cài riêng bằng `pip install requests` cho đến khi dependency này được bổ sung vào file.

Các module còn lại được import trong project như `argparse`, `json`, `pathlib` và `re` thuộc thư viện chuẩn Python, không cần cài thêm bằng pip.
