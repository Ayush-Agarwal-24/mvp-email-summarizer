# Contextual Email Summarizer & Action Extractor

## Stack
- FastAPI backend
- SQLite via SQLAlchemy
- Gmail API (read-only)
- Hugging Face Inference API
- Static HTML/CSS/JS frontend

## Prerequisites
- Python 3.10+
- Google Cloud project with Gmail API enabled
- OAuth consent screen in Testing with test users
- OAuth client (Web) with redirect URIs
- Hugging Face account and token

## Environment
Copy `.env.example` to `.env` and set values.

```
APP_SECRET_KEY=
OAUTH_REDIRECT_URI=http://127.0.0.1:8000/auth/google/callback
DB_URL=sqlite:///./data.db
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
HF_API_TOKEN=
ENV=local
```

## Local Run
```
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000` and connect Gmail.

## API
- GET `/api/me`
- GET `/api/emails?filter=unread|starred&limit=10`
- POST `/api/summarize` `{ "email_id": number }`


