#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""baseline.py - phương pháp đối chứng KHÔNG dùng LLM cho phân tích review.

Đầu vào : CSV, CSV.GZ hoặc TSV có hai cột `review_id`, `comments`.
Đầu ra  : CSV cùng "hình dạng" với đầu ra LLM:
          review_id, language, sentiment, aspects_positive, aspects_negative
          + cột phụ: status, lang_confidence, pos_score, neg_score (phục vụ QA/phân tích lỗi).

Phương pháp (xem README): làm sạch tối thiểu -> loại review vô giá trị/tự động -> nhận diện ngôn ngữ
(langdetect, dự phòng bằng từ dừng) -> chấm điểm theo câu bằng từ điển + phủ định
-> nhãn positive/mixed/negative -> khía cạnh theo từ khóa trong mệnh đề.

Chạy:  python src/baseline.py --config configs/porto.yaml [--input ...] [--output ...] [--limit N]
Không cần khóa API. Kết quả xác định (không có yếu tố ngẫu nhiên).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import html
import importlib.util
import json
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # thư mục gốc repo
R = None                                        # module từ vựng, nạp bởi load_lexicon()

try:
    import yaml
except ImportError:  # chỉ cần khi đọc file config
    yaml = None

DEFAULTS = {
    "input_path": "data/samples/reviews_sample.csv",
    "output_path": "data/processed/baseline_reviews.csv",
    "languages": ["en", "es", "fr", "de", "pt"],
    "lexicon_path": "data/samples/baseline_lexicon.py",
    "aspects": None,                   # None = dùng DEFAULT_ASPECTS trong tệp từ vựng,
    "lang_backend": "langdetect",      # langdetect | auto | stopwords
    "min_lang_confidence": 0.5,
    "short_max_tokens": 3,             # review <= n từ: nới lỏng nhận diện ngôn ngữ
    "short_min_lang_confidence": 0.1,
    "strip_accents": False,            # Câu 10A: mặc định KHÔNG bỏ dấu
    "negation_window": 3,
    "negation_factor": -1.0,
    "mixed_min_pos": 2.0,              # Câu 7B: ngưỡng mỗi bên để gán 'mixed' (chỉnh trên tập dev)
    "mixed_min_neg": 2.0,
    "aspect_window": 6,
    "no_signal_label": None,           # None = bỏ trống (abstain); hoặc 'positive'...
    "auto_patterns_extra": [],         # regex bổ sung cho review tự động (bản địa hoá)
}

OUT_COLUMNS = ["review_id", "language", "sentiment", "aspects_positive", "aspects_negative",
               "status", "lang_confidence", "pos_score", "neg_score"]

AUTO_PATTERNS = [
    r"this is an automated posting", r"automated posting",
    r"the host canceled this reservation", r"the reservation was cancell?ed",
]

_BR = re.compile(r"<\s*br\s*/?\s*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_SENT = re.compile(r"[.!?…;]+(?:\s+|$)")
_TOK = re.compile(r"[^\W\d_]+|[,:]")
_NT = re.compile(r"n't\b")
_LETTER = re.compile(r"[^\W\d_]")


# --------------------------------------------------------------------------- cấu hình
def load_config(path):
    cfg = dict(DEFAULTS)
    if path:
        if yaml is None:
            sys.exit("Thiếu PyYAML: pip install pyyaml")
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        cfg.update(raw.get("baseline") or {})
        if "aspects" not in (raw.get("baseline") or {}) and (raw.get("llm") or {}).get("aspects"):
            cfg["aspects"] = raw["llm"]["aspects"]   # dùng chung danh sách khía cạnh với phần LLM
    return cfg


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# --------------------------------------------------------------------------- làm sạch
def clean_text(raw):
    """Câu 10A: tối thiểu = bỏ thẻ HTML + chữ thường (+ chuẩn hoá khoảng trắng; xuống dòng = ngắt câu)."""
    if raw is None:
        return ""
    s = _BR.sub(". ", str(raw))
    s = html.unescape(_TAG.sub(" ", s))
    s = s.replace("’", "'").replace("`", "'").replace("\r", " ").replace("\n", " . ")
    return re.sub(r"\s+", " ", s.lower()).strip()


# --------------------------------------------------------------------------- từ điển
def load_lexicon(path):
    """Nạp tệp từ vựng (.py) từ đường dẫn trong config, mặc định data/samples/baseline_lexicon.py."""
    global R
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        p = ROOT / p                                  # chạy từ thư mục khác vẫn tìm được
    if not p.exists():
        sys.exit(f"Không thấy tệp từ vựng: {path}")
    spec = importlib.util.spec_from_file_location("baseline_lexicon", p)
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    return R

def _split_words(text, norm):
    exact, pref = set(), []
    for w in text.split():
        w = norm(w)
        (pref.append(w[:-1]) if w.endswith("*") else exact.add(w))
    return exact, tuple(pref)


class Lexicon:
    """Từ điển cảm xúc + phủ định + từ khóa khía cạnh cho một ngôn ngữ."""

    def __init__(self, lang, aspect_keys, accents=False):
        norm = strip_accents if accents else (lambda x: x)
        self.lang, self.norm = lang, norm
        self.exact, pref = {}, []
        for key, val in (("pos2", 2.0), ("pos1", 1.0), ("neg1", -1.0), ("neg2", -2.0)):
            for w in R.SENTIMENT[lang][key].split():
                w = norm(w)
                if w.endswith("*"):
                    pref.append((w[:-1], val))
                else:
                    self.exact.setdefault(w, val)
        self.pref = sorted(pref, key=lambda x: -len(x[0]))   # tiền tố dài nhất ưu tiên
        self.neg_exact, self.neg_pref = _split_words(R.NEGATORS[lang], norm)
        self.contrast = set(norm(w) for w in R.CONTRAST[lang].split())
        self.asp = [(k,) + _split_words(R.ASPECTS[k][lang], norm) for k in aspect_keys]

    @lru_cache(maxsize=None)
    def score(self, tok):
        v = self.exact.get(tok)
        if v is not None:
            return v
        for p, val in self.pref:
            if tok.startswith(p):
                return val
        return 0.0

    @lru_cache(maxsize=None)
    def is_negator(self, tok):
        return tok in self.neg_exact or tok.startswith(self.neg_pref)

    @lru_cache(maxsize=None)
    def aspects_of(self, tok):
        return tuple(k for k, ex, pf in self.asp if tok in ex or tok.startswith(pf))


# --------------------------------------------------------------------------- nhận diện ngôn ngữ
class LangdetectDetector:
    """Nhận diện ngôn ngữ bằng gói langdetect; đặt seed để kết quả ổn định."""
    name = "langdetect"

    def __init__(self):
        from langdetect import DetectorFactory, detect_langs
        DetectorFactory.seed = 0
        self._detect = detect_langs
        self._detect("hello world")  # kiểm tra sớm gói đã cài và hoạt động

    def detect(self, text, k=5):
        try:
            res = self._detect(text)
        except Exception:  # LangDetectException: văn bản không đủ đặc trưng để nhận diện
            return [("und", 0.0)]
        return [(r.lang.split("-")[0], float(r.prob)) for r in res[:k]]


class StopwordDetector:
    """Dự phòng thô: chỉ phân biệt các ngôn ngữ đích; ngôn ngữ khác -> 'und'."""
    name = "stopwords"

    def __init__(self):
        self.sw = {l: set(R.STOPWORDS[l].split()) for l in R.LANGS}
        words = {l: " ".join(R.SENTIMENT[l].values()) for l in R.LANGS}
        self.ex = {l: _split_words(words[l], lambda x: x) for l in R.LANGS}  # (exact, prefixes)

    def detect(self, text, k=5):
        toks = _TOK.findall(_NT.sub(" not", text))
        cnt = {l: sum(t in self.sw[l] or t in self.ex[l][0] or t.startswith(self.ex[l][1]) for t in toks)
               for l in R.LANGS}
        tot = sum(cnt.values())
        if not tot:
            return [("und", 0.0)]
        return sorted(((l, c / tot) for l, c in cnt.items() if c), key=lambda x: (-x[1], R.LANGS.index(x[0])))[:k]


def get_detector(cfg, backend):
    """Mặc định dùng langdetect; 'auto' sẽ dự phòng bằng từ dừng nếu thiếu langdetect."""
    if backend in ("langdetect", "auto"):
        try:
            return LangdetectDetector()
        except Exception as e:  # noqa: BLE001
            if backend == "langdetect":
                raise RuntimeError(
                    "Không khởi tạo được langdetect. Hãy cài bằng: pip install langdetect"
                ) from e
            print(
                f"[baseline] langdetect không dùng được ({e}); dùng bộ dự phòng từ dừng",
                file=sys.stderr,
            )
    if backend in ("auto", "stopwords"):
        return StopwordDetector()
    raise ValueError(f"lang_backend không hợp lệ: {backend}")


def choose_language(cands, n_tokens, cfg):
    sup = set(cfg["languages"])
    if not cands:
        return "und", 0.0, "uncertain"
    label, p = cands[0]
    # 1. Ưu tiên xử lý review rất ngắn
    if n_tokens <= cfg["short_max_tokens"]:
        supported = [
            (lang, prob)
            for lang, prob in cands
            if lang in sup
            and prob >= cfg["short_min_lang_confidence"]
        ]
        if supported:
            best_lang, best_prob = max(
                supported,
                key=lambda x: x[1]
            )
            return best_lang, best_prob, "ok"
        # Không ép review ngắn vào ngôn ngữ không hỗ trợ
        return "und", p, "uncertain"
    # 2. Xử lý review đủ dài
    if label in sup and p >= cfg["min_lang_confidence"]:
        return label, p, "ok"
    if label not in sup and label != "und" and p >= cfg["min_lang_confidence"]:
        return label, p, "unsupported"
    return "und", p, "uncertain"

# --------------------------------------------------------------------------- chấm điểm
def split_clauses(sentence, contrast):
    """-> (tokens, clause_id). Dấu , : và từ chuyển ý ngắt mệnh đề."""
    sentence = _NT.sub(" not", sentence)
    toks, cl, cid = [], [], 0
    for m in _TOK.finditer(sentence):
        t = m.group()
        if t in (",", ":"):
            cid += 1
            continue
        toks.append(t)
        cl.append(cid)
        if t in contrast:
            cid += 1
    return toks, cl


def score_sentence(toks, cl, lex, cfg):
    w, f = cfg["negation_window"], cfg["negation_factor"]
    sc = [0.0] * len(toks)
    for i, t in enumerate(toks):
        s = lex.score(t)
        if s:
            if any(cl[j] == cl[i] and lex.is_negator(toks[j]) for j in range(max(0, i - w), i)):
                s *= f                                     # Câu 6B: phủ định trong cửa sổ -> đảo dấu
            sc[i] = s
    return sc


def analyse(text, lex, cfg):
    """-> (P, N, {khóa_khía_cạnh: [p, n]}) trên toàn review; tính theo từng câu rồi cộng gộp (Câu 5C)."""
    P = N = 0.0
    asp = {}
    aw = cfg["aspect_window"]
    for sent in _SENT.split(text):
        toks, cl = split_clauses(sent, lex.contrast)
        if not toks:
            continue
        sc = score_sentence(toks, cl, lex, cfg)
        P += sum(x for x in sc if x > 0)
        N -= sum(x for x in sc if x < 0)
        for i, t in enumerate(toks):
            for a in lex.aspects_of(t):
                p = n = 0.0
                for j in range(max(0, i - aw), min(len(toks), i + aw + 1)):
                    if cl[j] == cl[i]:
                        if sc[j] > 0:
                            p += sc[j]
                        elif sc[j] < 0:
                            n -= sc[j]
                acc = asp.setdefault(a, [0.0, 0.0])
                acc[0] += p
                acc[1] += n
    return P, N, asp


def decide_sentiment(P, N, cfg):
    """Câu 7B: mixed = có đồng thời khen và chê, mỗi bên >= ngưỡng. Trả None nếu không có tín hiệu."""
    if P == 0 and N == 0:
        return None
    if P >= cfg["mixed_min_pos"] and N >= cfg["mixed_min_neg"]:
        return "mixed"
    if P > N:
        return "positive"
    if N > P:
        return "negative"
    return "mixed"                                        # P == N > 0: bằng chứng mâu thuẫn


def is_auto(text, patterns):
    return any(p.search(text) for p in patterns)


# --------------------------------------------------------------------------- xử lý một review
def process_review(rid, raw, ctx):
    cfg = ctx["cfg"]
    row = {"review_id": rid, "language": "", "sentiment": "", "aspects_positive": "[]",
           "aspects_negative": "[]", "status": "ok", "lang_confidence": "", "pos_score": "", "neg_score": ""}
    text = clean_text(raw)
    if not text or text == ".":
        row["status"] = "excluded_empty"
        return row
    if not _LETTER.search(text):
        row["status"] = "excluded_no_letters"
        return row
    if is_auto(text, ctx["auto"]):
        row["status"] = "excluded_auto"
        return row

    n_tokens = len(_TOK.findall(_NT.sub(" not", text))) - text.count(",") - text.count(":")
    lang, conf, kind = choose_language(ctx["detector"].detect(text), n_tokens, cfg)
    row["language"], row["lang_confidence"] = lang, round(conf, 3)
    if kind == "unsupported":
        row["status"] = "unsupported_language"
        return row
    if kind == "uncertain":
        row["status"] = "language_uncertain"
        return row

    lex = ctx["lex"][lang]
    P, N, asp = analyse(strip_accents(text) if cfg["strip_accents"] else text, lex, cfg)
    row["pos_score"], row["neg_score"] = P, N
    sent = decide_sentiment(P, N, cfg)
    if sent is None:
        if n_tokens <= 1:
            row["status"] = "excluded_short_no_signal"   # A4: 1 từ không thuộc positive/negative/mixed -> loại
            return row
        row["status"] = "no_signal"
        row["sentiment"] = cfg["no_signal_label"] or ""
    else:
        row["sentiment"] = sent
    pos, neg = [], []
    for key, (p, n) in asp.items():
        label = ctx["labels"][key]
        if p > n:
            pos.append(label)
        elif n > p:
            neg.append(label)
        elif p > 0:
            pos.append(label)
            neg.append(label)
    ordered = list(ctx["labels"].values())
    row["aspects_positive"] = json.dumps(sorted(pos, key=ordered.index), ensure_ascii=False)
    row["aspects_negative"] = json.dumps(sorted(neg, key=ordered.index), ensure_ascii=False)
    return row


def build_context(cfg, backend=None):
    load_lexicon(cfg.get("lexicon_path", DEFAULTS["lexicon_path"]))
    labels = {}
    for name in (cfg.get("aspects") or R.DEFAULT_ASPECTS):
        key = R.ASPECT_KEYS.get(str(name).strip().lower()) or (name if name in R.ASPECTS else None)
        if key is None:
            print(f"[baseline] CẢNH BÁO: khía cạnh '{name}' chưa có từ khóa -> bỏ qua", file=sys.stderr)
            continue
        labels[key] = name
    unknown = [l for l in cfg["languages"] if l not in R.LANGS]
    if unknown:
        sys.exit(f"Ngôn ngữ chưa có từ điển: {unknown}")
    detector = get_detector(cfg, backend or cfg["lang_backend"])
    print(f"[baseline] Bộ nhận diện ngôn ngữ: {detector.name}", file=sys.stderr)
    return {
        "cfg": cfg, "labels": labels, "detector": detector,
        "auto": [re.compile(p) for p in AUTO_PATTERNS + list(cfg["auto_patterns_extra"])],
        "lex": {l: Lexicon(l, list(labels), cfg["strip_accents"]) for l in cfg["languages"]},
    }


def _open(path, mode, **kw):
    return gzip.open(path, mode + "t", **kw) if str(path).endswith(".gz") else open(path, mode, **kw)


def detect_delimiter(fin):
    """Nhận diện dấu phân cách từ header, ưu tiên CSV rồi TSV rồi TSV dấu chấm phẩy."""
    header = fin.readline()
    fin.seek(0)
    for delimiter in (",", "\t", ";"):
        fields = next(csv.reader([header], delimiter=delimiter), [])
        if "comments" in fields and ("review_id" in fields or "id" in fields):
            return delimiter
    return ","


def run(cfg, input_path=None, output_path=None, limit=None, backend=None):
    input_path = input_path or cfg["input_path"]
    output_path = output_path or cfg["output_path"]
    ctx = build_context(cfg, backend)
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    stats = Counter()
    target = Path(output_path)
    temporary = target.with_name(target.name + ".part")

    with _open(input_path, "r", encoding="utf-8-sig", newline="") as fin:
        delimiter = detect_delimiter(fin)
        rd = csv.DictReader(fin, delimiter=delimiter)
        if "comments" not in (rd.fieldnames or []):
            sys.exit(f"Thiếu cột 'comments' trong {input_path} (có: {rd.fieldnames})")
        id_col = "review_id" if "review_id" in rd.fieldnames else ("id" if "id" in rd.fieldnames else None)
        if id_col is None:
            sys.exit("Thiếu cột 'review_id'")

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with temporary.open("w", encoding="utf-8", newline="") as fout:
                wr = csv.DictWriter(fout, fieldnames=OUT_COLUMNS)
                wr.writeheader()
                for i, r in enumerate(rd):
                    if limit is not None and i >= limit:
                        break
                    row = process_review(r[id_col], r["comments"], ctx)
                    wr.writerow(row)
                    stats["status:" + row["status"]] += 1
                    if row["sentiment"]:
                        stats["sentiment:" + row["sentiment"]] += 1
                    if row["language"]:
                        stats["lang:" + row["language"]] += 1
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    print(f"[baseline] Đã ghi {output_path}", file=sys.stderr)
    for k in sorted(stats):
        print(f"  {k:32s} {stats[k]}", file=sys.stderr)
    return stats


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Baseline phân tích review không dùng LLM")
    ap.add_argument("--config", help="configs/<city>.yaml (đọc mục `baseline:`)")
    ap.add_argument("--input")
    ap.add_argument("--output")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--lang-backend", choices=["langdetect", "auto", "stopwords"])
    a = ap.parse_args(argv)
    run(load_config(a.config), a.input, a.output, a.limit, a.lang_backend)


if __name__ == "__main__":
    main()
