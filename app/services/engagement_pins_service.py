# app/services/engagement_pins_service.py
import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.engagement_pin import EngagementPin
from app.models.user import User
from app.services.engagement_member_service import (
    FIRM_WIDE_MANAGEMENT_ROLES,
    require_can_manage_membership,
)

PIN_CAP = 5


def _validate_item_type(item_type: str) -> None:
    if item_type not in ("document", "folder"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="item_type must be 'document' or 'folder'",
        )


def _assert_item_in_engagement(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
) -> None:
    """
    Confirm the item exists, belongs to this firm AND this specific engagement,
    and is not soft-deleted. A pin on engagement X may only reference items
    that actually belong to engagement X.
    """
    if item_type == "document":
        item = db.query(Document).filter(
            Document.id == item_id,
            Document.firm_id == firm_id,
            Document.engagement_id == engagement_id,
            Document.deleted_at.is_(None),
        ).first()
    else:
        item = db.query(DocumentFolder).filter(
            DocumentFolder.id == item_id,
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.engagement_id == engagement_id,
            DocumentFolder.deleted_at.is_(None),
        ).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{item_type.capitalize()} not found in this engagement",
        )


def _assert_can_read_pins(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    user: User,
) -> None:
    """
    Elevated roles (manager, firm_owner, system_admin) may read without a
    membership check, but the engagement must still belong to this firm.
    All other staff must be a direct member of the engagement.
    Mirrors assert_can_access_document's engagement-scoped rule exactly.
    """
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.firm_id == firm_id,
    ).first()
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found",
        )
    if user.role in FIRM_WIDE_MANAGEMENT_ROLES:
        return
    member = db.query(EngagementMember).filter(
        EngagementMember.firm_id == firm_id,
        EngagementMember.engagement_id == engagement_id,
        EngagementMember.user_id == user.id,
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found",
        )


def add_pin(
    db: Session,
    *,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
    user: User,
) -> EngagementPin:
    require_can_manage_membership(db, firm_id=firm_id, engagement_id=engagement_id, user=user)
    _validate_item_type(item_type)
    _assert_item_in_engagement(db, firm_id, engagement_id, item_type, item_id)

    current_count = db.query(EngagementPin).filter(
        EngagementPin.firm_id == firm_id,
        EngagementPin.engagement_id == engagement_id,
    ).count()
    if current_count >= PIN_CAP:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Engagements are limited to {PIN_CAP} pins. Remove a pin before adding another.",
        )

    existing = db.query(EngagementPin).filter(
        EngagementPin.engagement_id == engagement_id,
        EngagementPin.item_type == item_type,
        EngagementPin.item_id == item_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already pinned",
        )

    pin = EngagementPin(
        firm_id=firm_id,
        engagement_id=engagement_id,
        item_type=item_type,
        item_id=item_id,
        pinned_by=user.id,
    )
    db.add(pin)
    db.commit()
    db.refresh(pin)
    return pin


def remove_pin(
    db: Session,
    *,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
    user: User,
) -> None:
    """Idempotent -- no error if not already pinned."""
    require_can_manage_membership(db, firm_id=firm_id, engagement_id=engagement_id, user=user)
    _validate_item_type(item_type)
    db.query(EngagementPin).filter(
        EngagementPin.firm_id == firm_id,
        EngagementPin.engagement_id == engagement_id,
        EngagementPin.item_type == item_type,
        EngagementPin.item_id == item_id,
    ).delete(synchronize_session=False)
    db.commit()


def list_pins(
    db: Session,
    *,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    user: User,
) -> List[dict]:
    """
    Return pins for this engagement in creation order. Readable by all
    engagement members and elevated roles. Items soft-deleted since pinning
    are excluded without removing the pin row itself.
    """
    _assert_can_read_pins(db, firm_id, engagement_id, user)

    pins = (
        db.query(EngagementPin)
        .filter(
            EngagementPin.firm_id == firm_id,
            EngagementPin.engagement_id == engagement_id,
        )
        .order_by(EngagementPin.created_at)
        .all()
    )

    result = []
    for pin in pins:
        if pin.item_type == "document":
            doc = db.query(Document).filter(
                Document.id == pin.item_id,
                Document.firm_id == firm_id,
                Document.deleted_at.is_(None),
            ).first()
            if doc is None:
                continue
            result.append({
                "id": str(pin.id),
                "item_type": "document",
                "item_id": str(doc.id),
                "name": doc.filename,
                "content_type": doc.content_type,
                "pinned_by": str(pin.pinned_by) if pin.pinned_by else None,
                "created_at": pin.created_at.isoformat(),
            })
        else:
            folder = db.query(DocumentFolder).filter(
                DocumentFolder.id == pin.item_id,
                DocumentFolder.firm_id == firm_id,
                DocumentFolder.deleted_at.is_(None),
            ).first()
            if folder is None:
                continue
            result.append({
                "id": str(pin.id),
                "item_type": "folder",
                "item_id": str(folder.id),
                "name": folder.name,
                "content_type": None,
                "pinned_by": str(pin.pinned_by) if pin.pinned_by else None,
                "created_at": pin.created_at.isoformat(),
            })
    return result
