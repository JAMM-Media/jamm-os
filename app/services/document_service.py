# app/services/document_service.py

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import io
import uuid as uuid_module

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.crud import document as crud_document
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.user import User
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.document_access import assert_can_upload_to_engagement

MAX_UPLOAD_BYTES = 250 * 1024 * 1024
MAX_DIRECT_UPLOAD_BYTES = 250 * 1024 * 1024


def _build_s3_key(firm_id, client_id, engagement_id, doc_id, filename) -> str:
    return f"{firm_id}/{client_id}/{engagement_id}/{doc_id}/{filename}"


def upload_document(
    *,
    db: Session,
    file: UploadFile,
    client_id: UUID,
    engagement_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    source: str = "staff",
    source_client_id: Optional[UUID] = None,
):
    db_client = db.query(Client).filter(
        Client.id == client_id,
        Client.firm_id == firm_id,
    ).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    db_engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.firm_id == firm_id,
        Engagement.client_id == client_id,
    ).first()
    if not db_engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    doc_id = uuid_module.uuid4()
    content_type = file.content_type or "application/octet-stream"
    s3_key = _build_s3_key(firm_id, client_id, engagement_id, doc_id, file.filename)

    s3_service.upload_fileobj(io.BytesIO(content), s3_key, content_type)

    doc = crud_document.create_document(
        db=db,
        firm_id=firm_id,
        client_id=client_id,
        engagement_id=engagement_id,
        uploaded_by=current_user_id,
        filename=file.filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=len(content),
        doc_id=doc_id,
        source=source,
        source_client_id=source_client_id,
    )

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="upload",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.uploaded",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )

    log_event(
        firm_id=firm_id,
        event_type="document.uploaded",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "file_size": len(content),
            "content_type": content_type,
            "upload_source": source,
            "engagement_id": str(engagement_id),
            "client_id": str(client_id),
            "filename": file.filename,
        }
    )

    return doc


def download_document(
    *,
    db: Session,
    document_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    url = s3_service.generate_presigned_url(doc.s3_key)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="download",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.accessed",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )

    log_event(
        firm_id=firm_id,
        event_type="document.downloaded",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "days_since_upload": (datetime.now(timezone.utc) - doc.created_at).days
                if doc.created_at else None,
            "filename": doc.filename if hasattr(doc, 'filename') else None,
            "action": "presigned_url_generated",
        }
    )

    return doc, url


def view_document(
    *,
    db: Session,
    document_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="view",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.accessed",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )

    log_event(
        firm_id=firm_id,
        event_type="document.viewed",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "days_since_upload": (datetime.now(timezone.utc) - doc.created_at).days
                if doc.created_at else None,
            "filename": doc.filename if hasattr(doc, 'filename') else None,
        }
    )

    return doc


def soft_delete_document(
    *,
    db: Session,
    document_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Mark document as deleted (soft delete). S3 object and DB row survive."""
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.deleted_at = datetime.now(timezone.utc)
    doc.deleted_by = current_user_id
    db.commit()
    db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="soft_delete",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.soft_deleted",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )

    log_event(
        firm_id=firm_id,
        event_type="document.soft_deleted",
        entity_type="document",
        entity_id=document_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "filename": doc.filename,
            "scope": doc.scope,
        }
    )


def restore_document(
    *,
    db: Session,
    document_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Restore a soft-deleted document. Returns it to its original folder_id (or root if the
    folder was hard-deleted -- ondelete=SET NULL on folder_id handles that automatically)."""
    doc = crud_document.get_document_any_state(db, document_id=document_id, firm_id=firm_id)
    if not doc or doc.deleted_at is None:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.deleted_at = None
    doc.deleted_by = None
    db.commit()
    db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="restore",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.restored",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )

    return doc


def purge_document(
    *,
    db: Session,
    document_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Permanently destroy one soft-deleted document. Writes audit BEFORE destruction
    so a mid-operation failure still leaves a record that destruction was attempted."""
    doc = crud_document.get_document_any_state(db, document_id=document_id, firm_id=firm_id)
    if not doc or doc.deleted_at is None:
        raise HTTPException(status_code=404, detail="Document not found")

    s3_key = doc.s3_key
    doc_id = doc.id

    # Audit written BEFORE destruction -- spec requirement.
    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="purge",
        document_id=doc_id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.purged",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc_id,
        ip_address=ip_address, user_agent=user_agent,
    )

    crud_document.delete_document(db, doc)
    s3_service.delete_object(s3_key)


def purge_all_trash(
    *,
    db: Session,
    firm_id: UUID,
    current_user_id: UUID,
    scope: Optional[str] = None,
    engagement_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> int:
    """Permanently destroy all soft-deleted documents matching the given scope.
    Writes one audit record per document BEFORE any destruction begins."""
    docs = crud_document.list_trash(
        db, firm_id=firm_id,
        scope=scope, engagement_id=engagement_id, client_id=client_id,
    ).all()

    if not docs:
        return 0

    # Audit all records before any destruction -- spec requirement.
    for doc in docs:
        crud_document.write_audit_log(
            db=db, firm_id=firm_id, action="purge",
            document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
        )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.purge_all",
        actor_id=current_user_id, actor_type="staff",
        entity_type="firm", entity_id=firm_id,
        ip_address=ip_address, user_agent=user_agent,
    )

    # Process one document at a time: DB row then S3 object. If a crash
    # occurs mid-batch, at most one document is left in an inconsistent state
    # and its audit record (written above) still points at it.
    for doc in docs:
        s3_key = doc.s3_key
        crud_document.delete_document(db, doc)
        s3_service.delete_object(s3_key)

    return len(docs)


def issue_upload_url(
    *,
    db: Session,
    firm_id: UUID,
    client_id: UUID,
    engagement_id: UUID,
    filename: str,
    content_type: str,
    folder_id: Optional[UUID] = None,
) -> dict:
    """Build an S3 key server-side and return a presigned PUT URL + pre-generated document_id.
    No Document row is created yet -- that happens in complete_upload when the browser
    confirms the PUT succeeded."""
    doc_id = uuid_module.uuid4()
    s3_key = _build_s3_key(firm_id, client_id, engagement_id, doc_id, filename)
    upload_url = s3_service.generate_presigned_put_url(s3_key, content_type)
    return {
        "document_id": doc_id,
        "upload_url": upload_url,
        "s3_key": s3_key,
        "expires_in_seconds": s3_service.PRESIGNED_URL_EXPIRY,
    }


def complete_upload(
    *,
    db: Session,
    user: User,
    document_id: UUID,
    firm_id: UUID,
    client_id: UUID,
    engagement_id: UUID,
    filename: str,
    content_type: str,
    current_user_id: UUID,
    folder_id: Optional[UUID] = None,
    duplicate_action: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Finalize a direct-to-S3 upload.

    1. Verify S3 object exists and size <= 250MB via HEAD request.
    2. Check for duplicate filename in the same folder.
    3. Create Document row, handling duplicate_action if provided.

    Returns dict with either {"document": doc} or {"conflict": {...}}.

    250MB enforcement: the file never passes through the server, so we cannot use
    read(MAX+1) to check size. Instead, a HEAD request to S3 reads the
    Content-Length of the already-uploaded object. If oversize, the S3 object is
    deleted and a 413 is returned. This approach is chosen because
    generate_presigned_url("put_object") does not support policy conditions
    (that requires generate_presigned_post with a different flow); HEAD
    verification is compatible with the existing PUT URL mechanism.
    """
    from botocore.exceptions import ClientError

    # Re-authorize before touching anything. Membership can be revoked in the
    # window between issue_upload_url and upload-complete (up to one presigned
    # URL lifetime). This must be first -- before the idempotency guard, before
    # HEAD, before any DB or S3 access.
    assert_can_upload_to_engagement(
        db, user=user, firm_id=firm_id,
        engagement_id=engagement_id, client_id=client_id,
    )

    # Check if document_id already completed (idempotency guard).
    existing = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if existing:
        return {"document": existing}

    s3_key = _build_s3_key(firm_id, client_id, engagement_id, document_id, filename)

    # Verify S3 object exists and get size.
    try:
        meta = s3_service.head_object(s3_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            raise HTTPException(status_code=404, detail="Upload not found -- S3 object does not exist")
        raise

    size_bytes = meta.get("ContentLength", 0)
    if size_bytes > MAX_DIRECT_UPLOAD_BYTES:
        s3_service.delete_object(s3_key)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {MAX_DIRECT_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    # Duplicate filename detection.
    duplicate = crud_document.find_duplicate_filename(
        db, firm_id=firm_id, engagement_id=engagement_id,
        folder_id=folder_id, filename=filename,
    )

    if duplicate and not duplicate_action:
        return {
            "conflict": {
                "existing_id": duplicate.id,
                "filename": duplicate.filename,
            }
        }

    actual_filename = filename

    if duplicate and duplicate_action == "replace":
        # Soft-delete the old document into trash.
        duplicate.deleted_at = datetime.now(timezone.utc)
        duplicate.deleted_by = current_user_id
        db.commit()

    elif duplicate and duplicate_action == "keep_both":
        actual_filename = crud_document.next_available_filename(
            db, firm_id=firm_id, engagement_id=engagement_id,
            folder_id=folder_id, filename=filename,
        )

    doc = crud_document.create_document(
        db=db,
        firm_id=firm_id,
        client_id=client_id,
        engagement_id=engagement_id,
        uploaded_by=current_user_id,
        filename=actual_filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=size_bytes,
        doc_id=document_id,
        source="staff",
    )

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="upload",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.uploaded",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )

    log_event(
        firm_id=firm_id,
        event_type="document.uploaded",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "file_size": size_bytes,
            "content_type": content_type,
            "upload_source": "direct",
            "engagement_id": str(engagement_id),
            "client_id": str(client_id),
            "filename": actual_filename,
        }
    )

    return {"document": doc}
