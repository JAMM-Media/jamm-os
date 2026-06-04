# app/api/notification_preferences.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.crud import notification_preference as crud_pref
from app.schemas.notification_preference import NotificationPreferenceOut, NotificationPreferenceUpdate
from app.core.enums import RecipientType, NotificationEventType, UserRole

router = APIRouter(prefix="/api/v1/notification-preferences", tags=["notification-preferences"])


def _recipient_type_for_user(user: User) -> RecipientType:
    """Infer recipient_type from the user's role."""
    if user.role == UserRole.client_portal_user:
        return RecipientType.client
    return RecipientType.staff


@router.get("/", response_model=list[NotificationPreferenceOut])
def list_preferences(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    """List all notification preferences for the current user."""
    recipient_type = _recipient_type_for_user(current_user)
    return crud_pref.get_preferences_for_recipient(
        db,
        firm_id=current_firm.id,
        recipient_id=current_user.id,
        recipient_type=recipient_type,
    )


@router.put("/{event_type}", response_model=NotificationPreferenceOut)
def upsert_preference(
    event_type: str,
    body: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    """Upsert a notification preference for the current user and a specific event type."""
    try:
        validated_event_type = NotificationEventType(event_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid event_type: {event_type!r}. "
                   f"Valid values: {[e.value for e in NotificationEventType]}",
        )

    recipient_type = _recipient_type_for_user(current_user)
    return crud_pref.upsert_preference(
        db,
        firm_id=current_firm.id,
        recipient_id=current_user.id,
        recipient_type=recipient_type,
        event_type=validated_event_type,
        channel=body.channel,
    )
