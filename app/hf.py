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

def summarize(text: str) -> str:
    t = clean_email_text(text or "")
    if len(t) > 2000:
        t = t[:2000]
    base = hf_post(SUMMARIZER, t, {"max_length": 150, "min_length": 40, "do_sample": False})
    s = ""
    if isinstance(base, list) and base and "summary_text" in base[0]:
        s = base[0]["summary_text"].strip()
    prompt = (
        "Rewrite the following email into a concise brief with sections.\n"
        "Use short bullet points and clear headings.\n"
        "Sections: Summary, Key Actions, Dates/Deadlines, Decision Needed.\n"
        "Keep 5 bullets max in total.\n\n"
        "Email:\n<<<\n" + (text or "")[:2000] + "\n>>>\n\n"
        "Base summary:\n<<<\n" + s + "\n>>>\n"
    )
    res = hf_post(EXTRACTOR, prompt, {"max_new_tokens": 256})
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
