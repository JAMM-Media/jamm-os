# app/api/checklist_templates.py

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.checklist_template import (
    ChecklistTemplateCreate,
    ChecklistTemplateOut,
    ChecklistTemplateUpdate,
)
from app.schemas.document_request import DocumentRequestCreate, DocumentRequestOut
from app.schemas.pagination import PaginatedResponse
from app.crud import checklist_template as crud
from app.crud import document_request as crud_doc_request
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_manager_or_above

router = APIRouter(prefix="/checklist-templates", tags=["checklist-templates"])


# ---------------------------------------------------------
# CREATE  (manager+ only)
# ---------------------------------------------------------
@router.post("/", response_model=ChecklistTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: ChecklistTemplateCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    return crud.create_template(db, payload, firm_id=current_firm.id)


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[ChecklistTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    engagement_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items = crud.list_templates(
        db,
        firm_id=current_firm.id,
        engagement_type=engagement_type,
        skip=skip,
        limit=limit,
    )
    total_items = crud.list_templates(
        db,
        firm_id=current_firm.id,
        engagement_type=engagement_type,
        skip=0,
        limit=10_000,
    )
    return PaginatedResponse(total=len(total_items), limit=limit, offset=skip, items=items)


# ---------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------
@router.get("/{template_id}", response_model=ChecklistTemplateOut)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    template = crud.get_template(db, template_id, firm_id=current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


# ---------------------------------------------------------
# UPDATE  (manager+ only)
# ---------------------------------------------------------
@router.patch("/{template_id}", response_model=ChecklistTemplateOut)
def update_template(
    template_id: UUID,
    payload: ChecklistTemplateUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    template = crud.update_template(db, template_id, firm_id=current_firm.id, data=payload)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


# ---------------------------------------------------------
# DELETE  (manager+ only)
# ---------------------------------------------------------
@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    deleted = crud.delete_template(db, template_id, firm_id=current_firm.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")


# ---------------------------------------------------------
# APPLY  — create a DocumentRequest from a template
# ---------------------------------------------------------
class ApplyTemplateBody(BaseModel):
    client_id: UUID
    engagement_id: UUID
    title: Optional[str] = None
    due_date: Optional[date] = None


@router.post("/{template_id}/apply", response_model=DocumentRequestOut, status_code=status.HTTP_201_CREATED)
def apply_template(
    template_id: UUID,
    payload: ApplyTemplateBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    template = crud.get_template(db, template_id, firm_id=current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    from app.schemas.document_request import ChecklistItem
    checklist_items = [ChecklistItem(**item) for item in (template.items or [])]

    doc_request_data = DocumentRequestCreate(
        client_id=payload.client_id,
        engagement_id=payload.engagement_id,
        title=payload.title or template.name,
        due_date=payload.due_date,
        checklist_items=checklist_items,
    )
    return crud_doc_request.create_document_request(db, doc_request_data, firm_id=current_firm.id)
