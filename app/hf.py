import json
import time
import re
import httpx
from .config import HF_API_TOKEN

SUMMARIZER = "facebook/bart-large-cnn"
EXTRACTOR = "google/flan-t5-base"

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
    if len(t) > 3000:
        t = t[:3000]
    base = hf_post(SUMMARIZER, t, {"max_length": 1020, "min_length": 200, "do_sample": False})
    s = ""
    if isinstance(base, list) and base and "summary_text" in base[0]:
        s = base[0]["summary_text"].strip()
        s = re.sub(r"<[^>]+>", "", s)
    rewrite = (
        "Rewrite the following email into a proper detailed brief with sections.\n"
        "Use bullet points and clear headings. Do not repeat the subject.\n"
        "Sections: Summary, Key Actions, Dates/Deadlines, Decision Needed.\n"
        "Keep 5-7 bullets total.\n\n"
        "Email:\n<<<\n" + t[:10000] + "\n>>>\n\n"
        "Base summary:\n<<<\n" + s + "\n>>>\n"
    )
    res = hf_post(EXTRACTOR, rewrite, {"max_new_tokens": 840})
    out = None
    if isinstance(res, list) and res and "generated_text" in res[0]:
        out = res[0]["generated_text"].strip()
        out = re.sub(r"<[^>]+>", "", out)
    return (out or s or "").strip()

def _rules_actions(t: str) -> dict:
    tasks = []
    meetings = []
    deadlines = []
    txt = t.lower()
    sents = re.split(r"(?<=[\.!?])\s+", t)
    for s in sents:
        sl = s.lower()
        if any(k in sl for k in ["apply", "register", "subscribe", "reply", "send", "share", "review", "confirm", "approve", "submit", "sign", "pay", "follow up"]):
            tasks.append({"title": s.strip()[:140]})
        if any(k in sl for k in ["meeting", "invite", "calendar", "zoom", "google meet", "teams", "schedule", "call"]):
            m = re.search(r"(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\b\d{1,2}:\d{2}\s?(am|pm)?|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\s?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))", sl)
            wt = m.group(0) if m else ""
            meetings.append({"title": s.strip()[:140], "when_text": wt})
        if any(k in sl for k in ["by ", "eod", "cob", "deadline", "due"]):
            m = re.search(r"(by\s+[^\.;,]+|eod|cob|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\s?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))", sl)
            wt = m.group(0) if m else ""
            deadlines.append({"title": s.strip()[:140], "when_text": wt})
    return {"tasks": tasks, "meetings": meetings, "deadlines": deadlines}

def extract_actions(text: str) -> dict:
    t = clean_email_text(text or "").strip()
    if len(t) > 3500:
        t = t[:3500]
    prompt = (
        "Extract action items from the email. Return ONLY valid JSON.\n"
        "Schema: {\"tasks\":[{\"title\":str}], \"meetings\":[{\"title\":str,\"when_text\":str}], \"deadlines\":[{\"title\":str,\"when_text\":str}]}\n"
        "Targets: tasks (reply, send, share, review, confirm, approve, submit, sign, pay, follow up, apply, register),"
        " meetings (invite, schedule, call, join; include simple when_text), deadlines (due/by/EOD/COB/tomorrow/Friday).\n"
        "Email:\n<<<\n" + t + "\n>>>\n"
    )
    res = hf_post(EXTRACTOR, prompt, {"max_new_tokens": 320})
    txt = ""
    if isinstance(res, list) and res and "generated_text" in res[0]:
        txt = res[0]["generated_text"].strip()
    try:
        data = json.loads(txt)
        if not isinstance(data, dict):
            raise ValueError()
    except Exception:
        data = {"tasks": [], "meetings": [], "deadlines": []}
    rules = _rules_actions(t)
    out = {"tasks": [], "meetings": [], "deadlines": []}
    seen = set()
    for lst_key in ["tasks", "meetings", "deadlines"]:
        for x in (data.get(lst_key) or []):
            key = (lst_key, (x.get("title") or ""), (x.get("when_text") or ""))
            if key in seen:
                continue
            seen.add(key)
            out[lst_key].append(x)
        for x in (rules.get(lst_key) or []):
            key = (lst_key, (x.get("title") or ""), (x.get("when_text") or ""))
            if key in seen:
                continue
            seen.add(key)
            out[lst_key].append(x)
    return out

def classify_email(text: str) -> dict:
    t = clean_email_text(text or "").strip()
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
