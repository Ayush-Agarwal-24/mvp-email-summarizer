from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SummarizeRequest(BaseModel):
    email_id: int
    force: Optional[bool] = True
    prompt: Optional[str] = None


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

class MarkBatchRequest(BaseModel):
    ids: List[int]
    force: Optional[bool] = True

class GenTestRequest(BaseModel):
    sender: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    prompt: Optional[str] = None
