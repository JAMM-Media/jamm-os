# app/crud/notification_preference.py

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference
from app.core.enums import RecipientType, NotificationEventType, NotificationChannel


def get_preference(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
    event_type: NotificationEventType,
) -> NotificationPreference | None:
    stmt = select(NotificationPreference).where(
        NotificationPreference.firm_id == firm_id,
        NotificationPreference.recipient_id == recipient_id,
        NotificationPreference.recipient_type == recipient_type,
        NotificationPreference.event_type == event_type,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_preferences_for_recipient(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
) -> list[NotificationPreference]:
    stmt = select(NotificationPreference).where(
        NotificationPreference.firm_id == firm_id,
        NotificationPreference.recipient_id == recipient_id,
        NotificationPreference.recipient_type == recipient_type,
    )
    return list(db.execute(stmt).scalars().all())


def upsert_preference(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
    event_type: NotificationEventType,
    channel: NotificationChannel,
) -> NotificationPreference:
    """Update channel if the row exists, otherwise create it."""
    existing = get_preference(db, firm_id, recipient_id, recipient_type, event_type)
    if existing is not None:
        existing.channel = channel
        db.commit()
        db.refresh(existing)
        return existing

    pref = NotificationPreference(
        firm_id=firm_id,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
        event_type=event_type,
        channel=channel,
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def get_channel_for_event(
    db: Session,
    firm_id: uuid.UUID,
    recipient_id: uuid.UUID,
    recipient_type: RecipientType,
    event_type: NotificationEventType,
) -> NotificationChannel:
    """Return the configured channel for this event. Defaults to 'both' if no row exists."""
    pref = get_preference(db, firm_id, recipient_id, recipient_type, event_type)
    if pref is None:
        return NotificationChannel.both
    return pref.channel
