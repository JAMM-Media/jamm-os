# app/api/notifications.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.crud import notification as crud_notification
from app.schemas.notification import NotificationOut
from app.schemas.pagination import PaginatedResponse
from app.core.enums import RecipientType, UserRole
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _recipient_type_for_user(user: User) -> RecipientType:
    """Infer recipient_type from the user's role."""
    if user.role == UserRole.client_portal_user:
        return RecipientType.client
    return RecipientType.staff


# IMPORTANT: /unread-count and /read-all must be defined BEFORE /{notification_id}
# to prevent FastAPI from matching literal strings as UUIDs.


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    """Return unread notification count for the current user."""
    recipient_type = _recipient_type_for_user(current_user)
    count = crud_notification.get_unread_count(
        db,
        firm_id=current_firm.id,
        recipient_id=current_user.id,
        recipient_type=recipient_type,
    )
    return {"count": count}


@router.patch("/read-all")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    recipient_type = _recipient_type_for_user(current_user)
    updated = NotificationService.mark_all_as_read(
        db,
        firm_id=current_firm.id,
        recipient_id=current_user.id,
        recipient_type=recipient_type,
    )
    return {"updated": updated}


@router.get("/", response_model=PaginatedResponse[NotificationOut])
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    """List notifications for the current user, paginated."""
    recipient_type = _recipient_type_for_user(current_user)
    items = crud_notification.get_notifications_for_recipient(
        db,
        firm_id=current_firm.id,
        recipient_id=current_user.id,
        recipient_type=recipient_type,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    total = crud_notification.count_notifications_for_recipient(
        db,
        firm_id=current_firm.id,
        recipient_id=current_user.id,
        recipient_type=recipient_type,
        unread_only=unread_only,
    )
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read. Returns 404 if not found or not owned by current user."""
    notification = NotificationService.mark_as_read(
        db,
        firm_id=current_firm.id,
        notification_id=notification_id,
        recipient_id=current_user.id,
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification
