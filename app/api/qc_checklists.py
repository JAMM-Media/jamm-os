# app/api/qc_checklists.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import qc_checklist as crud
from app.db.session import get_db
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.dependencies.auth import get_current_user
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.user import User
from app.schemas.qc_checklist import (
    QcChecklistTemplateCreate,
    QcChecklistTemplateOut,
    QcChecklistTemplateUpdate,
    QcChecklistItemCreate,
    QcChecklistItemOut,
    QcChecklistItemUpdate,
)

router = APIRouter(prefix="/qc-checklists", tags=["QC Checklists"])


# ── Template endpoints (manager+) ────────────────────────────────────────────

@router.get("/templates/", response_model=list[QcChecklistTemplateOut])
def list_templates(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    return crud.list_templates(db, current_firm.id, include_inactive=include_inactive)


@router.post("/templates/", response_model=QcChecklistTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: QcChecklistTemplateCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    return crud.create_template(db, current_firm.id, payload)


@router.patch("/templates/{template_id}", response_model=QcChecklistTemplateOut)
def update_template(
    template_id: UUID,
    payload: QcChecklistTemplateUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    obj = crud.get_template(db, current_firm.id, template_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Template not found")
    return crud.update_template(db, obj, payload)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    obj = crud.get_template(db, current_firm.id, template_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Template not found")
    crud.soft_delete_template(db, obj)


@router.post("/templates/{template_id}/restore", response_model=QcChecklistTemplateOut)
def restore_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    obj = crud.get_template(db, current_firm.id, template_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Template not found")
    crud.restore_template(db, obj)
    return obj


# ── Item endpoints (staff+) ───────────────────────────────────────────────────

@router.get("/items/", response_model=list[QcChecklistItemOut])
def list_items(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    return crud.list_items(db, current_firm.id, engagement_id)


@router.post("/items/", response_model=QcChecklistItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: QcChecklistItemCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == payload.engagement_id,
            Engagement.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return crud.create_item(db, current_firm.id, payload)


@router.patch("/items/{item_id}/check", response_model=QcChecklistItemOut)
def check_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_staff_or_above),
):
    obj = crud.get_item(db, current_firm.id, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Item not found")
    return crud.check_item(db, obj, current_user.id)


@router.patch("/items/{item_id}/uncheck", response_model=QcChecklistItemOut)
def uncheck_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    obj = crud.get_item(db, current_firm.id, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Item not found")
    return crud.uncheck_item(db, obj)


@router.patch("/items/{item_id}", response_model=QcChecklistItemOut)
def update_item(
    item_id: UUID,
    payload: QcChecklistItemUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    obj = crud.get_item(db, current_firm.id, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Item not found")
    return crud.update_item(db, obj, payload)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    obj = crud.get_item(db, current_firm.id, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Item not found")
    crud.delete_item(db, obj)
