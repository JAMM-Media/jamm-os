# app/api/document_request_templates.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.document_request_template import (
    DocumentRequestTemplateCreate,
    DocumentRequestTemplateUpdate,
    DocumentRequestTemplateOut,
)
from app.crud import document_request_template as crud_drt
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_manager_or_above
from app.models.user import User
import app.services.document_request_template_service as drt_service

router = APIRouter(
    prefix="/document-request-templates",
    tags=["Document Request Templates"]
)


@router.get("/suggested", response_model=DocumentRequestTemplateOut)
def get_suggested_template(
    engagement_type: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    template = drt_service.get_suggested_template(db, current_firm.id, engagement_type)
    if not template:
        raise HTTPException(status_code=404, detail="No template found for this engagement type")
    return template


@router.get("/", response_model=list[DocumentRequestTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    active_only: bool = Query(True),
):
    return crud_drt.list_templates(db, current_firm.id, active_only=active_only)


@router.post("/", response_model=DocumentRequestTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: DocumentRequestTemplateCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
    current_user: User = Depends(get_current_user),
):
    return drt_service.create_template(
        db=db, payload=payload, firm_id=current_firm.id, current_user_id=current_user.id,
    )


@router.get("/{template_id}", response_model=DocumentRequestTemplateOut)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    template = crud_drt.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}", response_model=DocumentRequestTemplateOut)
def update_template(
    template_id: UUID,
    payload: DocumentRequestTemplateUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
    current_user: User = Depends(get_current_user),
):
    template = crud_drt.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return drt_service.update_template(
        db=db, template=template, payload=payload,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )


@router.delete("/{template_id}")
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
    current_user: User = Depends(get_current_user),
):
    template = crud_drt.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    drt_service.delete_template(
        db=db, template=template, template_id=template_id,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )
    return {"message": "Template deleted"}
