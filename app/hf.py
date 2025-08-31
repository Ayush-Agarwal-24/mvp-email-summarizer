import json
import time
import re
import httpx
import os
from openai import OpenAI
from .config import HF_API_TOKEN

PRIMARY_MODEL = "openai/gpt-oss-20b:together"
FALLBACK_MODEL = "openai/gpt-oss-20b:together"

def hf_post(model: str, inputs: str, parameters: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    payload = {"inputs": inputs, "options": {"wait_for_model": True, "use_cache": True}}
    if parameters:
        payload["parameters"] = parameters
    url = f"https://api-inference.huggingface.co/models/{model}"
    for i in range(3):
        r = httpx.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code in (429, 503):
            time.sleep(1.5 * (i + 1))
            continue
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and ("error" in data or "estimated_time" in data):
            time.sleep(1.5 * (i + 1))
            continue
        return data
    return {}

def hf_openai_post(prompt: str, model: str = PRIMARY_MODEL, temperature: float = 0.2) -> str:
    api_key = os.environ.get("HF_TOKEN", HF_API_TOKEN)
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=api_key,
    )
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

def _split_sentences(t: str) -> list[str]:
    t = (t or "").strip()
    if not t:
        return []
    parts = re.split(r"(?<=[\.!?])\s+", t)
    out = []
    for p in parts:
        s = p.strip()
        if s:
            out.append(s)
    return out

def _sent_score(s: str) -> int:
    sl = s.lower()
    score = 0
    if any(k in sl for k in ["please", "need", "deadline", "due", "eod", "cob", "by ", "action", "follow up", "review", "confirm", "approve", "schedule", "call", "apply", "register"]):
        score += 2
    if re.search(r"\b\d{1,2}:\d{2}\s?(am|pm)?\b", sl):
        score += 1
    if re.search(r"\b(mon|tue|wed|thu|fri|sat|sun|today|tomorrow)\b", sl):
        score += 1
    if 40 <= len(s) <= 180:
        score += 1
    return score

def _overlap(a: str, b: str) -> float:
    aw = [w for w in re.findall(r"\w+", a.lower()) if len(w) > 2]
    bw = [w for w in re.findall(r"\w+", b.lower()) if len(w) > 2]
    if not aw or not bw:
        return 0.0
    aset = set(zip(aw, aw[1:]))
    bset = set(zip(bw, bw[1:]))
    if not bset:
        return 0.0
    inter = len(aset & bset)
    return inter / max(1, len(bset))

def _clean_after(t: str) -> str:
    x = t or ""
    x = re.sub(r"<[^>]+>", "", x)
    x = re.sub(r"https?://\S+", "", x)
    x = re.sub(r"www\.[^\s]+", "", x)
    x = re.sub(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\S*", "", x)
    x = re.sub(r"[\u200B-\u200D\uFEFF\u00AD]", "", x)
    x = re.sub(r"\b[\w\.-]+@[\w\.-]+\b", "", x)
    x = re.sub(r"(?im)^(view .*apply|click here|unsubscribe|manage preferences).*$", "", x)
    x = re.sub(r"(?i)\bview job:?\b.*", "", x)
    x = re.sub(r"(?i)apply with (resume|profile).*", "", x)
    x = re.sub(r"(?i)see all jobs on linkedin:?\s*.*", "", x)
    x = re.sub(r"[-—_]{3,}", " ", x)
    x = re.sub(r"[\u2190-\u21FF\u2600-\u27BF]", "", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x

def _clean_input_links(t: str) -> str:
    x = t or ""
    x = re.sub(r"(?im)^.*iframe.*$", "", x)
    x = re.sub(r"mailto:\S+", "", x)
    x = re.sub(r"https?://\S+", "", x)
    x = re.sub(r"www\.[^\s]+", "", x)
    x = re.sub(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\S*", "", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x

def _call(model: str, text: str, params: dict) -> str:
    try:
        resp = hf_post(model, text, params)
        if isinstance(resp, dict):
            return ""
        if isinstance(resp, list) and resp and isinstance(resp[0], dict):
            s = (resp[0].get("summary_text") or resp[0].get("generated_text") or "").strip()
            return re.sub(r"<[^>]+>", "", s)
    except Exception:
        return ""
    return ""

def _summarize_block(text: str) -> tuple[str, str]:
    s = _call(
        PRIMARY_MODEL,
        text,
        {"max_length": 200, "min_length": 80, "num_beams": 4, "no_repeat_ngram_size": 3, "length_penalty": 2.3, "do_sample": False, "early_stopping": True},
    )
    if s and _overlap(text, s) < 0.5:
        return s, PRIMARY_MODEL
    s2 = _call(
        PRIMARY_MODEL,
        text,
        {"max_length": 160, "min_length": 60, "num_beams": 4, "no_repeat_ngram_size": 3, "length_penalty": 2.5, "do_sample": False, "early_stopping": True},
    )
    if s2 and _overlap(text, s2) < 0.5:
        return s2, PRIMARY_MODEL
    f = _call(
        FALLBACK_MODEL,
        text,
        {"max_length": 200, "min_length": 80, "num_beams": 4, "no_repeat_ngram_size": 3, "length_penalty": 2.0, "do_sample": False, "early_stopping": True},
    )
    if f:
        return f, FALLBACK_MODEL
    return "", PRIMARY_MODEL

def _chunk(text: str, max_chars: int = 2800) -> list[str]:
    sents = _split_sentences(text)
    chunks = []
    cur = []
    cur_len = 0
    for s in sents:
        if cur_len + len(s) + 1 > max_chars and cur:
            chunks.append(" ".join(cur))
            cur = [s]
            cur_len = len(s) + 1
        else:
            cur.append(s)
            cur_len += len(s) + 1
    if cur:
        chunks.append(" ".join(cur))
    return chunks or [text]

def _bullets(src: str, para: str, n: int = 5) -> list[str]:
    sents = _split_sentences(para) or _split_sentences(src)
    scored = sorted(((i, s, _sent_score(s)) for i, s in enumerate(sents)), key=lambda x: (-x[2], x[0]))
    out = []
    for _, s, _sc in scored:
        s2 = _clean_after(s)
        if s2 and s2 not in out:
            out.append(s2)
        if len(out) >= n:
            break
    return out

def summarize2(text: str) -> tuple[str, str]:
    t = (text or "").strip()
    if not t:
        return "", PRIMARY_MODEL
    in_src = _clean_input_links(t)
    chunks = _chunk(in_src)
    partials = []
    used = PRIMARY_MODEL
    for c in chunks:
        s, m = _summarize_block(c)
        if s:
            partials.append(s)
            used = m
    joined = " ".join(partials) if partials else t
    final, m2 = _summarize_block(joined)
    used = m2 or used
    para_sents = _split_sentences(final)
    if len(para_sents) < 4:
        base = _split_sentences(joined)
        ext = [s for _, s, _sc in sorted(((i, s, _sent_score(s)) for i, s in enumerate(base)), key=lambda x: (-x[2], x[0]))][:5]
        final = " ".join(ext)
    final = _clean_after(final)
    bl = _bullets(t, final, 5)
    out = final
    if bl:
        out = final + "\n\n" + "\n".join(["- " + b for b in bl])
    out = _clean_after(out)
    out = (out + "\n\nPlease open the mail in your mailbox to learn more").strip()
    return out, used

def summarize(text: str) -> str:
    s, _ = summarize2(text)
    return s

def clean_email_text(t: str) -> str:
    x = t or ""
    x = re.sub(r"\s+", " ", x).strip()
    return x

def generate_with_prompt(sender: str, subject: str, body: str, prompt: str | None = None) -> tuple[str, str]:
    s = sender or ""
    sub = subject or ""
    b = body or ""
    if len(b) > 6000:
        b = b[:6000]
    b_clean = _clean_input_links(b)
    default = (
        "You need to paraphrase and summarize email content. Provide 3-5 concise bullets. "
        "No URLs, links, or HTML. Remove CTAs. End with: \"Please open the mail in your mailbox to learn more\"."
    )
    if prompt and len(prompt.strip()) >= 15:
        instr = default + "\n\nAdditional instruction:\n" + prompt.strip()
    else:
        instr = default
    p = (
        "[INST]\n" + instr + "\n\nInput:\n" +
        f"Sender: {s}\nSubject: {sub}\nBody:\n<<<\n{b_clean}\n>>>\n[/INST]"
    )
    out = hf_openai_post(
        p,
        model=PRIMARY_MODEL,
        temperature=0.2
    )
    if out.startswith(p):
        out = out[len(p):].lstrip()
    out = _clean_after(out)
    if out:
        ov = _overlap(b_clean, out)
        if ov > 0.6:
            out2 = hf_openai_post(
                p,
                model=PRIMARY_MODEL,
                temperature=0.1
            )
            if out2.startswith(p):
                out2 = out2[len(p):].lstrip()
            out2 = _clean_after(out2)
            if out2:
                out = out2
    if not out:
        sents = _split_sentences(b_clean)
        scored = sorted(((i, x, _sent_score(x)) for i, x in enumerate(sents)), key=lambda y: (-y[2], y[0]))
        top = [x for _, x, sc in scored if sc > 0][:5] or sents[:5]
        para = _clean_after(" ".join(top[:5]))
        blines = ["- " + _clean_after(x) for x in top[:5] if _clean_after(x)]
        out = (para + ("\n\n" + "\n".join(blines) if blines else "")).strip()
    if out and not out.endswith("learn more"):
        out = (out + "\n\nPlease open the mail in your mailbox to learn more").strip()
    return out, PRIMARY_MODEL

def summarize_bart(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) > 3500:
        t = t[:3500]
    try:
        resp = hf_post("facebook/bart-large-cnn", t, {"max_length": 160, "min_length": 50, "num_beams": 4, "no_repeat_ngram_size": 3, "length_penalty": 2.0, "do_sample": False})
        if isinstance(resp, list) and resp and isinstance(resp[0], dict):
            s = (resp[0].get("summary_text") or resp[0].get("generated_text") or "").strip()
            s = re.sub(r"<[^>]+>", "", s)
            s = _clean_after(s)
            return s
    except Exception:
        return ""
    return ""

def _rules_actions(t: str) -> dict:
    tasks = []
    meetings = []
    deadlines = []
    sents = re.split(r"(?<=[\.!?])\s+", t or "")
    for s in sents:
        sl = s.lower()
        if any(k in sl for k in ["apply", "register", "subscribe", "reply", "respond", "send", "share", "review", "confirm", "approve", "submit", "sign", "pay", "follow up"]):
            tasks.append({"title": s.strip()[:140]})
        if any(k in sl for k in ["meeting", "invite", "calendar", "zoom", "google meet", "teams", "schedule", "call", "join"]):
            m = re.search(r"(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\b\d{1,2}:\d{2}\s?(am|pm)?|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\s?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))", sl)
            wt = m.group(0) if m else ""
            meetings.append({"title": s.strip()[:140], "when_text": wt})
        if any(k in sl for k in [" by ", "eod", "cob", "deadline", "due"]):
            m = re.search(r"(by\s+[^\.;,]+|eod|cob|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\s?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))", sl)
            wt = m.group(0) if m else ""
            deadlines.append({"title": s.strip()[:140], "when_text": wt})
    return {"tasks": tasks, "meetings": meetings, "deadlines": deadlines}

def extract_actions(text: str) -> dict:
    t = (text or "").strip()
    if len(t) > 3500:
        t = t[:3500]
    return _rules_actions(t)

def classify_email(text: str) -> dict:
    tl = (text or "").strip().lower()
    if any(k in tl for k in ["invoice", "payment", "receipt"]):
        return {"category": "invoice", "tags": []}
    if any(k in tl for k in ["meeting", "call", "schedule", "invite", "calendar"]):
        return {"category": "meeting", "tags": []}
    if any(k in tl for k in ["deadline", "due", "eod", "cob", "by "]):
        return {"category": "deadline", "tags": []}
    if any(k in tl for k in ["unsubscribe", "newsletter"]):
        return {"category": "newsletter", "tags": []}
    if any(k in tl for k in ["support", "help", "ticket"]):
        return {"category": "support", "tags": []}
    return {"category": "fyi", "tags": []}
