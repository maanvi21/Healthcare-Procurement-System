import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import NotificationChannel, NotificationStatus


class TemplateCreate(BaseModel):
    name: str
    event_type: str
    channel: Literal["email"] = "email"
    subject_template: str | None = None
    body_template: str
    recipient_template: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    channel: Literal["email"] | None = None
    subject_template: str | None = None
    body_template: str | None = None
    recipient_template: str | None = None
    is_active: bool | None = None


class TemplateOut(TemplateCreate):
    id: uuid.UUID
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID | None
    channel: NotificationChannel
    recipient: str
    subject: str | None
    body: str
    event_type: str | None
    event_key: str | None
    status: NotificationStatus
    failure_reason: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SendRequest(BaseModel):
    channel: Literal["email"] = "email"
    recipient: str
    subject: str | None = None
    body: str
    event_type: str | None = None
    event_key: str | None = None


class DigestOut(BaseModel):
    recipient: str
    hours: int
    count: int
    summary: str
    notifications: list[NotificationOut] = Field(default_factory=list)
