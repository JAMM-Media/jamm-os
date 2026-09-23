# app/services/firm_library_seed_service.py
"""
Firm Library starter-template seeding service.

Reads 8 real .docx files from docs/firm-library-templates/ relative to the
repo root, uploads each to S3 under the firm_library scope, and creates a
matching DocumentTemplateStatus row (status=vendor_sample) for each.

DEPLOYMENT NOTE: The template files live at docs/firm-library-templates/ in
the repository. The Docker image (or other deployment artifact) must include
this directory alongside the app package. Resolve before first production
deploy -- if the image only copies app/ the glob below finds nothing and
seed_starter_templates raises HTTP 500.
"""
import io
import pathlib
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import TemplateStatus
from app.crud import document as crud_document
from app.models.document_template_status import DocumentTemplateStatus
from app.models.user import User
from app.services import s3 as s3_service
from app.services.document_template_status_service import _require_template_manager

_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# docs/firm-library-templates/ relative to the repo root (two parents up from
# app/services/).
_TEMPLATES_DIR = pathlib.Path(__file__).parent.parent.parent / "docs" / "firm-library-templates"


def has_starter_templates(db: Session, *, firm_id: uuid.UUID) -> bool:
    """Return True if this firm already has vendor_sample rows from a prior seeding run."""
    return (
        db.query(DocumentTemplateStatus)
        .filter(
            DocumentTemplateStatus.firm_id == firm_id,
            DocumentTemplateStatus.status == TemplateStatus.vendor_sample,
            DocumentTemplateStatus.source_item_id.is_(None),
        )
        .first()
    ) is not None


def seed_starter_templates(db: Session, *, firm_id: uuid.UUID, user: User) -> int:
    """Upload all starter template files to S3 and create Document + DocumentTemplateStatus rows.

    Gated to firm_owner, manager, system_admin. Refuses with 409 if already seeded.

    Atomicity: one db.commit() covers all 8 rows. If any step fails, db.rollback()
    is called so no partial DB rows are written. Note: S3 objects uploaded before
    the failure are not automatically deleted -- they become orphaned objects.
    This trade-off is acceptable for an infrequent admin operation; a future
    cleanup pass or retry-aware upload can address it if needed.

    Returns the count of documents created (always 8 on success).
    """
    _require_template_manager(user)

    if has_starter_templates(db, firm_id=firm_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Starter templates have already been seeded for this firm.",
        )

    template_files = sorted(_TEMPLATES_DIR.glob("*.docx"))
    if not template_files:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No starter template files found. Check deployment configuration.",
        )

    created = 0
    try:
        for path in template_files:
            doc_id = uuid.uuid4()
            filename = path.name
            s3_key = f"{firm_id}/firm_library/{doc_id}/{filename}"

            content = path.read_bytes()
            s3_service.upload_fileobj(
                io.BytesIO(content),
                s3_key,
                _DOCX_CONTENT_TYPE,
            )

            doc = crud_document.create_document(
                db,
                firm_id=firm_id,
                client_id=None,
                engagement_id=None,
                uploaded_by=None,
                filename=filename,
                s3_key=s3_key,
                content_type=_DOCX_CONTENT_TYPE,
                size_bytes=len(content),
                doc_id=doc_id,
                source="system",
            )

            ts = DocumentTemplateStatus(
                firm_id=firm_id,
                item_type="document",
                item_id=doc.id,
                status=TemplateStatus.vendor_sample,
                source_item_id=None,
            )
            db.add(ts)
            created += 1

        db.commit()
        return created

    except Exception:
        db.rollback()
        raise