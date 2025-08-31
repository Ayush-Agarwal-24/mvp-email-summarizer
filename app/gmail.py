import base64
from datetime import datetime
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from .config import GMAIL_SCOPE as _GMAIL_SCOPE

GMAIL_SCOPE = [_GMAIL_SCOPE]

def creds_from_session_token(token: dict) -> Credentials:
    return Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token.get("client_id"),
        client_secret=token.get("client_secret"),
        scopes=GMAIL_SCOPE,
    )

def gmail_service(creds: Credentials):
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

def extract_plain(payload) -> Optional[str]:
    if not payload:
        return None
    out = []
    def walk(p):
        mime = p.get("mimeType")
        data = p.get("body", {}).get("data")
        parts = p.get("parts")
        if mime == "text/plain" and data:
            try:
                out.append(base64.urlsafe_b64decode(data.encode()).decode(errors="ignore"))
            except Exception:
                pass
        elif mime == "text/html" and data:
            try:
                html = base64.urlsafe_b64decode(data.encode()).decode(errors="ignore")
                out.append(BeautifulSoup(html, "html.parser").get_text(" "))
            except Exception:
                pass
        if parts:
            for pp in parts:
                walk(pp)
    walk(payload)
    if not out:
        return None
    txt = "\n\n".join([x for x in out if x and x.strip()])
    return txt or None

def gmail_link(message_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{message_id}"

def parse_received(internal_date: Optional[str]) -> Optional[datetime]:
    if not internal_date:
        return None
    try:
        return datetime.fromtimestamp(int(internal_date) / 1000)
    except Exception:
        return None
