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
