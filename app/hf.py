import json
import httpx
from .config import HF_API_TOKEN

SUMMARIZER = "sshleifer/distilbart-cnn-12-6"
EXTRACTOR = "google/flan-t5-small"

def hf_post(model: str, inputs: str, parameters: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    payload = {"inputs": inputs}
    if parameters:
        payload["parameters"] = parameters
    r = httpx.post(f"https://api-inference.huggingface.co/models/{model}", headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def summarize(text: str) -> str:
    t = text.strip()
    if len(t) > 2000:
        t = t[:2000]
    res = hf_post(SUMMARIZER, t, {"max_length": 130, "min_length": 30, "do_sample": False})
    if isinstance(res, list) and res and "summary_text" in res[0]:
        return res[0]["summary_text"].strip()
    return ""

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
