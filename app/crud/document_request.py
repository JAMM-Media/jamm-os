# app/crud/document_request.py

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.document_request import DocumentRequest
from app.schemas.document_request import DocumentRequestCreate, DocumentRequestUpdate


def create_document_request(
    db: Session,
    data: DocumentRequestCreate,
    firm_id: UUID,
) -> DocumentRequest:
    request = DocumentRequest(
        firm_id=firm_id,
        client_id=data.client_id,
        engagement_id=data.engagement_id,
        title=data.title,
        due_date=data.due_date,
        checklist_items=[item.model_dump() for item in data.checklist_items],
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_document_request(
    db: Session,
    request_id: UUID,
    firm_id: UUID,
) -> DocumentRequest | None:
    stmt = select(DocumentRequest).where(
        DocumentRequest.id == request_id,
        DocumentRequest.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def list_document_requests(
    db: Session,
    firm_id: UUID,
    client_id: UUID | None = None,
    engagement_id: UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[DocumentRequest]:
    stmt = select(DocumentRequest).where(DocumentRequest.firm_id == firm_id)
    if client_id is not None:
        stmt = stmt.where(DocumentRequest.client_id == client_id)
    if engagement_id is not None:
        stmt = stmt.where(DocumentRequest.engagement_id == engagement_id)
    if status is not None:
        stmt = stmt.where(DocumentRequest.status == status)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_document_request(
    db: Session,
    request_id: UUID,
    firm_id: UUID,
    data: DocumentRequestUpdate,
) -> DocumentRequest | None:
    request = get_document_request(db, request_id, firm_id)
    if request is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "checklist_items" and value is not None:
            value = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
        setattr(request, key, value)
    db.commit()
    db.refresh(request)
    return request


def delete_document_request(
    db: Session,
    request_id: UUID,
    firm_id: UUID,
) -> bool:
    request = get_document_request(db, request_id, firm_id)
    if request is None:
        return False
    db.delete(request)
    db.commit()
    return True


def update_checklist_item_status(
    db: Session,
    request_id: UUID,
    firm_id: UUID,
    item_id: str,
    new_status: str,
) -> DocumentRequest | None:
    request = get_document_request(db, request_id, firm_id)
    if request is None:
        return None

    items = request.checklist_items or []
    for item in items:
        if item.get("id") == item_id:
            item["status"] = new_status
            break

    flag_modified(request, "checklist_items")

    required_items = [i for i in items if i.get("is_required")]
    uploaded_required = [i for i in required_items if i.get("status") == "uploaded"]

    if required_items and len(uploaded_required) == len(required_items):
        request.status = "complete"
        request.completed_at = datetime.now(timezone.utc)
    elif uploaded_required:
        request.status = "partial"
    else:
        request.status = "pending"

    db.commit()
    db.refresh(request)
    return request
