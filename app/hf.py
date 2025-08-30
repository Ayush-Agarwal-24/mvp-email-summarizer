import json
import time
import re
import httpx
from .config import HF_API_TOKEN

SUMMARIZER = "sshleifer/distilbart-cnn-12-6"
EXTRACTOR = "google/flan-t5-small"

def hf_post(model: str, inputs: str, parameters: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    payload = {"inputs": inputs}
    if parameters:
        payload["parameters"] = parameters
    url = f"https://api-inference.huggingface.co/models/{model}"
    for i in range(2):
        r = httpx.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code in (429, 503) and i == 0:
            time.sleep(1.2)
            continue
        r.raise_for_status()
        return r.json()
    return {}

def clean_email_text(t: str) -> str:
    x = t
    x = re.sub(r"(?is)^>.*$", "", x, flags=re.M)
    x = re.sub(r"(?is)--+\s*forwarded\s*message.*", "", x)
    x = re.sub(r"(?is)^On .+ wrote:.*", "", x)
    x = re.sub(r"(?is)unsubscribe.*", "", x)
    x = re.sub(r"(?is)confidentiality notice.*", "", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x

def summarize(text: str, category: str | None = None, longer: bool = False) -> str:
    t = clean_email_text(text or "")
    n = len(t)
    if n > 4000:
        t = t[:4000]
        n = len(t)
    if longer:
        base_params = {"max_length": 340, "min_length": 120, "do_sample": False}
        bullet_hint = "Aim for 8-10 bullets."
        rewrite_tokens = 420
    else:
        if n <= 400:
            base_params = {"max_length": 90, "min_length": 25, "do_sample": False}
            bullet_hint = "Keep 3-4 bullets total."
            rewrite_tokens = 220
        elif n <= 1200:
            base_params = {"max_length": 200, "min_length": 60, "do_sample": False}
            bullet_hint = "Keep 5-6 bullets total."
            rewrite_tokens = 300
        else:
            base_params = {"max_length": 260, "min_length": 80, "do_sample": False}
            bullet_hint = "Keep 6-8 bullets total."
            rewrite_tokens = 360
    base = hf_post(SUMMARIZER, t, base_params)
    s = ""
    if isinstance(base, list) and base and "summary_text" in base[0]:
        s = base[0]["summary_text"].strip()
    cat = (category or "").strip().lower()
    if cat in {"newsletter", "notification"}:
        rewrite = (
            "Rewrite into a clear newsletter brief in bullets with sections.\n"
            "Use specific, non-redundant points; avoid greetings and subject repetition.\n"
            + bullet_hint + " Neutral, informative tone.\n"
            "Sections: Highlights, Key Updates, What Changed, Links/Actions.\n\n"
            "Email:\n<<<\n" + (text or "")[:2000] + "\n>>>\n\n"
            "Base summary:\n<<<\n" + s + "\n>>>\n"
        )
    else:
        rewrite = (
            "Rewrite the following email into a concise brief with sections.\n"
            "Use bullet points and clear headings. Do not repeat the subject.\n"
            "Sections: Summary, Key Actions, Dates/Deadlines, Decision Needed.\n"
            + bullet_hint + "\n\n"
            "Email:\n<<<\n" + (text or "")[:2000] + "\n>>>\n\n"
            "Base summary:\n<<<\n" + s + "\n>>>\n"
        )
    res = hf_post(EXTRACTOR, rewrite, {"max_new_tokens": rewrite_tokens})
    out = None
    if isinstance(res, list) and res and "generated_text" in res[0]:
        out = res[0]["generated_text"].strip()
    return (out or s or "").strip()

def extract_actions(text: str) -> dict:
    t = text.strip()
    if len(t) > 2000:
        t = t[:2000]
    prompt = (
        "You are an email assistant. Extract ACTION ITEMS from the email in strict JSON.\n\n"
        "Email:\n<<<\n" + t + "\n>>>\n\n"
        "Return JSON with keys:\n{\n  \"tasks\": [{\"title\": str}],\n  \"meetings\": [{\"title\": str, \"when_text\": str}],\n  \"deadlines\": [{\"title\": str, \"when_text\": str}]\n}\n\n"
        "Rules:\n- Titles are short imperatives.\n- when_text is a short phrase.\n- If none, use empty arrays. Output ONLY JSON."
    )
    res = hf_post(EXTRACTOR, prompt, {"max_new_tokens": 256})
    txt = ""
    if isinstance(res, list) and res and "generated_text" in res[0]:
        txt = res[0]["generated_text"].strip()
    try:
        data = json.loads(txt)
        if not isinstance(data, dict):
            raise ValueError()
    except Exception:
        data = {"tasks": [], "meetings": [], "deadlines": []}
    return data

def classify_email(text: str) -> dict:
    t = (text or "").strip()
    if len(t) > 1500:
        t = t[:1500]
    prompt = (
        "Classify the email into one primary category and optional tags from this set: "
        "meeting, task, deadline, invoice, newsletter, notification, fyi, support.\n"
        "Return strict JSON: {\"category\": str, \"tags\": [str]}\n\n"
        "Email:\n<<<\n" + t + "\n>>>"
    )
    res = hf_post(EXTRACTOR, prompt, {"max_new_tokens": 128})
    txt = ""
    if isinstance(res, list) and res and "generated_text" in res[0]:
        txt = res[0]["generated_text"].strip()
    try:
        data = json.loads(txt)
        if not isinstance(data, dict) or "category" not in data:
            raise ValueError()
        if not isinstance(data.get("tags", []), list):
            data["tags"] = []
    except Exception:
        data = {"category": "fyi", "tags": []}
    return data
