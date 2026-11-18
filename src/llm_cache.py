import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "processed" / "llm_cache.jsonl"   # đổi bằng use_cache_file() khi cần
_cache = None   # dict trong bộ nhớ: khoá -> kết quả; nạp từ file ở lần dùng đầu tiên


def use_cache_file(path):
    """Đổi file cache (dùng khi test) và buộc nạp lại từ file mới."""
    global CACHE_PATH, _cache
    CACHE_PATH = Path(path)
    _cache = None


def make_key(review_id, comment, model, prompt_version):
    """Khoá cache: đổi nội dung review, mô hình hay prompt thì khoá đổi, không dùng nhầm kết quả cũ."""
    raw = f"{model}|{prompt_version}|{review_id}|{comment}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load():
    """Đọc toàn bộ file cache vào bộ nhớ một lần. Dòng hỏng (do bị ngắt giữa chừng) thì bỏ qua."""
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    _cache[row["key"]] = row["value"]
                except (json.JSONDecodeError, KeyError):
                    continue
    return _cache


def cache_get(key):
    """Trả về kết quả đã lưu theo khoá, hoặc None nếu chưa có."""
    return _load().get(key)


def cache_set(key, value):
    """Lưu kết quả: cập nhật bộ nhớ và GHI NGAY vào file, để ngắt giữa chừng cũng không mất gì."""
    _load()[key] = value
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")


def load_dotenv_simple(path=None):
    """Đọc file .env dạng TEN=gia_tri (nếu có) vào biến môi trường; biến đã có sẵn thì giữ nguyên."""
    path = Path(path) if path else ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def get_api_key(var="GEMINI_API_KEY"):
    """Đọc khoá API từ biến môi trường (hoặc .env); thiếu thì báo lỗi rõ ràng, không tự bịa khoá."""
    load_dotenv_simple()
    key = os.environ.get(var)
    if not key:
        raise RuntimeError(
            f"Chưa có khoá API: đặt biến môi trường {var} (xem .env.example), "
            "hoặc chạy với --skip-llm để chỉ dùng cache."
        )
    return key


def call_with_cache(key, call_fn, skip_llm=False, refresh=False):
    """Lấy kết quả theo thứ tự: cache -> (nếu được phép) gọi API -> lưu cache.

    skip_llm=True : không bao giờ gọi API; chưa có trong cache thì trả None (người gọi đếm là "thiếu").
    refresh=True  : bỏ qua cache cũ, gọi API lại (dùng khi muốn chứng minh LLM chạy với khoá khác).
    call_fn       : hàm không tham số, thực sự gọi API và trả về kết quả (ví dụ dict JSON).
    """
    if not refresh:
        hit = cache_get(key)
        if hit is not None:
            return hit
    if skip_llm:
        return None
    value = call_fn()
    cache_set(key, value)
    return value