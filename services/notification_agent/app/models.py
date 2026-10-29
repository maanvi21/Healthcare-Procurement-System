import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class NotificationChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    teams = "teams"
    slack = "slack"


class NotificationStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    simulated = "simulated"
    failed = "failed"


# Shared DB enum types so create_all does not try to create the same Postgres type twice.
_CHANNEL_ENUM = Enum(NotificationChannel, name="notification_channel")
_STATUS_ENUM = Enum(NotificationStatus, name="notification_status")


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    channel: Mapped[NotificationChannel] = mapped_column(_CHANNEL_ENUM)
    subject_template: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body_template: Mapped[str] = mapped_column(Text)
    recipient_template: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    notifications: Mapped[list["Notification"]] = relationship(back_populates="template")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notification_templates.id"), nullable=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(_CHANNEL_ENUM)
    recipient: Mapped[str] = mapped_column(String(256), index=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    event_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(_STATUS_ENUM, default=NotificationStatus.queued)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    template: Mapped[NotificationTemplate | None] = relationship(back_populates="notifications")
