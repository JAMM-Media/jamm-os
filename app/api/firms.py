# app/api/firms.py

import logging
import uuid as _uuid
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.firm import FirmCreate, FirmUpdate, FirmOut
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import firm as crud_firm
from app.dependencies.roles import require_firm_owner, require_system_admin
from app.models.user import User
from app.services.automation_presets import seed_firm_presets
from app.services.tax_organizer_service import seed_firm_organizer_templates
from app.services.engagement_letter_seed import seed_firm_letter_templates
from app.services import firm_service
from app.services import s3 as s3_service
from app.services.firm_settings import reject_retired_settings_keys

router = APIRouter(prefix="/firms", tags=["firms"])


# ---------------------------------------------------------
# CREATE - system_admin only
# Only JAMM PX staff (system_admin) can create new firms.
# Firms are created when a new customer signs up.
# ---------------------------------------------------------
@router.post("/", response_model=FirmOut, status_code=status.HTTP_201_CREATED)
def create_firm(
    payload: FirmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    existing = crud_firm.get_firm_by_slug(db, payload.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A firm with the slug '{payload.slug}' already exists.",
        )
    new_firm = firm_service.create_firm(db, payload, current_user_id=current_user.id)
    seeded = seed_firm_presets(firm_id=new_firm.id, db=db)
    logger.info(f"Firm {new_firm.id} created with {seeded} automation presets")
    seeded_templates = seed_firm_organizer_templates(firm_id=new_firm.id, db=db)
    logger.info(f"Firm {new_firm.id} created with {seeded_templates} organizer templates")
    seeded_letters = seed_firm_letter_templates(firm_id=new_firm.id, db=db)
    logger.info(f"Firm {new_firm.id} created with {seeded_letters} letter templates")
    return new_firm


# ---------------------------------------------------------
# UPDATE MY FIRM - firm_owner only
# ---------------------------------------------------------
@router.patch("/me", response_model=FirmOut)
def update_my_firm(
    payload: FirmUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    reject_retired_settings_keys(payload.settings)

    before = {
        "name": firm.name,
        "staff_auth_policy": firm.staff_auth_policy,
        "subscription_tier": firm.subscription_tier,
        "timesheet_approval_required": firm.timesheet_approval_required,
        "is_active": firm.is_active,
        "firm_type": firm.firm_type,
        "feature_flags": firm.feature_flags,
    }
    updated = crud_firm.update_firm(db, firm, payload)
    after = {
        "name": updated.name,
        "staff_auth_policy": updated.staff_auth_policy,
        "subscription_tier": updated.subscription_tier,
        "timesheet_approval_required": updated.timesheet_approval_required,
        "is_active": updated.is_active,
        "firm_type": updated.firm_type,
        "feature_flags": updated.feature_flags,
    }
    from app.services.behavioral_log import log_setting_changes
    log_setting_changes(
        firm_id=firm.id,
        actor_id=current_user.id,
        old_values=before,
        new_values=after,
    )
    return updated


_ALLOWED_FIRM_TYPES = {"tax_prep", "bookkeeping", "advisory"}

class ConciergeSettingsUpdate(BaseModel):
    firm_type: Optional[str] = None


# ---------------------------------------------------------
# UPDATE CONCIERGE SETTINGS - firm_owner only
# ---------------------------------------------------------
@router.patch("/me/concierge", response_model=FirmOut)
def update_concierge_settings(
    payload: ConciergeSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    if payload.firm_type is not None and payload.firm_type not in _ALLOWED_FIRM_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"firm_type must be one of: {', '.join(sorted(_ALLOWED_FIRM_TYPES))}",
        )
    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    old_firm_type = firm.firm_type
    if payload.firm_type is not None:
        firm.firm_type = payload.firm_type
    db.commit()
    db.refresh(firm)

    from app.services.behavioral_log import log_setting_changes
    log_setting_changes(
        firm_id=firm.id,
        actor_id=current_user.id,
        old_values={"firm_type": old_firm_type},
        new_values={"firm_type": firm.firm_type},
    )
    return firm


# ---------------------------------------------------------
# LIST - system_admin only
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[FirmOut])
def list_firms(
    db: Session = Depends(get_db),
    limit: int = Query(50, le=1000),
    offset: int = 0,
    _: object = Depends(require_system_admin),
):
    query = crud_firm.get_firms(db)
    return paginate(query, limit=limit, offset=offset)


# ---------------------------------------------------------
# LOGO UPLOAD URL - firm_owner only
# ---------------------------------------------------------

LOGO_ALLOWED_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp"
}
LOGO_MAX_SIZE = 2 * 1024 * 1024  # 2MB

class LogoUploadUrlRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int

class LogoUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str

@router.post("/logo/upload-url", response_model=LogoUploadUrlResponse)
def get_logo_upload_url(
    body: LogoUploadUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    """
    Returns a presigned PUT URL so the browser can upload the logo directly to S3.
    The frontend PUTs the file to upload_url, then calls PATCH /users/firm/settings
    with portal_logo_s3_key set to s3_key.
    """
    if body.file_type not in LOGO_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Logo must be PNG, JPG, SVG, or WEBP"
        )
    if body.file_size > LOGO_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Logo must be 2MB or smaller"
        )

    ext = body.file_name.rsplit(".", 1)[-1].lower() if "." in body.file_name else "png"
    s3_key = f"logos/{current_user.firm_id}/{_uuid.uuid4()}.{ext}"
    upload_url = s3_service.generate_presigned_put_url(s3_key, body.file_type)

    return LogoUploadUrlResponse(upload_url=upload_url, s3_key=s3_key)


# ---------------------------------------------------------
# LOGO SERVE - public, no auth required
# ---------------------------------------------------------

@router.get("/logo/{firm_id}")
def get_firm_logo(
    firm_id: _uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Public endpoint - no auth required.
    Returns a 302 redirect to a fresh presigned S3 URL for the firm's logo.
    Returns 404 if the firm has no logo configured.
    Used as the img src for portal top bar and login page.
    """
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    settings = firm.settings or {}
    s3_key = settings.get("portal_logo_s3_key")
    if not s3_key:
        raise HTTPException(status_code=404, detail="No logo configured")

    presigned_url = s3_service.generate_presigned_url(s3_key)
    return RedirectResponse(url=presigned_url, status_code=302)


# ---------------------------------------------------------
# GET SINGLE - system_admin only
# ---------------------------------------------------------
@router.get("/{firm_id}", response_model=FirmOut)
def get_firm(
    firm_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_system_admin),
):
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    return firm


# ---------------------------------------------------------
# UPDATE - system_admin only
# ---------------------------------------------------------
@router.patch("/{firm_id}", response_model=FirmOut)
def update_firm(
    firm_id: UUID,
    payload: FirmUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_system_admin),
):
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    reject_retired_settings_keys(payload.settings)

    return crud_firm.update_firm(db, firm, payload)


# ---------------------------------------------------------
# DELETE - system_admin only
# Deleting a firm cascades to ALL its data. This is irreversible.
# ---------------------------------------------------------
@router.delete("/{firm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_firm(
    firm_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_system_admin),
):
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    crud_firm.delete_firm(db, firm)