# app/api/documents.py

import io
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Body,
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
from app.schemas.document import (
    AuditLogOut,
    DocumentDownloadResponse,
    DocumentOut,
    DocumentPreviewResponse,
    DocumentSupersededUpdate,
    PurgeAllConfirm,
    PurgeConfirm,
    UploadUrlRequest,
    UploadUrlResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
    DocumentRenameRequest,
    DocumentMoveRequest,
    DocumentCopyRequest,
)
from app.schemas.pagination import PaginatedResponse
from app.crud import document as crud_document
from app.crud import document_folder as crud_document_folder
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner, require_staff_or_above
from app.models.signature_envelope import SignatureEnvelope
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log
import app.services.document_service as document_service
from app.services.document_access import (
    assert_can_access_document,
    assert_can_approve_document,
    assert_can_delete_document,
    assert_can_reassign_document,
    assert_can_share_document,
    assert_can_upload_to_engagement,
    assert_can_move_across_engagements,
    check_preview_eligible,
    filter_accessible_documents,
)

router = APIRouter(prefix="/documents", tags=["documents"])

# Both "not found" and "access denied" use this identical detail string (hardening B).
_NOT_FOUND = "Document not found"


def _client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


# -----------------------------------------------------------------------
# POST /documents/upload -- Upload a file to S3
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
    # Canonical-relationship check: verifies engagement.client_id matches the
    # supplied client_id and that the user is a member (or manager/owner).
    # This is hardening A -- parent-mismatch prevention.
    assert_can_upload_to_engagement(
        db, user=current_user, firm_id=current_firm.id,
        engagement_id=engagement_id, client_id=client_id,
    )
    return document_service.upload_document(
        db=db, file=file, client_id=client_id,
        engagement_id=engagement_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


# -----------------------------------------------------------------------
# GET /documents/trash -- List soft-deleted documents (per-scope trash view)
# NOTE: registered before /{document_id} so "trash" is not misread as a UUID.
# -----------------------------------------------------------------------
@router.get("/trash", response_model=PaginatedResponse[DocumentOut])
def list_trash_documents(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
    scope: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    query = crud_document.list_trash(
        db,
        firm_id=current_firm.id,
        scope=scope,
        client_id=client_id,
        engagement_id=engagement_id,
    )
    # The same gate that governed the live file governs its trash entry.
    query = filter_accessible_documents(query, db, current_user, current_firm.id)
    total = query.count()
    docs = query.offset(offset).limit(limit).all()

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
                "client_name": client_map.get(doc.client_id),
                "engagement_title": engagement_map.get(doc.engagement_id),
                "uploaded_by_name": user_map.get(doc.uploaded_by) if doc.uploaded_by else None,
            }
        )
        for doc in docs
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# -----------------------------------------------------------------------
# POST /documents/trash/purge-all -- Owner-only: permanently destroy all trash
# within the specified scope. Double-confirmation required.
# NOTE: registered before /{document_id} routes.
# -----------------------------------------------------------------------
@router.post("/trash/purge-all", status_code=status.HTTP_200_OK)
def purge_all_trash(
    body: PurgeAllConfirm,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm must be true to proceed with permanent destruction",
        )
    purged = document_service.purge_all_trash(
        db=db,
        firm_id=current_firm.id,
        current_user_id=current_user.id,
        scope=body.scope,
        engagement_id=body.engagement_id,
        client_id=body.client_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return {"purged": purged}


# -----------------------------------------------------------------------
# POST /documents/upload-url -- Issue a presigned PUT URL for direct-to-S3 upload
# NOTE: registered before /{document_id} so "upload-url" is not read as a UUID.
# -----------------------------------------------------------------------
@router.post("/upload-url", response_model=UploadUrlResponse)
def issue_upload_url(
    body: UploadUrlRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    assert_can_upload_to_engagement(
        db, user=current_user, firm_id=current_firm.id,
        engagement_id=body.engagement_id, client_id=body.client_id,
    )
    result = document_service.issue_upload_url(
        db=db,
        firm_id=current_firm.id,
        client_id=body.client_id,
        engagement_id=body.engagement_id,
        filename=body.filename,
        content_type=body.content_type,
        folder_id=body.folder_id,
    )
    return UploadUrlResponse(**result)


# -----------------------------------------------------------------------
# POST /documents/{document_id}/upload-complete -- Finalize a direct-to-S3 upload
# -----------------------------------------------------------------------
@router.post("/{document_id}/upload-complete", response_model=UploadCompleteResponse)
def complete_upload(
    document_id: uuid.UUID,
    body: UploadCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    assert_can_upload_to_engagement(
        db, user=current_user, firm_id=current_firm.id,
        engagement_id=body.engagement_id, client_id=body.client_id,
    )
    result = document_service.complete_upload(
        db=db,
        user=current_user,
        document_id=document_id,
        firm_id=current_firm.id,
        client_id=body.client_id,
        engagement_id=body.engagement_id,
        filename=body.filename,
        content_type=body.content_type,
        current_user_id=current_user.id,
        folder_id=body.folder_id,
        duplicate_action=body.duplicate_action,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if result.get("document"):
        return UploadCompleteResponse(document=DocumentOut.model_validate(result["document"]))
    return UploadCompleteResponse(
        conflict=result["conflict"]
    )


# -----------------------------------------------------------------------
# PATCH /documents/{document_id}/rename -- Rename a document
# -----------------------------------------------------------------------
@router.patch("/{document_id}/rename", response_model=DocumentOut)
def rename_document(
    document_id: uuid.UUID,
    body: DocumentRenameRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_access_document(db, current_user, doc, current_firm.id)
    renamed = document_service.rename_document(
        db=db, document_id=document_id, firm_id=current_firm.id,
        new_filename=body.filename,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return DocumentOut.model_validate(renamed)


# -----------------------------------------------------------------------
# PATCH /documents/{document_id}/move -- Move within scope or across engagements
# -----------------------------------------------------------------------
@router.patch("/{document_id}/move", response_model=DocumentOut)
def move_document(
    document_id: uuid.UUID,
    body: DocumentMoveRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    src_doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not src_doc:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_access_document(db, current_user, src_doc, current_firm.id)

    is_cross_engagement = (
        body.engagement_id is not None
        and body.engagement_id != src_doc.engagement_id
    )

    if is_cross_engagement:
        assert_can_move_across_engagements(db, current_user, src_doc, current_firm.id)
        moved = document_service.move_document_across_engagements(
            db=db, user=current_user,
            document_id=document_id, firm_id=current_firm.id,
            dest_engagement_id=body.engagement_id,
            dest_client_id=body.client_id,
            target_folder_id=body.folder_id,
            current_user_id=current_user.id,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    else:
        moved = document_service.move_document(
            db=db, user=current_user,
            document_id=document_id, firm_id=current_firm.id,
            target_folder_id=body.folder_id,
            current_user_id=current_user.id,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    return DocumentOut.model_validate(moved)


# -----------------------------------------------------------------------
# POST /documents/{document_id}/copy -- Copy a document (in-place or cross-scope)
# -----------------------------------------------------------------------
@router.post("/{document_id}/copy", response_model=UploadCompleteResponse)
def copy_document(
    document_id: uuid.UUID,
    body: DocumentCopyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    # Source access re-verified at execution time inside the service.
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_access_document(db, current_user, doc, current_firm.id)

    result = document_service.copy_document(
        db=db, user=current_user,
        document_id=document_id, firm_id=current_firm.id,
        target_folder_id=body.folder_id,
        current_user_id=current_user.id,
        duplicate_action=body.duplicate_action,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if result.get("document"):
        return UploadCompleteResponse(document=DocumentOut.model_validate(result["document"]))
    return UploadCompleteResponse(conflict=result["conflict"])


# -----------------------------------------------------------------------
# GET /documents/search -- Keyword search on filenames (access-gated)
# NOTE: registered before /{document_id} and before / to avoid routing issues.
# -----------------------------------------------------------------------
@router.get("/pending", response_model=PaginatedResponse[DocumentOut])
def list_pending_documents(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
    engagement_id: Optional[uuid.UUID] = None,
    client_id: Optional[uuid.UUID] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    query = crud_document.list_pending_documents(
        db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        client_id=client_id,
    )
    query = filter_accessible_documents(query, db, current_user, current_firm.id)
    total = query.count()
    docs = query.offset(offset).limit(limit).all()

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
                "client_name": client_map.get(doc.client_id),
                "engagement_title": engagement_map.get(doc.engagement_id),
                "uploaded_by_name": user_map.get(doc.uploaded_by) if doc.uploaded_by else None,
            }
        )
        for doc in docs
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# -----------------------------------------------------------------------
# GET /documents/search -- Full-text filename search
# NOTE: registered before /{document_id} and before / to avoid routing issues.
# -----------------------------------------------------------------------
@router.get("/search", response_model=PaginatedResponse[DocumentOut])
def search_documents(
    q: str = Query(..., min_length=2, description="Search query (minimum 2 characters)"),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
    scope: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    # 1. Firm boundary first.
    # 2. filter_accessible_documents applied BEFORE count or pagination.
    # 3. Wildcard-escaped ilike for the filename match.
    # No count, facet, or aggregate from the pre-authorization candidate set
    # is ever returned -- total reflects only the authorized, filtered result.
    query = crud_document.search_documents(
        db,
        firm_id=current_firm.id,
        query_str=q,
        scope=scope,
        client_id=client_id,
        engagement_id=engagement_id,
    )
    query = filter_accessible_documents(query, db, current_user, current_firm.id)
    total = query.count()
    docs = query.offset(offset).limit(limit).all()

    items = [DocumentOut.model_validate(doc) for doc in docs]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# -----------------------------------------------------------------------
# GET /documents/ -- List documents (scoped to firm; filterable)
# -----------------------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
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
    # Filter at the query layer so inaccessible documents are never fetched.
    query = filter_accessible_documents(query, db, current_user, current_firm.id)
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
# GET /documents/{document_id} -- Return a single document
# -----------------------------------------------------------------------
@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    # Gate before any enrichment (hardening C). Denial raises 404 with the
    # same detail string as not-found (hardening B).
    assert_can_access_document(db, current_user, doc, current_firm.id)

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
# GET /documents/{document_id}/download -- Return a presigned URL
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
    # Gate check before any URL generation (hardening B, C): no presigned URL
    # is ever generated for a request the user cannot access.
    _prefetch = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not _prefetch:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_access_document(db, current_user, _prefetch, current_firm.id)

    doc, url = document_service.download_document(
        db=db, document_id=document_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return DocumentDownloadResponse(
        document_id=doc.id,
        filename=doc.filename,
        url=url,
        expires_in_seconds=s3_service.PRESIGNED_URL_EXPIRY,
    )


# -----------------------------------------------------------------------
# GET /documents/{document_id}/preview -- Return a preview URL if eligible
# -----------------------------------------------------------------------
@router.get("/{document_id}/preview", response_model=DocumentPreviewResponse)
def preview_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    # Access gate first (same as download). 404 = not found OR access denied.
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_access_document(db, current_user, doc, current_firm.id)

    # Magic-byte check against actual S3 bytes, not stored content_type alone.
    eligible = check_preview_eligible(doc.content_type, doc.s3_key)
    if not eligible:
        return DocumentPreviewResponse(
            document_id=doc.id,
            preview_available=False,
            reason="File type not supported for in-browser preview",
        )

    url = s3_service.generate_presigned_url(doc.s3_key)
    return DocumentPreviewResponse(
        document_id=doc.id,
        preview_available=True,
        url=url,
        expires_in_seconds=s3_service.PRESIGNED_URL_EXPIRY,
    )


# -----------------------------------------------------------------------
# DELETE /documents/{document_id} -- Soft-delete (moves to trash)
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
    _prefetch = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not _prefetch:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_delete_document(db, current_user, _prefetch, current_firm.id)

    document_service.soft_delete_document(
        db=db, document_id=document_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


# -----------------------------------------------------------------------
# POST /documents/{document_id}/restore -- Restore from trash (trio-gated)
# -----------------------------------------------------------------------
@router.post("/{document_id}/restore", response_model=DocumentOut)
def restore_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    # Pre-fetch including deleted state so the trio check can run.
    _prefetch = crud_document.get_document_any_state(
        db, document_id=document_id, firm_id=current_firm.id
    )
    if not _prefetch or _prefetch.deleted_at is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_delete_document(db, current_user, _prefetch, current_firm.id)

    doc = document_service.restore_document(
        db=db, document_id=document_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return DocumentOut.model_validate(doc)


# -----------------------------------------------------------------------
# POST /documents/{document_id}/purge -- Owner-only permanent destruction
# -----------------------------------------------------------------------
@router.post("/{document_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_document(
    document_id: uuid.UUID,
    body: PurgeConfirm,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    # require_firm_owner (stricter than trio) is the gate for purge.
    # The document must be in trash (deleted_at not null).
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm must be true to proceed with permanent destruction",
        )
    document_service.purge_document(
        db=db, document_id=document_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


# -----------------------------------------------------------------------
# GET /documents/{document_id}/audit -- Audit trail for one document
# -----------------------------------------------------------------------
@router.get("/{document_id}/audit", response_model=list[AuditLogOut])
def get_audit_log(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_access_document(db, current_user, doc, current_firm.id)

    return crud_document.list_audit_logs(
        db, firm_id=current_firm.id, document_id=document_id
    ).all()


# -----------------------------------------------------------------------
# PATCH /documents/{document_id}/superseded -- Mark/unmark as superseded
# -----------------------------------------------------------------------
@router.post("/{document_id}/approve", response_model=DocumentOut)
def approve_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    pre = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not pre:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_approve_document(db, current_user, pre, current_firm.id)
    doc = document_service.approve_pending_document(
        db=db,
        user=current_user,
        document_id=document_id,
        firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return DocumentOut.model_validate(doc)


@router.post("/{document_id}/reassign", response_model=DocumentOut)
def reassign_document(
    document_id: uuid.UUID,
    request: Request,
    dest_engagement_id: uuid.UUID = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    pre = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not pre:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_reassign_document(db, current_user, pre, current_firm.id)
    doc = document_service.reassign_pending_document(
        db=db,
        user=current_user,
        document_id=document_id,
        firm_id=current_firm.id,
        dest_engagement_id=dest_engagement_id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return DocumentOut.model_validate(doc)


@router.post("/{document_id}/share-to-portal", response_model=DocumentOut)
def share_document_to_portal(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    pre = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not pre:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_share_document(db, current_user, pre, current_firm.id)
    doc = document_service.share_document_to_portal(
        db=db,
        document_id=document_id,
        firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return DocumentOut.model_validate(doc)


@router.post("/{document_id}/unshare-from-portal", response_model=DocumentOut)
def unshare_document_from_portal(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    pre = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not pre:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    assert_can_share_document(db, current_user, pre, current_firm.id)
    doc = document_service.unshare_document_from_portal(
        db=db,
        document_id=document_id,
        firm_id=current_firm.id,
        current_user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return DocumentOut.model_validate(doc)


@router.patch("/{document_id}/superseded", response_model=DocumentOut)
def patch_document_superseded(
    document_id: uuid.UUID,
    body: DocumentSupersededUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    # Visibility gate (not trio): marking superseded is metadata management, not
    # deletion. Any engagement member who can read a document can flag it.
    # If the product model later restricts this to administrators, upgrade to
    # assert_can_delete_document.
    assert_can_access_document(db, current_user, doc, current_firm.id)
    doc.is_superseded = body.is_superseded
    db.commit()
    db.refresh(doc)
    return DocumentOut.model_validate(doc)
