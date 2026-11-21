"""Gắn nhãn LLM cho K7: cảm xúc, khía cạnh khen/chê, ngôn ngữ. Có cache, chạy tiếp được sau khi dừng."""
import hashlib
import json
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd

SENTIMENTS = {"positive", "mixed", "negative"}
POLARITIES = {"praise", "criticism"}
ASPECT_HELP = {
    "noise": "noise coming from OUTSIDE the unit: street, bars, construction, neighbours",
    "neighbours": "other residents or other guests in the building disturbing the guest",
    "area_hygiene": "rubbish, smell, dirty streets/stairwells/common areas around the unit",
    "safety": "crime, theft, feeling unsafe, dangerous area",
    "location": "position, access, transport, things nearby",
    "unit_cleanliness": "cleanliness INSIDE the unit",
    "host": "host communication, check-in, service",
    "value": "price versus quality",
    "amenities": "facilities and equipment inside the unit (wifi, AC, kitchen...)",
    "accuracy": "listing description versus reality",
    "other": "anything else",
}


def build_prompt(batch, aspects):
    lines = "\n".join(f"- {a}: {ASPECT_HELP.get(a, a)}" for a in aspects)
    return f"""You analyse short guest reviews of short-term rental listings. Reviews can be in any language.
Return ONLY a JSON array with one object per review, in the same order, with keys:
  "id": the review id exactly as given,
  "language": ISO 639-1 code of the review text,
  "sentiment": one of positive | mixed | negative,
  "aspects": list of {{"aspect": <one of the allowed aspects>, "polarity": "praise" | "criticism", "evidence": <short quote copied word for word from the review>}}.
Allowed aspects:
{lines}
Rules:
- Aspects about the surroundings OUTSIDE the unit (noise, neighbours, area_hygiene, safety) must not be used for problems inside the apartment or with the host.
- evidence must be copied verbatim, in the original language of the review.
- If the review praises or criticises nothing, use an empty list.
REVIEWS:
{json.dumps(batch, ensure_ascii=False)}"""


# ---------------- clients ----------------
def gemini_call(model, api_key, temperature):
    """Google Gemini client wrapper."""
    try:
        from google import genai
        from google.genai import types
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Thiếu package google-genai. Cài đặt bằng: pip install google-genai"
        ) from exc

    client = genai.Client(api_key=api_key)

    def call(prompt):
        config = types.GenerateContentConfig(
            temperature=float(temperature) if temperature is not None else 0.0,
            response_mime_type="application/json",
        )
        r = client.models.generate_content(model=model, contents=prompt, config=config)
        return r.text

    return call


# def mock_call(prompt):
#     """CHỈ ĐỂ THỬ LUỒNG, không phải kết quả thật."""
#     batch = json.loads(prompt.split("REVIEWS:\n", 1)[1])
#     keys = {"noise": ["noise", "noisy", "loud"], "neighbours": ["neighbour", "neighbor"],
#             "area_hygiene": ["trash", "garbage", "smell"], "safety": ["unsafe", "theft", "dangerous"]}
#     out = []
#     for r in batch:
#         h = int(hashlib.md5(r["id"].encode()).hexdigest(), 16) % 100
#         if h < 2:
#             out.append({"id": r["id"], "sentiment": "???"})
#             continue
#         t, asp = r["text"].lower(), []
#         for a, ks in keys.items():
#             for k in ks:
#                 i = t.find(k)
#                 if i >= 0:
#                     ev = r["text"][max(0, i - 10): i + len(k) + 10] if h > 5 else "fabricated quote"
#                     asp.append({"aspect": a, "polarity": "criticism", "evidence": ev})
#                     break
#         out.append({"id": r["id"], "language": "en", "sentiment": "negative" if asp else "positive", "aspects": asp})
#     return json.dumps(out)


def openai_compat_call(lc, api_key):
    """Nhà cung cấp dùng giao diện giống OpenAI (xAI Grok, Groq, OpenRouter, ...)."""
    import requests
    url = lc["base_url"].rstrip("/") + "/chat/completions"

    def call(prompt):
        payload = {"model": lc["model"], "messages": [{"role": "user", "content": prompt}]}
        if lc.get("temperature") is not None:      # đặt temperature: null nếu model từ chối tham số này
            payload["temperature"] = lc["temperature"]
        r = requests.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload,
                          timeout=lc.get("timeout_s", 180))
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]
    return call


def make_call(lc):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    env = lc.get("api_key_env", "GEMINI_API_KEY")
    key = os.environ.get(env)
    if not key:
        raise RuntimeError(f"Chưa đặt biến môi trường {env}")
    if lc["provider"] == "openai_compat":
        return openai_compat_call(lc, key)
    return gemini_call(lc["model"], key, lc.get("temperature", 0))


# ---------------- parse / validate ----------------
def parse(text):
    a, b = text.find("["), text.rfind("]")
    return json.loads(text[a:b + 1])


def validate(item, allowed):
    if not isinstance(item, dict):
        return None, "not_object"
    sent, lang = item.get("sentiment"), item.get("language")
    if sent not in SENTIMENTS:
        return None, f"sentiment:{sent}"
    if not isinstance(lang, str) or not lang.strip():
        return None, "language"
    asp = []
    for a in item.get("aspects") or []:
        if not isinstance(a, dict) or a.get("aspect") not in allowed or a.get("polarity") not in POLARITIES:
            return None, "aspect"
        asp.append({"aspect": a["aspect"], "polarity": a["polarity"], "evidence": str(a.get("evidence") or "")})
    return {"language": lang.strip().lower(), "sentiment": sent, "aspects": asp}, ""


# ---------------- cache ----------------
def load_cache(path):
    cache = {}
    if Path(path).exists():
        for line in open(path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                cache[r["id"]] = r          # dòng sau ghi đè dòng trước
    return cache


def append_cache(path, rec):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------- chạy ----------------
def run_labeling(df, cfg, skip_llm=False):
    """df: cột id, comment_clean (đã bỏ trùng id). Trả về DataFrame nhãn."""
    k7 = cfg["kpi"]["k7"]
    lc = k7["llm"]
    allowed = list(k7["aspects"]["community"]) + list(k7["aspects"]["other"])
    community = set(k7["aspects"]["community"])
    cache_path = Path(lc["cache_path"])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache(cache_path)
    call = None
    stats = {"requests": 0, "reviews": 0, "failed": 0}
    texts = dict(zip(df["id"].astype(str), df["comment_clean"].fillna("")))

    def process(ids):
        nonlocal call
        if not ids:
            return True
        if call is None:
            call = make_call(lc)
        bs, maxreq = lc["batch_size"], lc.get("max_requests_per_run", 10**9)
        for i in range(0, len(ids), bs):
            if stats["requests"] >= maxreq:
                print(f"Dừng: đủ {maxreq} yêu cầu cho lần chạy này, chạy lại để làm tiếp")
                return False
            chunk = ids[i:i + bs]
            prompt = build_prompt([{"id": x, "text": texts[x]} for x in chunk], allowed)
            for attempt in range(5):
                try:
                    stats["requests"] += 1
                    resp = call(prompt)
                    break
                except Exception as e:           # lỗi API: không ghi nhãn giả vào cache
                    msg = str(e)
                    daily = "perday" in msg.lower().replace(" ", "").replace("_", "") or "requests per day" in msg.lower()
                    if daily or attempt == 4:    # hết hạn mức ngày: thử lại vô ích
                        print(f"Dừng vì lỗi API: {msg[:400]}")
                        return False
                    time.sleep(lc.get("retry_sleep_s", 20) * (attempt + 1))
            try:
                items = {str(it.get("id")): it for it in parse(resp) if isinstance(it, dict)}
            except Exception:
                items = {}
            for x in chunk:
                res, err = validate(items.get(x), allowed) if x in items else (None, "missing_in_response")
                prev = cache.get(x, {}).get("attempt", 0)
                rec = {"id": x, "ok": res is not None, "result": res, "error": err, "attempt": prev + 1,
                       "model": lc["model"], "prompt_version": lc["prompt_version"]}
                cache[x] = rec
                append_cache(cache_path, rec)
                stats["reviews"] += 1
                stats["failed"] += res is None
            time.sleep(lc.get("sleep_s", 4))
        return True

    ids = list(texts)
    if skip_llm:
        missing = set(ids).difference(cache)
        if missing:
            raise ValueError(f"Cache thiếu {len(missing)}/{len(ids)} ID của mẫu K7. Hãy bổ sung nhãn trước khi tính.")
    else:
        if process([x for x in ids if x not in cache]):                       # lần 1
            process([x for x in ids if x in cache and not cache[x]["ok"] and cache[x]["attempt"] < 2])   # chạy lại 1 lần

    if stats["requests"]:
        log = lc.get("usage_log")
        if log:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(f"- {date.today()} | {lc['provider']} {lc['model']} | prompt {lc['prompt_version']} | "
                         f"{stats['requests']} yêu cầu | {stats['reviews']} review | {stats['failed']} lỗi\n")
    rows = []
    for x in ids:
        r = cache.get(x)
        if r is None:
            continue
        if not r["ok"]:
            rows.append(dict(id=int(x), sentiment="", language="", aspects_praised="", aspects_criticized="",
                             evidence="", label_valid=False, error=r["error"]))
            continue
        a = r["result"]["aspects"]
        crit = [t for t in a if t["polarity"] == "criticism"]
        rows.append(dict(
            id=int(x), sentiment=r["result"]["sentiment"], language=r["result"]["language"],
            aspects_praised=";".join(sorted({t["aspect"] for t in a if t["polarity"] == "praise"})),
            aspects_criticized=";".join(sorted({t["aspect"] for t in crit})),
            evidence=" | ".join(t["evidence"] for t in crit if t["aspect"] in community and t["evidence"]),
            label_valid=True, error=""))
    out = pd.DataFrame(rows, columns=["id", "sentiment", "language", "aspects_praised", "aspects_criticized",
                                      "evidence", "label_valid", "error"])
    Path(lc["labels_path"]).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(lc["labels_path"], index=False, encoding="utf-8")
    print(f"LLM: {stats['requests']} yêu cầu, {stats['reviews']} review mới, {stats['failed']} lỗi; "
          f"{len(out)}/{len(ids)} review có nhãn trong cache")
    return out


def handlabel_sample(df, area_col, n, seed, path):
    """Mẫu để gán nhãn tay (mù: không có kết quả LLM). Phân tầng theo khu."""
    df = df[df[area_col].notna()]
    shuffled = df.sample(frac=1, random_state=seed)
    # Mỗi lượt lấy một review từ mỗi khu còn dữ liệu, cho tới khi đủ n.
    position = shuffled.groupby(area_col).cumcount()
    sample = shuffled.loc[position.sort_values(kind="stable").index].head(n)
    s = sample[["id", "listing_id", area_col, "comment_clean"]].assign(
        hand_language="", hand_sentiment="", hand_community_complaint="")
    s.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Mẫu gán tay: {len(s)} review -> {path}")