# app/services/document_request_template_service.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import document_request_template as crud_drt
from app.models.document_request_template import DocumentRequestTemplate
from app.services.behavioral_log import log_event


def create_template(
    *,
    db: Session,
    payload,  # DocumentRequestTemplateCreate
    firm_id,
    current_user_id,
):
    template = crud_drt.create_template(db, payload, firm_id)
    log_event(
        firm_id=firm_id,
        event_type="document_request_template.created",
        entity_type="document_request_template",
        entity_id=template.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "name": template.name,
            "engagement_type": template.engagement_type,
            "item_count": len(template.items) if template.items else 0,
        }
    )
    return template


def update_template(
    *,
    db: Session,
    template,
    payload,  # DocumentRequestTemplateUpdate
    firm_id,
    current_user_id,
):
    updated = crud_drt.update_template(db, template, payload)
    log_event(
        firm_id=firm_id,
        event_type="document_request_template.updated",
        entity_type="document_request_template",
        entity_id=updated.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "name": updated.name,
            "engagement_type": updated.engagement_type,
        }
    )
    return updated


def delete_template(
    *,
    db: Session,
    template,
    template_id,
    firm_id,
    current_user_id,
):
    crud_drt.delete_template(db, template)
    log_event(
        firm_id=firm_id,
        event_type="document_request_template.deleted",
        entity_type="document_request_template",
        entity_id=template_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={}
    )


def get_suggested_template(
    db: Session,
    firm_id,
    engagement_type: str,
) -> DocumentRequestTemplate | None:
    stmt = (
        select(DocumentRequestTemplate)
        .where(DocumentRequestTemplate.firm_id == firm_id)
        .where(DocumentRequestTemplate.engagement_type == engagement_type)
        .where(DocumentRequestTemplate.is_active == True)
        .order_by(DocumentRequestTemplate.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()
