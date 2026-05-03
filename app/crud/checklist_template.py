# app/crud/checklist_template.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.checklist_template import ChecklistTemplate
from app.schemas.checklist_template import ChecklistTemplateCreate, ChecklistTemplateUpdate


def create_template(
    db: Session,
    data: ChecklistTemplateCreate,
    firm_id: UUID,
) -> ChecklistTemplate:
    template = ChecklistTemplate(
        firm_id=firm_id,
        name=data.name,
        engagement_type=data.engagement_type,
        items=[item.model_dump() for item in data.items],
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_template(
    db: Session,
    template_id: UUID,
    firm_id: UUID,
) -> ChecklistTemplate | None:
    stmt = select(ChecklistTemplate).where(
        ChecklistTemplate.id == template_id,
        ChecklistTemplate.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def list_templates(
    db: Session,
    firm_id: UUID,
    engagement_type: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[ChecklistTemplate]:
    stmt = select(ChecklistTemplate).where(ChecklistTemplate.firm_id == firm_id)
    if engagement_type is not None:
        stmt = stmt.where(ChecklistTemplate.engagement_type == engagement_type)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_template(
    db: Session,
    template_id: UUID,
    firm_id: UUID,
    data: ChecklistTemplateUpdate,
) -> ChecklistTemplate | None:
    template = get_template(db, template_id, firm_id)
    if template is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "items" and value is not None:
            value = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


def delete_template(
    db: Session,
    template_id: UUID,
    firm_id: UUID,
) -> bool:
    template = get_template(db, template_id, firm_id)
    if template is None:
        return False
    db.delete(template)
    db.commit()
    return True
