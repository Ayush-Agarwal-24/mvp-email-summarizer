from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from .session import add_session
from .db import SessionLocal, engine
from .models import Base, User, Email, Summary, Action
from .schemas import SummarizeRequest, EmailOut, SummaryOut, GenTestRequest
from .auth import router as auth_router
from .gmail import creds_from_session_token, gmail_service, extract_plain, gmail_link, parse_received
from .hf import generate_with_prompt, extract_actions_llm
import json
import traceback

Base.metadata.create_all(bind=engine)

app = FastAPI()
add_session(app)
app.include_router(auth_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def dashboard():
    return FileResponse("static/index.html")

@app.get("/api/me")
def me(request: Request):
    token = request.session.get("token")
    if not token:
        return {"connected": False}
    try:
        creds = creds_from_session_token(token)
        svc = gmail_service(creds)
        profile = svc.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress")
        return {"connected": True, "email": email}
    except Exception:
        return {"connected": False}

@app.get("/api/emails")
def list_emails(request: Request, filter: str = "unread", category: str | None = None, limit: int = 10, db: Session = Depends(get_db)):
    token = request.session.get("token")
    if not token:
        return []
    try:
        creds = creds_from_session_token(token)
        svc = gmail_service(creds)
        label_ids = ["INBOX"]
        if filter == "unread":
            label_ids.append("UNREAD")
        if filter == "starred":
            label_ids.append("STARRED")
        cat_map = {
            "primary": "CATEGORY_PERSONAL",
            "social": "CATEGORY_SOCIAL",
            "promotions": "CATEGORY_PROMOTIONS",
            "updates": "CATEGORY_UPDATES",
            "forums": "CATEGORY_FORUMS",
        }
        if category and category.lower() in cat_map:
            label_ids.append(cat_map[category.lower()])
        msgs = svc.users().messages().list(userId="me", labelIds=label_ids, maxResults=limit).execute().get("messages", [])
        out = []
        profile = svc.users().getProfile(userId="me").execute()
        sub = profile.get("emailAddress")
        user = db.query(User).filter_by(google_sub=sub).first()
        if not user:
            user = User(google_sub=sub, email=sub)
            db.add(user)
            db.commit()
            db.refresh(user)
        for m in msgs:
            mid = m.get("id")
            full = svc.users().messages().get(userId="me", id=mid, format="full").execute()
            payload = full.get("payload")
            headers = payload.get("headers", []) if payload else []
            def h(name):
                for x in headers:
                    if x.get("name") == name:
                        return x.get("value")
                return None
            sender = h("From")
            subject = h("Subject")
            body = extract_plain(payload) or ""
            snippet = full.get("snippet") or body[:160]
            internal = full.get("internalDate")
            received = parse_received(internal)
            thread_id = full.get("threadId") or ""
            gmail_url = gmail_link(mid)
            existing = db.query(Email).filter_by(message_id=mid).first()
            if not existing:
                rec = Email(user_id=user.id, message_id=mid, thread_id=thread_id, sender=sender, subject=subject, snippet=snippet, body_text=body, received_at=received, gmail_url=gmail_url)
                db.add(rec)
                db.commit()
                db.refresh(rec)
                out.append(rec)
            else:
                out.append(existing)
        return [EmailOut.from_orm(r).dict() for r in out]
    except Exception:
        return []

@app.post("/api/summarize")
def do_summarize(req: SummarizeRequest, db: Session = Depends(get_db)) -> SummaryOut:
    email = db.query(Email).filter_by(id=req.email_id).first()
    if not email:
        raise HTTPException(status_code=404)
    existing = db.query(Summary).filter_by(email_id=email.id).first()
    src = email.body_text or email.snippet or ""
    try:
        s, model = generate_with_prompt(email.sender or "", email.subject or "", src, req.prompt)
    except Exception:
        traceback.print_exc()
        s, model = "", ""
    model = model or PRIMARY_MODEL
    if existing:
        existing.summary_text = s
        existing.actions_json = None
        existing.model_name = model
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return SummaryOut.from_orm(existing)
    rec = Summary(email_id=email.id, summary_text=s, actions_json=None, model_name=model, created_at=datetime.utcnow())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return SummaryOut.from_orm(rec)

@app.post("/api/summarize_all")
def summarize_all(request: Request, db: Session = Depends(get_db)):
    token = request.session.get("token")
    if not token:
        raise HTTPException(status_code=401)
    user = None
    try:
        creds = creds_from_session_token(token)
        svc = gmail_service(creds)
        profile = svc.users().getProfile(userId="me").execute()
        sub = profile.get("emailAddress")
        user = db.query(User).filter_by(google_sub=sub).first()
        if not user:
            raise HTTPException(status_code=401)
        emails = db.query(Email).filter_by(user_id=user.id).order_by(Email.received_at.desc()).limit(10).all()
        results = []
        for email in emails:
            src = email.body_text or email.snippet or ""
            s, model = generate_with_prompt(email.sender or "", email.subject or "", src, None)
            existing = db.query(Summary).filter_by(email_id=email.id).first()
            if existing:
                existing.summary_text = s
                existing.actions_json = None
                existing.model_name = model
                existing.created_at = datetime.utcnow()
                db.commit()
                db.refresh(existing)
                results.append(SummaryOut.from_orm(existing).dict())
            else:
                rec = Summary(email_id=email.id, summary_text=s, actions_json=None, model_name=model, created_at=datetime.utcnow())
                db.add(rec)
                db.commit()
                db.refresh(rec)
                results.append(SummaryOut.from_orm(rec).dict())
        return results
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract_actions")
def extract_actions_api(req: SummarizeRequest, db: Session = Depends(get_db)):
    email = db.query(Email).filter_by(id=req.email_id).first()
    if not email:
        raise HTTPException(status_code=404)
    src = email.body_text or email.snippet or ""
    try:
        actions = extract_actions_llm(email.sender or "", email.subject or "", src, req.prompt)
    except Exception:
        traceback.print_exc()
        actions = {"tasks": [], "meetings": [], "deadlines": []}
    db.query(Action).filter_by(email_id=email.id).delete()
    for t in actions.get("tasks", []):
        db.add(Action(email_id=email.id, type="task", title=t.get("title", ""), when_datetime=None, status="open", snooze_until=None))
    for m in actions.get("meetings", []):
        db.add(Action(email_id=email.id, type="meeting", title=m.get("title", ""), when_datetime=None, status="open", snooze_until=None))
    for d in actions.get("deadlines", []):
        db.add(Action(email_id=email.id, type="deadline", title=d.get("title", ""), when_datetime=None, status="open", snooze_until=None))
    db.commit()
    return actions

@app.post("/api/extract_all")
def extract_all_actions(request: Request, db: Session = Depends(get_db)):
    token = request.session.get("token")
    if not token:
        raise HTTPException(status_code=401)
    user = None
    try:
        creds = creds_from_session_token(token)
        svc = gmail_service(creds)
        profile = svc.users().getProfile(userId="me").execute()
        sub = profile.get("emailAddress")
        user = db.query(User).filter_by(google_sub=sub).first()
        if not user:
            raise HTTPException(status_code=401)
        emails = db.query(Email).filter_by(user_id=user.id).order_by(Email.received_at.desc()).limit(10).all()
        results = []
        for email in emails:
            src = email.body_text or email.snippet or ""
            try:
                actions = extract_actions_llm(email.sender or "", email.subject or "", src, None)
            except Exception:
                actions = {"tasks": [], "meetings": [], "deadlines": []}
            db.query(Action).filter_by(email_id=email.id).delete()
            for t in actions.get("tasks", []):
                db.add(Action(email_id=email.id, type="task", title=t.get("title", ""), when_datetime=None, status="open", snooze_until=None))
            for m in actions.get("meetings", []):
                db.add(Action(email_id=email.id, type="meeting", title=m.get("title", ""), when_datetime=None, status="open", snooze_until=None))
            for d in actions.get("deadlines", []):
                db.add(Action(email_id=email.id, type="deadline", title=d.get("title", ""), when_datetime=None, status="open", snooze_until=None))
            db.commit()
            results.append({"email_id": email.id, "actions": actions})
        return results
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/{email_id}")
def email_detail(email_id: int, db: Session = Depends(get_db)):
    email = db.query(Email).filter_by(id=email_id).first()
    if not email:
        raise HTTPException(status_code=404)
    raw = email.body_text or email.snippet or ""
    return {
        "id": email.id,
        "sender": email.sender,
        "subject": email.subject,
        "received_at": email.received_at,
        "gmail_url": email.gmail_url,
        "body_text": raw[:5000]
    }
