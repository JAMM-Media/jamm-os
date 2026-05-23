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
from app.schemas.document import DocumentOut, DocumentDownloadResponse, AuditLogOut, DocumentSupersededUpdate
from app.schemas.pagination import PaginatedResponse
from app.crud import document as crud_document
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.models.signature_envelope import SignatureEnvelope
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log
import app.services.document_service as document_service

router = APIRouter(prefix="/documents", tags=["documents"])


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
    return document_service.upload_document(
        db=db, file=file, client_id=client_id,
        engagement_id=engagement_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


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
    total = query.count()
    docs = query.offset(offset).limit(limit).all()

    doc_ids = [doc.id for doc in docs]
    envelope_status_map: dict[uuid.UUID, str] = {}
    if doc_ids:
        envelopes = db.query(SignatureEnvelope).filter(
            SignatureEnvelope.signed_document_id.in_(doc_ids)
        ).all()
        for env in envelopes:
            envelope_status_map[env.signed_document_id] = env.status

    client_ids = [doc.client_id for doc in docs if doc.client_id]
    engagement_ids = [doc.engagement_id for doc in docs if doc.engagement_id]
    uploaded_by_ids = [doc.uploaded_by for doc in docs if doc.uploaded_by]

    client_map = {}
    if client_ids:
        clients = db.query(Client).filter(Client.id.in_(client_ids)).all()
        client_map = {c.id: c.name for c in clients}

    engagement_map = {}
    if engagement_ids:
        engagements = db.query(Engagement).filter(Engagement.id.in_(engagement_ids)).all()
        engagement_map = {e.id: e.name for e in engagements}

    user_map = {}
    if uploaded_by_ids:
        users = db.query(User).filter(User.id.in_(uploaded_by_ids)).all()
        user_map = {u.id: u.full_name or u.email for u in users}

    items = [
        DocumentOut.model_validate(doc).model_copy(
            update={
                "envelope_status": envelope_status_map.get(doc.id, "uploaded"),
                "client_name": client_map.get(doc.client_id),
                "engagement_title": engagement_map.get(doc.engagement_id),
                "uploaded_by_name": user_map.get(doc.uploaded_by) if doc.uploaded_by else None,
            }
        )
        for doc in docs
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# -----------------------------------------------------------------------
# GET /documents/{document_id} — Return a single document
# -----------------------------------------------------------------------
@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Enrich with envelope status
    envelope = db.query(SignatureEnvelope).filter(
        SignatureEnvelope.signed_document_id == document_id
    ).first()
    envelope_status = envelope.status if envelope else "uploaded"

    client = db.query(Client).filter(Client.id == doc.client_id).first()
    engagement = db.query(Engagement).filter(Engagement.id == doc.engagement_id).first()
    uploader = db.query(User).filter(User.id == doc.uploaded_by).first() if doc.uploaded_by else None

    return DocumentOut.model_validate(doc).model_copy(
        update={
            "envelope_status": envelope_status,
            "client_name": client.name if client else None,
            "engagement_title": engagement.name if engagement else None,
            "uploaded_by_name": (uploader.full_name or uploader.email) if uploader else None,
        }
    )


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
    doc, url = document_service.download_document(
        db=db, document_id=document_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    from app.schemas.document import DocumentDownloadResponse
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
    document_service.delete_document(
        db=db, document_id=document_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


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


# -----------------------------------------------------------------------
# PATCH /documents/{document_id}/superseded — Mark/unmark as superseded
# -----------------------------------------------------------------------
@router.patch("/{document_id}/superseded", response_model=DocumentOut)
def patch_document_superseded(
    document_id: uuid.UUID,
    body: DocumentSupersededUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_superseded = body.is_superseded
    db.commit()
    db.refresh(doc)
    return DocumentOut.model_validate(doc)
