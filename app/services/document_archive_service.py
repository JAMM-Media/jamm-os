# app/services/document_archive_service.py

from uuid import UUID


def generate_and_deliver_document_archive(firm_id: UUID) -> None:
    import logging
    log = logging.getLogger(__name__)
    db = None
    try:
        from app.db.session import SessionLocal
        db = SessionLocal()
        _run_archive(firm_id, db, log)
    except Exception as exc:
        log.error("document_archive: top-level error firm=%s: %s", firm_id, type(exc).__name__)
    finally:
        if db:
            db.close()


def _run_archive(firm_id, db, log):
    from app.models.document import Document
    from sqlalchemy import select

    documents = db.execute(
        select(Document).where(Document.firm_id == firm_id)
    ).scalars().all()

    if not documents:
        from app.models.user import User
        from app.models.firm import Firm
        from app.core.enums import UserRole
        from app.services.email_service import EmailService

        firm_owner = db.query(User).filter(
            User.firm_id == firm_id,
            User.role == UserRole.firm_owner,
            User.is_active == True,
        ).first()
        if firm_owner:
            firm = db.query(Firm).filter(Firm.id == firm_id).first()
            firm_name = firm.name if firm else "Your firm"
            EmailService.send_notification_email(
                to_email=firm_owner.email,
                firm_name=firm_name,
                recipient_name=firm_owner.full_name or "Firm Owner",
                title="Your document archive is ready",
                body="No documents found to archive.",
                app_url="",
            )
        return

    import io
    import zipfile
    import requests as http_requests

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for doc in documents:
            try:
                from app.services.s3 import generate_presigned_url
                url = generate_presigned_url(doc.s3_key)
                resp = http_requests.get(url, timeout=30)
                resp.raise_for_status()
                folder = str(doc.client_id)
                if doc.engagement_id:
                    folder = f"{folder}/{doc.engagement_id}"
                zf.writestr(f"{folder}/{doc.filename}", resp.content)
            except Exception as exc:
                log.warning("document_archive: skipped doc %s: %s", doc.id, type(exc).__name__)
                continue
    zip_buf.seek(0)

    from datetime import date
    from app.services.s3 import upload_fileobj

    s3_key = f"exports/{firm_id}/documents_{date.today().isoformat()}.zip"
    upload_fileobj(zip_buf, s3_key, "application/zip")

    from app.services.s3 import generate_presigned_url

    download_url = generate_presigned_url(s3_key)

    from app.models.user import User
    from app.models.firm import Firm
    from app.core.enums import UserRole
    from app.services.email_service import EmailService

    firm_owner = db.query(User).filter(
        User.firm_id == firm_id,
        User.role == UserRole.firm_owner,
        User.is_active == True,
    ).first()
    if not firm_owner:
        log.warning("document_archive: no firm owner found for firm %s", firm_id)
        return

    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    firm_name = firm.name if firm else "Your firm"
    doc_count = len(documents)

    EmailService.send_notification_email(
        to_email=firm_owner.email,
        firm_name=firm_name,
        recipient_name=firm_owner.full_name or "Firm Owner",
        title="Your document archive is ready",
        body=f"Your document archive containing {doc_count} files is ready to download. The link below will expire in 1 hour.",
        app_url=download_url,
    )

    from app.services.behavioral_log import log_event

    log_event(
        firm_id=firm_id,
        event_type="firm.document_archive_requested",
        entity_type="firm",
        entity_id=firm_id,
        actor_type="staff",
        metadata={"document_count": doc_count},
    )


def generate_and_deliver_engagement_archive(
    firm_id: UUID,
    engagement_id: UUID,
    requested_by_user_id: UUID,
) -> None:
    import logging
    log = logging.getLogger(__name__)
    db = None
    try:
        from app.db.session import SessionLocal
        db = SessionLocal()
        _run_engagement_archive(firm_id, engagement_id, requested_by_user_id, db, log)
    except Exception as exc:
        log.error(
            "engagement_archive: top-level error firm=%s engagement=%s: %s",
            firm_id, engagement_id, type(exc).__name__,
        )
    finally:
        if db:
            db.close()


def _run_engagement_archive(firm_id, engagement_id, requested_by_user_id, db, log):
    from collections import deque
    from app.models.document import Document
    from app.models.document_folder import DocumentFolder
    from sqlalchemy import select

    # Firm-wide archive includes soft-deleted documents (no deleted_at filter).
    # Match that behavior here for consistency.
    documents = db.execute(
        select(Document).where(
            Document.firm_id == firm_id,
            Document.scope == "engagement",
            Document.engagement_id == engagement_id,
        )
    ).scalars().all()

    # Load all folders (including soft-deleted) for zip path reconstruction.
    # A live document in a trashed folder keeps its real nested path in the zip.
    folders = db.execute(
        select(DocumentFolder).where(
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.engagement_id == engagement_id,
        )
    ).scalars().all()

    # BFS from root folders outward (mirrors copy_folder_structure traversal).
    # Result: folder_paths maps folder.id -> zip path string like "Folder A/Subfolder B".
    children_of: dict = {}
    for folder in folders:
        key = folder.parent_folder_id
        if key not in children_of:
            children_of[key] = []
        children_of[key].append(folder)

    folder_paths: dict = {}
    queue: deque = deque(children_of.get(None, []))
    while queue:
        folder = queue.popleft()
        if folder.parent_folder_id is None:
            folder_paths[folder.id] = folder.name
        else:
            parent = folder_paths.get(folder.parent_folder_id, "")
            folder_paths[folder.id] = f"{parent}/{folder.name}" if parent else folder.name
        for child in children_of.get(folder.id, []):
            queue.append(child)

    if not documents:
        _send_engagement_archive_email(
            db=db,
            requested_by_user_id=requested_by_user_id,
            firm_id=firm_id,
            engagement_id=engagement_id,
            body="No documents found to archive.",
            download_url="",
            log=log,
        )
        return

    import io
    import zipfile
    import requests as http_requests

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for doc in documents:
            try:
                from app.services.s3 import generate_presigned_url
                url = generate_presigned_url(doc.s3_key)
                resp = http_requests.get(url, timeout=30)
                resp.raise_for_status()
                if doc.folder_id and doc.folder_id in folder_paths:
                    zip_path = f"{folder_paths[doc.folder_id]}/{doc.filename}"
                else:
                    zip_path = doc.filename
                zf.writestr(zip_path, resp.content)
            except Exception as exc:
                log.warning(
                    "engagement_archive: skipped doc %s: %s", doc.id, type(exc).__name__
                )
                continue
    zip_buf.seek(0)

    from datetime import date
    from app.services.s3 import upload_fileobj

    s3_key = f"exports/{firm_id}/engagement_{engagement_id}_{date.today().isoformat()}.zip"
    upload_fileobj(zip_buf, s3_key, "application/zip")

    from app.services.s3 import generate_presigned_url

    download_url = generate_presigned_url(s3_key)

    _send_engagement_archive_email(
        db=db,
        requested_by_user_id=requested_by_user_id,
        firm_id=firm_id,
        engagement_id=engagement_id,
        body=(
            f"Your engagement archive containing {len(documents)} files is ready to download. "
            "The link below will expire in 1 hour."
        ),
        download_url=download_url,
        log=log,
    )

    from app.services.behavioral_log import log_event

    log_event(
        firm_id=firm_id,
        event_type="engagement.document_archive_completed",
        entity_type="engagement",
        entity_id=engagement_id,
        actor_type="staff",
        metadata={"document_count": len(documents)},
    )


def _send_engagement_archive_email(
    *, db, requested_by_user_id, firm_id, engagement_id, body, download_url, log
):
    from app.models.user import User
    from app.models.firm import Firm
    from app.services.email_service import EmailService

    requester = db.query(User).filter(
        User.id == requested_by_user_id,
        User.firm_id == firm_id,
    ).first()
    if not requester:
        log.warning(
            "engagement_archive: requested_by user not found firm=%s engagement=%s",
            firm_id, engagement_id,
        )
        return
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    firm_name = firm.name if firm else "Your firm"
    EmailService.send_notification_email(
        to_email=requester.email,
        firm_name=firm_name,
        recipient_name=requester.full_name or "Team Member",
        title="Your engagement archive is ready",
        body=body,
        app_url=download_url,
    )
