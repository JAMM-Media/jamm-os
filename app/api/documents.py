# app/api/documents.py

import io
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
    File,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.schemas.document import DocumentOut, DocumentDownloadResponse, AuditLogOut
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import document as crud_document
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.services import s3 as s3_service

router = APIRouter(prefix="/documents", tags=["documents"])

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _build_s3_key(firm_id: uuid.UUID, client_id: uuid.UUID, engagement_id: uuid.UUID, doc_id: uuid.UUID, filename: str) -> str:
    """Deterministic S3 key. Path segments prevent accidental collisions across tenants."""
    return f"{firm_id}/{client_id}/{engagement_id}/{doc_id}/{filename}"


def _client_ip(request: Request) -> Optional[str]:
    """Best-effort IP extraction for audit logging."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


# -----------------------------------------------------------------------
# POST /documents/upload — Upload a file to S3
# -----------------------------------------------------------------------
@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    client_id: uuid.UUID = Query(...),
    engagement_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    # Verify client belongs to this firm
    db_client = db.query(Client).filter(
        Client.id == client_id,
        Client.firm_id == current_firm.id,
    ).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify engagement belongs to this firm and client
    db_engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.firm_id == current_firm.id,
        Engagement.client_id == client_id,
    ).first()
    if not db_engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    # Read file content and enforce size limit
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    # Pre-generate the UUID so the S3 key and DB id stay in sync.
    doc_id = uuid.uuid4()
    content_type = file.content_type or "application/octet-stream"
    s3_key = _build_s3_key(
        current_firm.id, client_id, engagement_id, doc_id, file.filename
    )

    s3_service.upload_fileobj(io.BytesIO(content), s3_key, content_type)

    doc = crud_document.create_document(
        db=db,
        firm_id=current_firm.id,
        client_id=client_id,
        engagement_id=engagement_id,
        uploaded_by=current_user.id,
        filename=file.filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=len(content),
        doc_id=doc_id,
    )

    crud_document.write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="upload",
        document_id=doc.id,
        user_id=current_user.id,
        ip_address=_client_ip(request),
    )
    return doc


# -----------------------------------------------------------------------
# GET /documents/ — List documents (scoped to firm; filterable)
# -----------------------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    query = crud_document.list_documents(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        engagement_id=engagement_id,
    )
    return paginate(query, limit=limit, offset=offset)


# -----------------------------------------------------------------------
# GET /documents/{document_id}/download — Return a presigned URL
# -----------------------------------------------------------------------
@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
def download_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    url = s3_service.generate_presigned_url(doc.s3_key)

    crud_document.write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="download",
        document_id=doc.id,
        user_id=current_user.id,
        ip_address=_client_ip(request),
    )
    return DocumentDownloadResponse(
        document_id=doc.id,
        filename=doc.filename,
        url=url,
        expires_in_seconds=s3_service.PRESIGNED_URL_EXPIRY,
    )


# -----------------------------------------------------------------------
# DELETE /documents/{document_id} — Delete from S3 and DB
# -----------------------------------------------------------------------
@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Write audit log BEFORE deleting (document_id FK will go NULL on delete,
    # but we capture it while the document still exists)
    crud_document.write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="delete",
        document_id=doc.id,
        user_id=current_user.id,
        ip_address=_client_ip(request),
    )

    s3_key = doc.s3_key
    crud_document.delete_document(db, doc)
    s3_service.delete_object(s3_key)


# -----------------------------------------------------------------------
# GET /documents/{document_id}/audit — Audit trail for one document
# -----------------------------------------------------------------------
@router.get("/{document_id}/audit", response_model=list[AuditLogOut])
def get_audit_log(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return crud_document.list_audit_logs(
        db, firm_id=current_firm.id, document_id=document_id
    ).all()
