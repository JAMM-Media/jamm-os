# app/crud/portal_notification.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from app.models.portal_notification import PortalNotification
from app.schemas.portal_notification import PortalNotificationCreate


def create_notification(
    db: Session,
    data: PortalNotificationCreate,
) -> PortalNotification:
    notification = PortalNotification(
        firm_id=data.firm_id,
        client_id=data.client_id,
        title=data.title,
        body=data.body,
        notification_type=data.notification_type,
        related_entity_type=data.related_entity_type,
        related_entity_id=data.related_entity_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_notifications_for_client(
    db: Session,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = False,
) -> list[PortalNotification]:
    stmt = (
        select(PortalNotification)
        .where(
            PortalNotification.client_id == client_id,
            PortalNotification.firm_id == firm_id,
        )
        .order_by(PortalNotification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(PortalNotification.is_read.is_(False))
    return list(db.execute(stmt).scalars().all())


def get_unread_count(
    db: Session,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> int:
    stmt = (
        select(func.count())
        .select_from(PortalNotification)
        .where(
            PortalNotification.client_id == client_id,
            PortalNotification.firm_id == firm_id,
            PortalNotification.is_read.is_(False),
        )
    )
    return db.execute(stmt).scalar_one()


def mark_as_read(
    db: Session,
    notification_id: uuid.UUID,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> PortalNotification | None:
    stmt = select(PortalNotification).where(
        PortalNotification.id == notification_id,
        PortalNotification.client_id == client_id,
        PortalNotification.firm_id == firm_id,
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
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> int:
    """Mark all unread notifications as read. Returns count updated."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(PortalNotification)
        .where(
            PortalNotification.client_id == client_id,
            PortalNotification.firm_id == firm_id,
            PortalNotification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def create_bulk_notifications(
    db: Session,
    notifications: list[PortalNotificationCreate],
) -> list[PortalNotification]:
    records = [
        PortalNotification(
            firm_id=n.firm_id,
            client_id=n.client_id,
            title=n.title,
            body=n.body,
            notification_type=n.notification_type,
            related_entity_type=n.related_entity_type,
            related_entity_id=n.related_entity_id,
        )
        for n in notifications
    ]
    db.add_all(records)
    db.commit()
    for r in records:
        db.refresh(r)
    return records
