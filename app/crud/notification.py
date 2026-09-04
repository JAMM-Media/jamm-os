# app/crud/notification.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate
from app.core.enums import RecipientType


def create_notification(
    db: Session,
    firm_id: uuid.UUID,
    data: NotificationCreate,
) -> Notification:
    notification = Notification(
        firm_id=firm_id,
        recipient_id=data.recipient_id,
        recipient_type=data.recipient_type,
        title=data.title,
        body=data.body,
        notification_type=data.notification_type,
        tier=data.tier,
        related_entity_type=data.related_entity_type,
        related_entity_id=data.related_entity_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_notifications_for_recipient(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = False,
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(
            Notification.firm_id == firm_id,
            Notification.recipient_id == recipient_id,
            Notification.recipient_type == recipient_type,
        )
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return list(db.execute(stmt).scalars().all())


def count_notifications_for_recipient(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
    unread_only: bool = False,
) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.firm_id == firm_id,
            Notification.recipient_id == recipient_id,
            Notification.recipient_type == recipient_type,
        )
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return db.execute(stmt).scalar_one()


def get_unread_count(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.firm_id == firm_id,
            Notification.recipient_id == recipient_id,
            Notification.recipient_type == recipient_type,
            Notification.is_read.is_(False),
        )
    )
    return db.execute(stmt).scalar_one()


def mark_as_read(
    db: Session,
    firm_id: uuid.UUID,
    notification_id: uuid.UUID,
    recipient_id: uuid.UUID,
) -> Notification | None:
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.firm_id == firm_id,
        Notification.recipient_id == recipient_id,
    )
    notification = db.execute(stmt).scalar_one_or_none()
    if notification is None:
        return None
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_as_read(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
) -> int:
    """Mark all unread notifications for this recipient as read. Returns count updated."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(
            Notification.firm_id == firm_id,
            Notification.recipient_id == recipient_id,
            Notification.recipient_type == recipient_type,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
