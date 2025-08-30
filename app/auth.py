import secrets
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
from .config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI, GMAIL_SCOPE

router = APIRouter()

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = f"{GMAIL_SCOPE} openid email profile"

@router.get("/auth/google/login")
def google_login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    q = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return RedirectResponse(f"{AUTH_URL}?{urlencode(q)}")

@router.get("/auth/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None):
    saved = request.session.get("oauth_state")
    if not code or not state or not saved or state != saved:
        return RedirectResponse("/")
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    import httpx
    r = httpx.post(TOKEN_URL, data=data, timeout=30)
    if r.status_code != 200:
        return RedirectResponse("/")
    token = r.json()
    token["client_id"] = GOOGLE_CLIENT_ID
    token["client_secret"] = GOOGLE_CLIENT_SECRET
    request.session["token"] = token
    return RedirectResponse("/")
