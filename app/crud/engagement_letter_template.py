# app/crud/engagement_letter_template.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.engagement_letter_template import EngagementLetterTemplate
from app.schemas.engagement_letter_template import (
    EngagementLetterTemplateCreate,
    EngagementLetterTemplateUpdate,
)


def create_template(
    db: Session,
    schema: EngagementLetterTemplateCreate,
    firm_id: UUID,
) -> EngagementLetterTemplate:
    template = EngagementLetterTemplate(
        firm_id=firm_id,
        name=schema.name,
        engagement_type=schema.engagement_type,
        body_html=schema.body_html,
        variable_fields=schema.variable_fields,
        is_active=schema.is_active,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_template(
    db: Session,
    template_id: UUID,
    firm_id: UUID,
) -> EngagementLetterTemplate | None:
    stmt = select(EngagementLetterTemplate).where(
        EngagementLetterTemplate.id == template_id,
        EngagementLetterTemplate.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def list_templates(
    db: Session,
    firm_id: UUID,
    engagement_type: str | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[EngagementLetterTemplate]:
    stmt = select(EngagementLetterTemplate).where(EngagementLetterTemplate.firm_id == firm_id)
    if engagement_type is not None:
        stmt = stmt.where(EngagementLetterTemplate.engagement_type == engagement_type)
    if is_active is not None:
        stmt = stmt.where(EngagementLetterTemplate.is_active == is_active)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_template(
    db: Session,
    template: EngagementLetterTemplate,
    schema: EngagementLetterTemplateUpdate,
) -> EngagementLetterTemplate:
    updates = schema.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(template, key, value)
    if "variable_fields" in updates:
        flag_modified(template, "variable_fields")
    db.commit()
    db.refresh(template)
    return template


def delete_template(
    db: Session,
    template: EngagementLetterTemplate,
) -> None:
    template.is_active = False
    db.commit()
