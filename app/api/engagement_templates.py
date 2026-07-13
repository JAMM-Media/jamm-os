# app/api/engagement_templates.py

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.engagement_template import (
    EngagementTemplateCreate,
    EngagementTemplateUpdate,
    EngagementTemplateOut,
)
from app.crud import engagement_template as crud_et
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_manager_or_above
from app.models.user import User
import app.services.engagement_template_service as engagement_template_service

router = APIRouter(
    prefix="/engagement-templates",
    tags=["Engagement Templates"]
)


class UseTemplatePayload(BaseModel):
    client_id: UUID
    engagement_name: Optional[str] = None
    assigned_staff_id: Optional[UUID] = None
    tax_year: Optional[int] = None


@router.get("/", response_model=list[EngagementTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    return crud_et.list_templates(db, current_firm.id)


@router.post("/", response_model=EngagementTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: EngagementTemplateCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
    current_user: User = Depends(get_current_user),
):
    return engagement_template_service.create_template(
        db=db, payload=payload, firm_id=current_firm.id, current_user_id=current_user.id,
    )


@router.get("/{template_id}", response_model=EngagementTemplateOut)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    template = crud_et.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}", response_model=EngagementTemplateOut)
def update_template(
    template_id: UUID,
    payload: EngagementTemplateUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
    current_user: User = Depends(get_current_user),
):
    template = crud_et.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return engagement_template_service.update_template(
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
    template = crud_et.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    engagement_template_service.delete_template(
        db=db, template=template, template_id=template_id,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )
    return {"message": "Template deleted"}


@router.post("/{template_id}/use")
def use_template(
    template_id: UUID,
    payload: UseTemplatePayload,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    current_user: User = Depends(get_current_user),
):
    template = crud_et.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return engagement_template_service.use_template(
        db=db, template=template, template_id=template_id, payload=payload,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )
