# app/crud/document.py

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentAuditLog


def create_document(
    db: Session,
    firm_id: uuid.UUID,
    client_id: Optional[uuid.UUID],
    engagement_id: Optional[uuid.UUID],
    uploaded_by: Optional[uuid.UUID],
    filename: str,
    s3_key: str,
    content_type: str,
    size_bytes: int,
    doc_id: Optional[uuid.UUID] = None,
    source: str = "staff",
    source_client_id: Optional[uuid.UUID] = None,
    copied_from_document_id: Optional[uuid.UUID] = None,
    triage_status: Optional[str] = None,
    client_note: Optional[str] = None,
) -> Document:
    # scope is derived from the FK combination and enforced by the DB CHECK
    # constraint on documents.scope.
    if engagement_id is not None:
        scope = "engagement"
    elif client_id is not None:
        scope = "client"
    else:
        scope = "firm_library"
    doc = Document(
        id=doc_id or uuid.uuid4(),
        firm_id=firm_id,
        client_id=client_id,
        engagement_id=engagement_id,
        scope=scope,
        uploaded_by=uploaded_by,
        source=source,
        source_client_id=source_client_id,
        filename=filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=size_bytes,
        copied_from_document_id=copied_from_document_id,
        client_note=client_note,
    )
    # Only set triage_status explicitly when the caller passes a value.
    # None means "use the column server_default ('filed')".
    if triage_status is not None:
        doc.triage_status = triage_status
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, document_id: uuid.UUID, firm_id: uuid.UUID) -> Optional[Document]:
    """Return a live (not soft-deleted) document. Returns None for deleted docs."""
    return db.query(Document).filter(
        Document.id == document_id,
        Document.firm_id == firm_id,
        Document.deleted_at.is_(None),
    ).first()


def get_document_any_state(
    db: Session, document_id: uuid.UUID, firm_id: uuid.UUID
) -> Optional[Document]:
    """Return a document regardless of soft-delete state. Used by restore and purge."""
    return db.query(Document).filter(
        Document.id == document_id,
        Document.firm_id == firm_id,
    ).first()


def list_documents(
    db: Session,
    firm_id: uuid.UUID,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
    scope: Optional[str] = None,
):
    """Returns a query of live (not soft-deleted) filed documents scoped to the firm.

    Pending documents (triage_status='pending') are intentionally excluded here.
    They appear only in list_pending_documents, so an unreviewed client-uploaded
    file can never be mistaken for one that staff has already checked.
    """
    query = db.query(Document).filter(
        Document.firm_id == firm_id,
        Document.deleted_at.is_(None),
        Document.triage_status == "filed",
    )
    if client_id:
        query = query.filter(Document.client_id == client_id)
    if engagement_id:
        query = query.filter(Document.engagement_id == engagement_id)
    if scope:
        query = query.filter(Document.scope == scope)
    return query


def list_pending_documents(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: Optional[uuid.UUID] = None,
    client_id: Optional[uuid.UUID] = None,
):
    """Returns a query of live pending documents awaiting staff triage."""
    query = db.query(Document).filter(
        Document.firm_id == firm_id,
        Document.deleted_at.is_(None),
        Document.triage_status == "pending",
    )
    if engagement_id:
        query = query.filter(Document.engagement_id == engagement_id)
    if client_id:
        query = query.filter(Document.client_id == client_id)
    return query


def list_trash(
    db: Session,
    firm_id: uuid.UUID,
    scope: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
):
    """Returns a query of soft-deleted documents scoped to the firm."""
    query = db.query(Document).filter(
        Document.firm_id == firm_id,
        Document.deleted_at.isnot(None),
    )
    if scope:
        query = query.filter(Document.scope == scope)
    if client_id:
        query = query.filter(Document.client_id == client_id)
    if engagement_id:
        query = query.filter(Document.engagement_id == engagement_id)
    return query


def delete_document(db: Session, document: Document) -> None:
    """Hard-delete (permanent, irreversible). Called only from purge service functions."""
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


def find_duplicate_filename(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    folder_id: Optional[uuid.UUID],
    filename: str,
) -> Optional[Document]:
    """Return the first live document with the same filename in the same folder slot, or None."""
    query = db.query(Document).filter(
        Document.firm_id == firm_id,
        Document.engagement_id == engagement_id,
        Document.filename == filename,
        Document.deleted_at.is_(None),
    )
    if folder_id is not None:
        query = query.filter(Document.folder_id == folder_id)
    else:
        query = query.filter(Document.folder_id.is_(None))
    return query.first()


def next_available_filename(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    folder_id: Optional[uuid.UUID],
    filename: str,
) -> str:
    """Return the lowest-numbered suffixed filename not already in use.
    'report.pdf' -> 'report (2).pdf', or 'report (3).pdf' if (2) exists, etc.
    """
    dot_pos = filename.rfind(".")
    if dot_pos > 0:
        stem = filename[:dot_pos]
        ext = filename[dot_pos:]
    else:
        stem = filename
        ext = ""

    n = 2
    while True:
        candidate = f"{stem} ({n}){ext}"
        q = db.query(Document).filter(
            Document.firm_id == firm_id,
            Document.engagement_id == engagement_id,
            Document.filename == candidate,
            Document.deleted_at.is_(None),
        )
        if folder_id is not None:
            q = q.filter(Document.folder_id == folder_id)
        else:
            q = q.filter(Document.folder_id.is_(None))
        exists = q.first()
        if not exists:
            return candidate
        n += 1


def search_documents(
    db: Session,
    firm_id: uuid.UUID,
    query_str: str,
    scope: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
):
    """Search live documents by filename using a case-insensitive LIKE.

    Wildcard characters (% and _) in query_str are escaped so they match
    literally, not as wildcards. The escape character is backslash.
    Tenant boundary (firm_id) and soft-delete filter are applied first.
    """
    escaped = (
        query_str
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    pattern = f"%{escaped}%"
    q = db.query(Document).filter(
        Document.firm_id == firm_id,
        Document.deleted_at.is_(None),
        Document.triage_status == "filed",
        Document.filename.ilike(pattern, escape="\\"),
    )
    if scope:
        q = q.filter(Document.scope == scope)
    if client_id:
        q = q.filter(Document.client_id == client_id)
    if engagement_id:
        q = q.filter(Document.engagement_id == engagement_id)
    return q
