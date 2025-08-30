from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from .session import add_session
from .db import SessionLocal, engine
from .models import Base, User, Email, Summary, Action
from .schemas import SummarizeRequest, ActionCreate, ActionUpdate, ActionOut, EmailOut, SummaryOut
from .auth import router as auth_router
from .gmail import creds_from_session_token, gmail_service, extract_plain, gmail_link, parse_received
from .hf import summarize, extract_actions
import json

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
def list_emails(request: Request, filter: str = "unread", limit: int = 50, db: Session = Depends(get_db)):
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
    if existing and existing.created_at and existing.created_at > datetime.utcnow() - timedelta(hours=24):
        return SummaryOut.from_orm(existing)
    try:
        s = summarize(email.body_text or email.snippet or "")
    except Exception:
        s = ""
    try:
        actions = extract_actions(email.body_text or email.snippet or "")
    except Exception:
        actions = {"tasks": [], "meetings": [], "deadlines": []}
    data = json.dumps(actions)
    model = "distilbart-cnn-12-6 + flan-t5-small"
    if existing:
        existing.summary_text = s
        existing.actions_json = data
        existing.model_name = model
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return SummaryOut.from_orm(existing)
    rec = Summary(email_id=email.id, summary_text=s, actions_json=data, model_name=model, created_at=datetime.utcnow())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return SummaryOut.from_orm(rec)

@app.get("/api/items")
def list_actions(type: str | None = None, status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Action)
    if type:
        q = q.filter(Action.type == type)
    if status:
        q = q.filter(Action.status == status)
    return [ActionOut.from_orm(x).dict() for x in q.order_by(Action.id.desc()).all()]

@app.post("/api/items")
def create_action(body: ActionCreate, db: Session = Depends(get_db)):
    email = db.query(Email).filter_by(id=body.email_id).first()
    if not email:
        raise HTTPException(status_code=404)
    rec = Action(email_id=email.id, type=body.type, title=body.title, when_datetime=body.when_datetime, status="open")
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return ActionOut.from_orm(rec).dict()

@app.patch("/api/items/{item_id}")
def update_action(item_id: int, body: ActionUpdate, db: Session = Depends(get_db)):
    rec = db.query(Action).filter_by(id=item_id).first()
    if not rec:
        raise HTTPException(status_code=404)
    if body.status is not None:
        rec.status = body.status
    if body.snooze_until is not None:
        rec.snooze_until = body.snooze_until
    db.commit()
    db.refresh(rec)
    return ActionOut.from_orm(rec).dict()
