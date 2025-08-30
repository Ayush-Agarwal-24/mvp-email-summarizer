from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    google_sub = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    emails = relationship("Email", back_populates="user")

class Email(Base):
    __tablename__ = "emails"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    message_id = Column(String, unique=True, index=True, nullable=False)
    thread_id = Column(String, index=True, nullable=False)
    sender = Column(String, index=True)
    subject = Column(String, index=True)
    snippet = Column(Text)
    body_text = Column(Text)
    received_at = Column(DateTime, index=True)
    gmail_url = Column(String)
    user = relationship("User", back_populates="emails")
    summary = relationship("Summary", uselist=False, back_populates="email")
    actions = relationship("Action", back_populates="email")

class Summary(Base):
    __tablename__ = "summaries"
    email_id = Column(Integer, ForeignKey("emails.id"), primary_key=True)
    summary_text = Column(Text)
    actions_json = Column(Text)
    model_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    email = relationship("Email", back_populates="summary")

class Action(Base):
    __tablename__ = "actions"
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), index=True, nullable=False)
    type = Column(String, index=True)
    title = Column(Text)
    when_datetime = Column(DateTime, nullable=True)
    status = Column(String, index=True, default="open")
    snooze_until = Column(DateTime, nullable=True)
    email = relationship("Email", back_populates="actions")
