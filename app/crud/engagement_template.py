# app/crud/engagement_template.py

from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.engagement_template import EngagementTemplate
from app.schemas.engagement_template import EngagementTemplateCreate, EngagementTemplateUpdate


def list_templates(db: Session, firm_id: UUID, active_only: bool = True) -> list[EngagementTemplate]:
    stmt = select(EngagementTemplate).where(EngagementTemplate.firm_id == firm_id)
    if active_only:
        stmt = stmt.where(EngagementTemplate.is_active == True)
    stmt = stmt.order_by(EngagementTemplate.use_count.desc(), EngagementTemplate.name.asc())
    return list(db.execute(stmt).scalars().all())


def get_template(db: Session, template_id: UUID, firm_id: UUID) -> EngagementTemplate | None:
    stmt = select(EngagementTemplate).where(
        EngagementTemplate.id == template_id,
        EngagementTemplate.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def create_template(db: Session, template_in: EngagementTemplateCreate, firm_id: UUID) -> EngagementTemplate:
    data = template_in.model_dump()
    data['task_templates'] = [
        t.model_dump() if hasattr(t, 'model_dump') else t
        for t in data.get('task_templates', [])
    ]
    template = EngagementTemplate(**data, firm_id=firm_id)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(db: Session, template: EngagementTemplate, payload: EngagementTemplateUpdate) -> EngagementTemplate:
    data = payload.model_dump(exclude_unset=True)
    if 'task_templates' in data and data['task_templates'] is not None:
        data['task_templates'] = [
            t.model_dump() if hasattr(t, 'model_dump') else t
            for t in data['task_templates']
        ]
    for key, value in data.items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template: EngagementTemplate) -> None:
    template.is_active = False
    db.commit()


def increment_use_count(db: Session, template_id: UUID, firm_id: UUID) -> None:
    template = get_template(db, template_id, firm_id)
    if template:
        template.use_count += 1
        db.commit()


def list_active_recurring_templates(db: Session) -> list[EngagementTemplate]:
    """Returns all recurring templates across all firms where is_recurring=True and is_active=True.
    Used exclusively by the scheduler job."""
    stmt = (
        select(EngagementTemplate)
        .where(EngagementTemplate.is_recurring == True)
        .where(EngagementTemplate.is_active == True)
    )
    return list(db.execute(stmt).scalars().all())
