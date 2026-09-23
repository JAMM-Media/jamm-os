# app/services/document_template_status_service.py
"""
Service layer for the DocumentTemplateStatus lifecycle.

Gate: firm_owner, manager, or system_admin only. No engagement administrator
concept applies at firm scope; this is a firm-wide library, not per-engagement.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import TemplateStatus, UserRole
from app.models.document_template_status import DocumentTemplateStatus
from app.models.user import User

# Roles allowed to mutate template status rows.
_TEMPLATE_MANAGERS = (
    UserRole.firm_owner,
    UserRole.manager,
    UserRole.system_admin,
)


def _validate_item_type(item_type: str) -> None:
    if item_type not in ("document", "folder"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="item_type must be 'document' or 'folder'",
        )


def _require_template_manager(user: User) -> None:
    if user.role not in _TEMPLATE_MANAGERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a firm owner or manager may change template lifecycle status.",
        )


def _get_row(
    db: Session, *, firm_id: uuid.UUID, item_type: str, item_id: uuid.UUID
) -> Optional[DocumentTemplateStatus]:
    return (
        db.query(DocumentTemplateStatus)
        .filter(
            DocumentTemplateStatus.firm_id == firm_id,
            DocumentTemplateStatus.item_type == item_type,
            DocumentTemplateStatus.item_id == item_id,
        )
        .first()
    )


def get_status(
    db: Session,
    *,
    firm_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
) -> Optional[DocumentTemplateStatus]:
    """Return the status row, or None if the item is not part of the template lifecycle."""
    _validate_item_type(item_type)
    return _get_row(db, firm_id=firm_id, item_type=item_type, item_id=item_id)


def set_draft(
    db: Session,
    *,
    firm_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
    user: User,
) -> DocumentTemplateStatus:
    """Create or update the row to firm_draft. Gated to firm managers."""
    _validate_item_type(item_type)
    _require_template_manager(user)

    row = _get_row(db, firm_id=firm_id, item_type=item_type, item_id=item_id)
    if row is None:
        row = DocumentTemplateStatus(
            firm_id=firm_id,
            item_type=item_type,
            item_id=item_id,
            status=TemplateStatus.firm_draft,
        )
        db.add(row)
    else:
        row.status = TemplateStatus.firm_draft
    db.commit()
    db.refresh(row)
    return row


def publish(
    db: Session,
    *,
    firm_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
    user: User,
) -> DocumentTemplateStatus:
    """Move to firm_approved and record who published it. Gated to firm managers."""
    _validate_item_type(item_type)
    _require_template_manager(user)

    row = _get_row(db, firm_id=firm_id, item_type=item_type, item_id=item_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No template status row exists for this item. Call set_draft first.",
        )
    row.status = TemplateStatus.firm_approved
    row.published_by = user.id
    row.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def revert_to_draft(
    db: Session,
    *,
    firm_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
    user: User,
) -> DocumentTemplateStatus:
    """Move firm_approved back to firm_draft. Gated to firm managers.

    published_by and published_at are preserved as an audit record of the most
    recent publication event, not cleared. A future call to publish() will
    overwrite them with the new publisher and timestamp.
    """
    _validate_item_type(item_type)
    _require_template_manager(user)

    row = _get_row(db, firm_id=firm_id, item_type=item_type, item_id=item_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No template status row exists for this item.",
        )
    if row.status != TemplateStatus.firm_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item is currently '{row.status.value}', not firm_approved.",
        )
    row.status = TemplateStatus.firm_draft
    db.commit()
    db.refresh(row)
    return row