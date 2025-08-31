import json
import os
from openai import OpenAI

PRIMARY_MODEL = "gpt-3.5-turbo"
FALLBACK_MODEL = "gpt-3.5-turbo"

def hf_openai_post(prompt: str, model: str = PRIMARY_MODEL, temperature: float = 0.2) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
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
        "You are an expert email assistant. Carefully read the email and extract all possible actionable items, tasks, deadlines, meetings, contacts, links, phone numbers, locations, and follow-ups. "
        "Infer tasks and deadlines even if they are implied or require interpretation. "
        "If the email is a job alert, extract each job as a task. If there are dates, treat them as deadlines. "
        "Return a JSON object with these keys: 'tasks', 'meetings', 'deadlines', 'contacts', 'links', 'phone_numbers', 'locations', 'follow_ups'. "
        "Each key should map to a list of objects with 'title' and optional 'when_text' or 'value' as appropriate. "
        "Do not leave any key empty if you can infer any actionable item. "
        "The output must be valid JSON. Example:\n"
        "{\n"
        "  \"tasks\": [{\"title\": \"Apply for job\", \"when_text\": \"by Friday\"}],\n"
        "  \"meetings\": [{\"title\": \"Team sync\", \"when_text\": \"Monday 10am\"}],\n"
        "  \"deadlines\": [{\"title\": \"Submit report\", \"when_text\": \"2025-09-01\"}],\n"
        "  \"contacts\": [{\"title\": \"John Doe\", \"value\": \"john@example.com\"}],\n"
        "  \"links\": [{\"title\": \"Job posting\", \"value\": \"https://example.com/job\"}],\n"
        "  \"phone_numbers\": [{\"title\": \"HR\", \"value\": \"+1-555-1234\"}],\n"
        "  \"locations\": [{\"title\": \"Office\", \"value\": \"123 Main St\"}],\n"
        "  \"follow_ups\": [{\"title\": \"Check with manager\", \"when_text\": \"next week\"}]\n"
        "}"
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
        if not out or not isinstance(out, str):
            print("EXTRACT ACTIONS: LLM response is empty or not a string")
            return {k: [] for k in ["tasks", "meetings", "deadlines", "contacts", "links", "phone_numbers", "locations", "follow_ups"]}
        data = json.loads(out)
        if isinstance(data, dict):
            for k in ["tasks", "meetings", "deadlines", "contacts", "links", "phone_numbers", "locations", "follow_ups"]:
                if k not in data:
                    data[k] = []
                if isinstance(data[k], list):
                    data[k] = [
                        x if isinstance(x, dict) else {"title": str(x), "when_text": "" if k in ["tasks", "meetings", "deadlines", "follow_ups"] else "", "value": str(x) if k in ["contacts", "links", "phone_numbers", "locations"] else ""}
                        for x in data[k]
                    ]
            return data
    except Exception as e:
        print(f"EXTRACT ACTIONS JSON ERROR: {e}")
        import re
        match = re.search(r"\{.*\}", out, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    for k in ["tasks", "meetings", "deadlines", "contacts", "links", "phone_numbers", "locations", "follow_ups"]:
                        if k not in data:
                            data[k] = []
                        if isinstance(data[k], list):
                            data[k] = [
                                x if isinstance(x, dict) else {"title": str(x), "when_text": "" if k in ["tasks", "meetings", "deadlines", "follow_ups"] else "", "value": str(x) if k in ["contacts", "links", "phone_numbers", "locations"] else ""}
                                for x in data[k]
                            ]
                    return data
            except Exception as e2:
                print(f"EXTRACT ACTIONS JSON SUBSTRING ERROR: {e2}")
    return {k: [] for k in ["tasks", "meetings", "deadlines", "contacts", "links", "phone_numbers", "locations", "follow_ups"]}
