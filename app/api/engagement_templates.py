# app/api/engagement_templates.py

import uuid
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.task import Task
from app.models.document_request import DocumentRequest
from app.schemas.engagement_template import (
    EngagementTemplateCreate,
    EngagementTemplateUpdate,
    EngagementTemplateOut,
)
from app.crud import engagement_template as crud_et
from app.crud.qc_checklist import populate_from_template
from app.core.tax_deadlines import get_filing_deadline
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_manager_or_above
from app.models.user import User
from app.services.behavioral_log import log_event

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
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    return crud_et.list_templates(db, current_firm.id, active_only=active_only)


@router.post("/", response_model=EngagementTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: EngagementTemplateCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
    current_user: User = Depends(get_current_user),
):
    template = crud_et.create_template(db, payload, current_firm.id)
    log_event(
        firm_id=current_firm.id,
        event_type="engagement_template.created",
        entity_type="engagement_template",
        entity_id=template.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "name": template.name,
            "engagement_type": str(template.engagement_type) if template.engagement_type else None,
            "task_count": len(template.task_templates) if template.task_templates else 0,
            "has_document_checklist": bool(template.document_checklist),
            "is_recurring": bool(getattr(template, "is_recurring", False)),
        }
    )
    return template


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
    updated = crud_et.update_template(db, template, payload)
    log_event(
        firm_id=current_firm.id,
        event_type="engagement_template.updated",
        entity_type="engagement_template",
        entity_id=updated.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "name": updated.name,
            "is_recurring": bool(getattr(updated, "is_recurring", False)),
        }
    )
    return updated


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
    crud_et.delete_template(db, template)
    log_event(
        firm_id=current_firm.id,
        event_type="engagement_template.deleted",
        entity_type="engagement_template",
        entity_id=template_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={}
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

    # Auto-set filing_deadline from engagement_type
    filing_deadline = None
    if template.engagement_type:
        deadline_tuple = get_filing_deadline(template.engagement_type)
        if deadline_tuple:
            today = date.today()
            month, day = deadline_tuple
            try:
                filing_deadline = date(today.year, month, day)
            except ValueError:
                pass

    engagement = Engagement(
        firm_id=current_firm.id,
        client_id=payload.client_id,
        name=payload.engagement_name or template.name,
        engagement_type=template.engagement_type,
        filing_deadline=filing_deadline,
    )
    db.add(engagement)
    db.flush()

    tasks_created = 0
    for task_tmpl in (template.task_templates or []):
        title = task_tmpl.get("title", "") if isinstance(task_tmpl, dict) else getattr(task_tmpl, "title", "")
        notes = task_tmpl.get("description") if isinstance(task_tmpl, dict) else getattr(task_tmpl, "description", None)
        if not title:
            continue
        task = Task(
            firm_id=current_firm.id,
            client_id=engagement.client_id,
            engagement_id=engagement.id,
            title=title,
            notes=notes,
        )
        db.add(task)
        tasks_created += 1

    doc_request_created = False
    if template.document_checklist:
        checklist_items = [
            {
                "id": str(uuid.uuid4()),
                "label": item,
                "description": "",
                "is_required": True,
                "status": "pending",
            }
            for item in template.document_checklist
            if isinstance(item, str) and item.strip()
        ]
        if checklist_items:
            doc_request = DocumentRequest(
                firm_id=current_firm.id,
                client_id=engagement.client_id,
                engagement_id=engagement.id,
                title=f"{template.name} — Documents",
                checklist_items=checklist_items,
                status="pending",
            )
            db.add(doc_request)
            doc_request_created = True

    db.commit()
    db.refresh(engagement)

    if engagement.engagement_type:
        populate_from_template(
            db=db,
            firm_id=current_firm.id,
            engagement_id=engagement.id,
            engagement_type=engagement.engagement_type,
        )

    crud_et.increment_use_count(db, template_id, current_firm.id)

    log_event(
        firm_id=current_firm.id,
        event_type="engagement_template.used",
        entity_type="engagement_template",
        entity_id=template_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "client_id": str(payload.client_id),
            "engagement_id": str(engagement.id),
            "tasks_created": tasks_created,
            "doc_request_created": doc_request_created,
        }
    )

    return {
        "engagement_id": str(engagement.id),
        "tasks_created": tasks_created,
        "doc_request_created": doc_request_created,
    }
