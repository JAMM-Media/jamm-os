# app/crud/document.py

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentAuditLog


def create_document(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    engagement_id: uuid.UUID,
    uploaded_by: Optional[uuid.UUID],
    filename: str,
    s3_key: str,
    content_type: str,
    size_bytes: int,
    doc_id: Optional[uuid.UUID] = None,
) -> Document:
    doc = Document(
        id=doc_id or uuid.uuid4(),
        firm_id=firm_id,
        client_id=client_id,
        engagement_id=engagement_id,
        uploaded_by=uploaded_by,
        filename=filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=size_bytes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, document_id: uuid.UUID, firm_id: uuid.UUID) -> Optional[Document]:
    return db.query(Document).filter(
        Document.id == document_id,
        Document.firm_id == firm_id,
    ).first()


def list_documents(
    db: Session,
    firm_id: uuid.UUID,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
):
    """Returns a query scoped to the firm, suitable for use with paginate()."""
    query = db.query(Document).filter(Document.firm_id == firm_id)
    if client_id:
        query = query.filter(Document.client_id == client_id)
    if engagement_id:
        query = query.filter(Document.engagement_id == engagement_id)
    return query


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()


def write_audit_log(
    db: Session,
    firm_id: uuid.UUID,
    action: str,
    document_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
) -> DocumentAuditLog:
    """Append an immutable audit record. Never call update on this."""
    entry = DocumentAuditLog(
        firm_id=firm_id,
        document_id=document_id,
        user_id=user_id,
        action=action,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_logs(
    db: Session,
    firm_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = None,
):
    """Returns a query of audit log entries scoped to the firm."""
    query = db.query(DocumentAuditLog).filter(DocumentAuditLog.firm_id == firm_id)
    if document_id:
        query = query.filter(DocumentAuditLog.document_id == document_id)
    return query.order_by(DocumentAuditLog.created_at.desc())
