# app/services/notification_service.py

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.crud import notification as crud_notification
from app.crud import notification_preference as crud_notification_preference
from app.crud.document import write_audit_log
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate
from app.core.enums import RecipientType, NotificationType, NotificationChannel, NotificationEventType

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    def create_notification(
        db: Session,
        firm_id: uuid.UUID,
        recipient_id: uuid.UUID,
        recipient_type: RecipientType,
        title: str,
        body: str,
        notification_type: NotificationType,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[uuid.UUID] = None,
        to_email: Optional[str] = None,
        force_in_app: bool = False,
    ) -> Optional[Notification]:
        # force_in_app is for compliance notices the recipient may not opt out
        # of. A firm may stop the emails; a firm may not make the record
        # disappear from the app. It never forces an email.
        # NotificationType and NotificationEventType share the same values —
        # convert via value to get the matching NotificationEventType.
        try:
            event_type = NotificationEventType(notification_type.value)
        except ValueError:
            event_type = NotificationEventType.system

        channel = crud_notification_preference.get_channel_for_event(
            db, firm_id, recipient_id, recipient_type, event_type
        )

        if channel == NotificationChannel.none and not force_in_app:
            logger.info(
                "Notification suppressed (channel=none): firm=%s recipient=%s type=%s",
                firm_id, recipient_id, notification_type,
            )
            return None

        notification: Optional[Notification] = None

        # Create in-app record for in_app and both channels
        if force_in_app or channel in (NotificationChannel.in_app, NotificationChannel.both):
            data = NotificationCreate(
                recipient_id=recipient_id,
                recipient_type=recipient_type,
                title=title,
                body=body,
                notification_type=notification_type,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )
            notification = crud_notification.create_notification(db, firm_id=firm_id, data=data)
            write_audit_log(db, firm_id=firm_id, action="notification_created")
            logger.info(
                "Notification created: id=%s firm=%s recipient=%s type=%s",
                notification.id, firm_id, recipient_id, notification_type,
            )

        # Send email for email and both channels, when to_email is provided
        if channel in (NotificationChannel.email, NotificationChannel.both) and to_email:
            from app.services.email_service import EmailService
            EmailService.send_notification_email(
                to_email=to_email,
                firm_name="",
                recipient_name="",
                title=title,
                body=body,
            )

        return notification

    @staticmethod
    def mark_as_read(
        db: Session,
        firm_id: uuid.UUID,
        notification_id: uuid.UUID,
        recipient_id: uuid.UUID,
    ) -> Optional[Notification]:
        return crud_notification.mark_as_read(
            db,
            firm_id=firm_id,
            notification_id=notification_id,
            recipient_id=recipient_id,
        )

    @staticmethod
    def mark_all_as_read(
        db: Session,
        firm_id: uuid.UUID,
        recipient_id: uuid.UUID,
        recipient_type: RecipientType,
    ) -> int:
        return crud_notification.mark_all_as_read(
            db,
            firm_id=firm_id,
            recipient_id=recipient_id,
            recipient_type=recipient_type,
        )
