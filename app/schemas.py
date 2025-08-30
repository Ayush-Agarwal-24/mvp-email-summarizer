from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SummarizeRequest(BaseModel):
    email_id: int

class ActionCreate(BaseModel):
    email_id: int
    type: str
    title: str
    when_datetime: Optional[datetime] = None

class ActionUpdate(BaseModel):
    status: Optional[str] = None
    snooze_until: Optional[datetime] = None

class ActionOut(BaseModel):
    id: int
    email_id: int
    type: str
    title: str
    when_datetime: Optional[datetime]
    status: str
    snooze_until: Optional[datetime]
    class Config:
        from_attributes = True

class EmailOut(BaseModel):
    id: int
    sender: Optional[str]
    subject: Optional[str]
    snippet: Optional[str]
    received_at: Optional[datetime]
    gmail_url: Optional[str]
    class Config:
        from_attributes = True

class SummaryOut(BaseModel):
    email_id: int
    summary_text: Optional[str]
    actions_json: Optional[str]
    model_name: Optional[str]
    class Config:
        from_attributes = True
