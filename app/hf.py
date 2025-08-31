import json
import os
import httpx
from openai import OpenAI

PRIMARY_MODEL = "openai/gpt-oss-20b:together"
FALLBACK_MODEL = "openai/gpt-oss-20b:together"

def hf_openai_post(prompt: str, model: str = PRIMARY_MODEL, temperature: float = 0.2) -> str:
    api_key = os.environ.get("HF_TOKEN")
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
        return ""

def generate_with_prompt(sender: str, subject: str, body: str, prompt: str | None = None) -> tuple[str, str]:
    s = sender or ""
    sub = subject or ""
    b = body or ""
    if len(b) > 6000:
        b = b[:6000]
    default = (
        "You need to paraphrase and summarize email content. Provide 3-5 concise bullets in markdown. "
        "No URLs, links, or HTML. Remove CTAs. End with: \"Please open the mail in your mailbox to learn more\"."
    )
    if prompt and len(prompt.strip()) >= 15:
        instr = default + "\n\nAdditional instruction:\n" + prompt.strip()
    else:
        instr = default
    p = (
        "[INST]\n" + instr + "\n\nInput:\n" +
        f"Sender: {s}\nSubject: {sub}\nBody:\n<<<\n{b}\n>>>\n[/INST]"
    )
    out = hf_openai_post(p, model=PRIMARY_MODEL, temperature=0.2)
    if out.startswith(p):
        out = out[len(p):].lstrip()
    out = out.strip()
    if out:
        if out.count("Please open the mail in your mailbox to learn more") > 1:
            out = out.replace("Please open the mail in your mailbox to learn more", "", 1)
        if not out.endswith("Please open the mail in your mailbox to learn more"):
            out = (out + "\n\nPlease open the mail in your mailbox to learn more").strip()
    return out, PRIMARY_MODEL

def extract_actions_llm(sender: str, subject: str, body: str, prompt: str | None = None) -> dict:
    s = sender or ""
    sub = subject or ""
    b = body or ""
    if len(b) > 6000:
        b = b[:6000]
    default = (
        "You are an AI assistant. Extract all actionable items from the following email. "
        "Return a JSON object with three keys: 'tasks', 'meetings', and 'deadlines'. "
        "Each key should map to a list of objects with 'title' and optional 'when_text'. "
        "Be concise and do not include any unrelated information."
    )
    if prompt and len(prompt.strip()) >= 15:
        instr = default + "\n\nAdditional instruction:\n" + prompt.strip()
    else:
        instr = default
    p = (
        "[INST]\n" + instr + "\n\nInput:\n" +
        f"Sender: {s}\nSubject: {sub}\nBody:\n<<<\n{b}\n>>>\n[/INST]"
    )
    out = hf_openai_post(p, model=PRIMARY_MODEL, temperature=0.2)
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            for k in ["tasks", "meetings", "deadlines"]:
                if k not in data:
                    data[k] = []
                if isinstance(data[k], list):
                    data[k] = [
                        x if isinstance(x, dict) else {"title": str(x), "when_text": ""}
                        for x in data[k]
                    ]
            return data
    except Exception:
        pass
    return {"tasks": [], "meetings": [], "deadlines": []}
