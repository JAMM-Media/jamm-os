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
from app.models.document_folder import DocumentFolder
from app.models.engagement import Engagement
from app.models.user import User
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.core.enums import NotificationType, NotificationTier, RecipientType
from app.crud import document_folder as crud_document_folder
from app.models.engagement_member import EngagementMember
from app.services.document_access import (
    assert_can_approve_document,
    assert_can_reassign_document,
    assert_can_upload_to_engagement,
    assert_can_move_across_engagements,
    assert_can_write_to_destination,
)

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
    client_note: Optional[str] = None,
    description: Optional[str] = None,
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
        triage_status="pending" if source == "client" else None,
        client_note=client_note,
        description=description,
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

    if source == "client":
        _notify_engagement_staff_of_pending_upload(
            firm_id=firm_id,
            engagement_id=engagement_id,
            doc_id=doc.id,
            filename=file.filename,
            client_name=db_client.name,
        )

    return doc


def _notify_engagement_staff_of_pending_upload(
    *,
    firm_id: UUID,
    engagement_id: UUID,
    doc_id: UUID,
    filename: str,
    client_name: str,
) -> None:
    """Notify all engagement members that a client-uploaded document awaits triage.

    Uses a dedicated SessionLocal so the notification write is isolated from
    the upload request session -- same pattern as engagement_member_service.
    Fires exactly once: on arrival. approve and reassign do not call this.
    """
    from app.db.session import SessionLocal
    from app.services.notification_service import NotificationService

    notification_db = SessionLocal()
    try:
        recipient_ids = list(notification_db.execute(
            select(EngagementMember.user_id).where(
                EngagementMember.firm_id == firm_id,
                EngagementMember.engagement_id == engagement_id,
            )
        ).scalars().all())

        for recipient_id in recipient_ids:
            NotificationService.create_notification(
                db=notification_db,
                firm_id=firm_id,
                recipient_id=recipient_id,
                recipient_type=RecipientType.staff,
                title="Document received from client",
                body=f"{client_name} uploaded \"{filename}\" -- review it in the triage tray.",
                notification_type=NotificationType.system,
                tier=NotificationTier.quiet,
                related_entity_type="document",
                related_entity_id=doc_id,
            )
    finally:
        notification_db.close()


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
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
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
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
    filename: str,
    content_type: str,
    current_user_id: UUID,
    folder_id: Optional[UUID] = None,
    duplicate_action: Optional[str] = None,
    description: Optional[str] = None,
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

    # Re-authorize before touching anything. Role/membership can be revoked in
    # the window between issue_upload_url and upload-complete (presigned URL
    # lifetime). This must be first -- before the idempotency guard, HEAD, or DB.
    if engagement_id is not None:
        assert_can_upload_to_engagement(
            db, user=user, firm_id=firm_id,
            engagement_id=engagement_id, client_id=client_id,
        )
    else:
        dest_scope = "client" if client_id is not None else "firm_library"
        assert_can_write_to_destination(
            db, user=user, firm_id=firm_id,
            dest_scope=dest_scope,
            dest_engagement_id=None,
            dest_client_id=client_id,
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
        description=description,
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


def rename_document(
    *,
    db: Session,
    document_id: UUID,
    firm_id: UUID,
    new_filename: str,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> "Document":
    """Rename a document. Access: visibility gate (any user who can see it)."""
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")

    old_filename = doc.filename
    doc.filename = new_filename
    db.commit()
    db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="rename",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.renamed",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    log_event(
        firm_id=firm_id,
        event_type="document.renamed",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"from_filename": old_filename, "to_filename": new_filename},
    )
    return doc


def move_document(
    *,
    db: Session,
    user,
    document_id: UUID,
    firm_id: UUID,
    target_folder_id: Optional[UUID],
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> "Document":
    """Move a document within its current scope container (same engagement/client/firm_library).

    Access: visibility gate (any member who can see the document).
    target_folder_id must belong to the SAME scope container as the document.
    If it belongs to a different engagement, refuse with 400.
    """
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if target_folder_id is not None:
        folder = db.query(DocumentFolder).filter(
            DocumentFolder.id == target_folder_id,
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.deleted_at.is_(None),
        ).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Destination folder not found")

        # Verify same scope container.
        if doc.scope == "engagement":
            if folder.engagement_id != doc.engagement_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Destination folder belongs to a different engagement. "
                        "Use the cross-engagement move by supplying engagement_id."
                    ),
                )
        elif doc.scope == "client":
            if folder.client_id != doc.client_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Destination folder belongs to a different client.",
                )
        # firm_library: any folder with firm_library scope in the same firm is valid

    old_folder_id = doc.folder_id
    doc.folder_id = target_folder_id
    db.commit()
    db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="move",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.moved",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    log_event(
        firm_id=firm_id,
        event_type="document.moved",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "from_folder_id": str(old_folder_id) if old_folder_id else None,
            "to_folder_id": str(target_folder_id) if target_folder_id else None,
            "cross_engagement": False,
        },
    )
    return doc


def move_document_across_engagements(
    *,
    db: Session,
    user,
    document_id: UUID,
    firm_id: UUID,
    dest_engagement_id: UUID,
    dest_client_id: UUID,
    target_folder_id: Optional[UUID],
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> "Document":
    """Move a document to a different engagement (the misfile fix).

    Trio-gated. Audit-logs both from and to engagement_id explicitly.
    """
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    dest_eng = db.query(Engagement).filter(
        Engagement.id == dest_engagement_id,
        Engagement.firm_id == firm_id,
        Engagement.client_id == dest_client_id,
    ).first()
    if not dest_eng:
        raise HTTPException(status_code=404, detail="Destination engagement not found")

    if target_folder_id is not None:
        folder = db.query(DocumentFolder).filter(
            DocumentFolder.id == target_folder_id,
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.engagement_id == dest_engagement_id,
            DocumentFolder.deleted_at.is_(None),
        ).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Destination folder not found in target engagement")

    from_engagement_id = doc.engagement_id
    from_client_id = doc.client_id

    doc.engagement_id = dest_engagement_id
    doc.client_id = dest_client_id
    doc.folder_id = target_folder_id
    db.commit()
    db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="move_across_engagements",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.moved_across_engagements",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    log_event(
        firm_id=firm_id,
        event_type="document.moved_across_engagements",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "from_engagement_id": str(from_engagement_id) if from_engagement_id else None,
            "to_engagement_id": str(dest_engagement_id),
            "from_client_id": str(from_client_id) if from_client_id else None,
            "to_client_id": str(dest_client_id),
        },
    )
    return doc


def copy_document(
    *,
    db: Session,
    user,
    document_id: UUID,
    firm_id: UUID,
    target_folder_id: Optional[UUID],
    dest_engagement_id: Optional[UUID] = None,
    dest_client_id: Optional[UUID] = None,
    current_user_id: UUID,
    duplicate_action: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Copy a document (create a new S3 object, new Document row).

    S3 mechanism: server-side copy_object_within_bucket. No bytes downloaded.

    Re-verifies source access and destination write access at execution time
    (TOCTOU hardening: membership may have changed since the UI loaded).

    Returns {"document": new_doc} or {"conflict": {...}} if duplicate handling
    is needed.
    """
    src = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not src:
        raise HTTPException(status_code=404, detail="Document not found")

    # Resolve destination scope.
    if target_folder_id is not None:
        dest_folder = db.query(DocumentFolder).filter(
            DocumentFolder.id == target_folder_id,
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.deleted_at.is_(None),
        ).first()
        if not dest_folder:
            raise HTTPException(status_code=404, detail="Destination folder not found")
        dest_scope = dest_folder.scope
        dest_engagement_id = dest_folder.engagement_id
        dest_client_id = dest_folder.client_id
    elif dest_engagement_id is not None:
        # Explicit engagement-root destination (no folder within it).
        # Mirror move_document_across_engagements: validate that the engagement
        # belongs to dest_client_id and to this firm.
        dest_eng = db.query(Engagement).filter(
            Engagement.id == dest_engagement_id,
            Engagement.firm_id == firm_id,
            Engagement.client_id == dest_client_id,
        ).first()
        if not dest_eng:
            raise HTTPException(status_code=404, detail="Destination engagement not found")
        dest_scope = "engagement"
        # dest_engagement_id and dest_client_id are already the correct values from params.
        target_folder_id = None  # engagement root: no subfolder
    else:
        # Copy-in-place: same scope as source.
        dest_scope = src.scope
        dest_engagement_id = src.engagement_id
        dest_client_id = src.client_id
        target_folder_id = src.folder_id

    # Re-verify write access to destination at execution time.
    assert_can_write_to_destination(
        db, user=user, firm_id=firm_id,
        dest_scope=dest_scope,
        dest_engagement_id=dest_engagement_id,
        dest_client_id=dest_client_id,
    )

    # Duplicate check in destination.
    duplicate = crud_document.find_duplicate_filename(
        db, firm_id=firm_id, engagement_id=dest_engagement_id,
        folder_id=target_folder_id, filename=src.filename,
    )

    if duplicate and not duplicate_action:
        return {
            "conflict": {
                "existing_id": duplicate.id,
                "filename": duplicate.filename,
            }
        }

    actual_filename = src.filename

    if duplicate and duplicate_action == "replace":
        duplicate.deleted_at = datetime.now(timezone.utc)
        duplicate.deleted_by = current_user_id
        db.commit()
    elif duplicate and duplicate_action == "keep_both":
        actual_filename = crud_document.next_available_filename(
            db, firm_id=firm_id, engagement_id=dest_engagement_id,
            folder_id=target_folder_id, filename=src.filename,
        )

    new_doc_id = uuid_module.uuid4()
    new_s3_key = _build_s3_key(
        firm_id, dest_client_id, dest_engagement_id, new_doc_id, actual_filename
    )

    s3_service.copy_object_within_bucket(src.s3_key, new_s3_key)

    cross_client = (src.client_id != dest_client_id)

    new_doc = crud_document.create_document(
        db=db,
        firm_id=firm_id,
        client_id=dest_client_id,
        engagement_id=dest_engagement_id,
        uploaded_by=current_user_id,
        filename=actual_filename,
        s3_key=new_s3_key,
        content_type=src.content_type,
        size_bytes=src.size_bytes,
        doc_id=new_doc_id,
        source="staff",
        copied_from_document_id=document_id,
    )

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="copy",
        document_id=new_doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.copied",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=new_doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    log_event(
        firm_id=firm_id,
        event_type="document.copied",
        entity_type="document",
        entity_id=new_doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "source_document_id": str(document_id),
            "source_scope": src.scope,
            "source_engagement_id": str(src.engagement_id) if src.engagement_id else None,
            "source_client_id": str(src.client_id) if src.client_id else None,
            "dest_folder_id": str(target_folder_id) if target_folder_id else None,
            "dest_scope": dest_scope,
            "dest_engagement_id": str(dest_engagement_id) if dest_engagement_id else None,
            "dest_client_id": str(dest_client_id) if dest_client_id else None,
            "cross_client": cross_client,
        },
    )
    return {"document": new_doc}


def approve_pending_document(
    *,
    db: Session,
    user,
    document_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.triage_status != "pending":
        raise HTTPException(status_code=409, detail="This document has already been processed")

    assert_can_approve_document(db=db, user=user, document=doc, firm_id=firm_id)

    pbc_folder = crud_document_folder.get_document_folder_by_name(
        db=db, firm_id=firm_id, engagement_id=doc.engagement_id, name="Provided by Client (PBC)",
    ) if doc.engagement_id else None
    if pbc_folder:
        doc.folder_id = pbc_folder.id

    doc.triage_status = "filed"
    db.commit()
    db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="approve",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.approved",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    # NOTE: "document.approved" is flagged as unconfirmed against Andrew's blessed
    # event-type list -- no docs/ file enumerates blessed event strings.
    log_event(
        firm_id=firm_id,
        event_type="document.approved",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"filename": doc.filename, "folder_id": str(pbc_folder.id) if pbc_folder else None},
    )
    return doc


def reassign_pending_document(
    *,
    db: Session,
    user,
    document_id: UUID,
    firm_id: UUID,
    dest_engagement_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=firm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.triage_status != "pending":
        raise HTTPException(status_code=409, detail="This document has already been processed")

    assert_can_reassign_document(db=db, user=user, document=doc, firm_id=firm_id)

    dest_engagement = db.query(Engagement).filter(
        Engagement.id == dest_engagement_id,
        Engagement.firm_id == firm_id,
    ).first()
    if not dest_engagement:
        raise HTTPException(status_code=404, detail="Destination engagement not found")

    # Cross-client guard: reassigning to an engagement under a different client
    # would move a client's file into another client's binder -- a tenant data
    # leak. This check mirrors the exact failure pattern in CVE-2026-47231
    # (Admidio document module), where the destination was authorized but the
    # source-destination client relationship was not validated.
    if dest_engagement.client_id != doc.client_id:
        raise HTTPException(
            status_code=422,
            detail="Cannot reassign to an engagement belonging to a different client",
        )

    pbc_folder = crud_document_folder.get_document_folder_by_name(
        db=db, firm_id=firm_id, engagement_id=dest_engagement_id, name="Provided by Client (PBC)",
    )
    if pbc_folder:
        doc.folder_id = pbc_folder.id
    else:
        doc.folder_id = None

    doc.engagement_id = dest_engagement_id
    doc.triage_status = "filed"
    db.commit()
    db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="reassign",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.reassigned",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    # NOTE: "document.reassigned" is flagged as unconfirmed against Andrew's blessed
    # event-type list -- no docs/ file enumerates blessed event strings.
    log_event(
        firm_id=firm_id,
        event_type="document.reassigned",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "filename": doc.filename,
            "dest_engagement_id": str(dest_engagement_id),
            "folder_id": str(pbc_folder.id) if pbc_folder else None,
        },
    )
    return doc


def share_document_to_portal(
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

    # firm_library documents have no client_id, so sharing them to the portal
    # is meaningless: there is no client context to share with.
    if doc.scope == "firm_library":
        raise HTTPException(
            status_code=422,
            detail="Firm Library documents have no client to share with",
        )

    already_shared = doc.visibility == "client_visible"
    if not already_shared:
        doc.visibility = "client_visible"
        db.commit()
        db.refresh(doc)

    # Audit both repeat and first-time pushes -- a repeated push attempt is
    # itself worth recording.
    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="share_to_portal",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.shared_to_portal",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    # NOTE: "document.shared_to_portal" is flagged as unconfirmed against
    # Andrew's blessed event-type list -- no docs/ file enumerating blessed
    # event strings was found as of this task.
    log_event(
        firm_id=firm_id,
        event_type="document.shared_to_portal",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"filename": doc.filename, "was_already_shared": already_shared},
    )
    return doc


def unshare_document_from_portal(
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

    # No scope restriction needed: unsharing a firm_library doc that was never
    # shareable is a natural no-op (it can never have reached client_visible).
    already_internal = doc.visibility == "internal"
    if not already_internal:
        doc.visibility = "internal"
        db.commit()
        db.refresh(doc)

    crud_document.write_audit_log(
        db=db, firm_id=firm_id, action="unshare_from_portal",
        document_id=doc.id, user_id=current_user_id, ip_address=ip_address,
    )
    write_audit_log(
        db=db, firm_id=firm_id, action="document.unshared",
        actor_id=current_user_id, actor_type="staff",
        entity_type="document", entity_id=doc.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    # NOTE: "document.unshared" is flagged as unconfirmed against Andrew's
    # blessed event-type list -- no docs/ file enumerating blessed event
    # strings was found as of this task.
    log_event(
        firm_id=firm_id,
        event_type="document.unshared",
        entity_type="document",
        entity_id=doc.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"filename": doc.filename, "was_already_internal": already_internal},
    )
    return doc
