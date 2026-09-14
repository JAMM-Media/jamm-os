# app/crud/document_request_template.py

from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.document_request_template import DocumentRequestTemplate
from app.schemas.document_request_template import (
    DocumentRequestTemplateCreate,
    DocumentRequestTemplateUpdate,
)


def list_templates(
    db: Session, firm_id: UUID, active_only: bool = True
) -> list[DocumentRequestTemplate]:
    stmt = select(DocumentRequestTemplate).where(
        DocumentRequestTemplate.firm_id == firm_id
    )
    if active_only:
        stmt = stmt.where(DocumentRequestTemplate.is_active == True)
    stmt = stmt.order_by(
        DocumentRequestTemplate.use_count.desc(),
        DocumentRequestTemplate.name.asc(),
    )
    return list(db.execute(stmt).scalars().all())


def get_template(
    db: Session, template_id: UUID, firm_id: UUID
) -> DocumentRequestTemplate | None:
    stmt = select(DocumentRequestTemplate).where(
        DocumentRequestTemplate.id == template_id,
        DocumentRequestTemplate.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def create_template(
    db: Session,
    template_in: DocumentRequestTemplateCreate,
    firm_id: UUID,
) -> DocumentRequestTemplate:
    data = template_in.model_dump()
    data["items"] = [
        item.model_dump() if hasattr(item, "model_dump") else item
        for item in data.get("items", [])
    ]
    template = DocumentRequestTemplate(**data, firm_id=firm_id)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template: DocumentRequestTemplate,
    payload: DocumentRequestTemplateUpdate,
) -> DocumentRequestTemplate:
    data = payload.model_dump(exclude_unset=True)
    if "items" in data and data["items"] is not None:
        data["items"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in data["items"]
        ]
    for key, value in data.items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template: DocumentRequestTemplate) -> None:
    template.is_active = False
    db.commit()


def increment_use_count(
    db: Session, template_id: UUID, firm_id: UUID
) -> None:
    template = get_template(db, template_id, firm_id)
    if template:
        template.use_count += 1
        db.commit()
