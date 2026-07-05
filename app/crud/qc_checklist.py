# app/crud/qc_checklist.py

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.qc_checklist import (
    QcChecklistTemplate, QcChecklistItem
)
from app.schemas.qc_checklist import (
    QcChecklistTemplateCreate, QcChecklistTemplateUpdate,
    QcChecklistItemCreate, QcChecklistItemUpdate
)
import uuid
from datetime import datetime, timezone


# --- Template CRUD ---

def create_template(db: Session, firm_id, data: QcChecklistTemplateCreate):
    obj = QcChecklistTemplate(firm_id=firm_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_templates(db: Session, firm_id, include_inactive: bool = False):
    stmt = select(QcChecklistTemplate).where(
        QcChecklistTemplate.firm_id == firm_id
    )
    if not include_inactive:
        stmt = stmt.where(QcChecklistTemplate.is_active == True)
    return db.execute(stmt.order_by(QcChecklistTemplate.name)).scalars().all()


def get_template(db: Session, firm_id, template_id):
    return db.execute(
        select(QcChecklistTemplate).where(
            QcChecklistTemplate.id == template_id,
            QcChecklistTemplate.firm_id == firm_id,
        )
    ).scalars().first()


def update_template(db: Session, obj: QcChecklistTemplate, data: QcChecklistTemplateUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def soft_delete_template(db: Session, obj: QcChecklistTemplate):
    obj.is_active = False
    db.commit()


def restore_template(db: Session, obj: QcChecklistTemplate):
    obj.is_active = True
    db.commit()


def get_template_for_engagement_type(db: Session, firm_id, engagement_type: str):
    return db.execute(
        select(QcChecklistTemplate).where(
            QcChecklistTemplate.firm_id == firm_id,
            QcChecklistTemplate.engagement_type == engagement_type,
            QcChecklistTemplate.is_active == True,
        )
    ).scalars().first()


# --- Item CRUD ---

def create_item(db: Session, firm_id, data: QcChecklistItemCreate):
    obj = QcChecklistItem(firm_id=firm_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_items(db: Session, firm_id, engagement_id):
    return db.execute(
        select(QcChecklistItem)
        .where(
            QcChecklistItem.firm_id == firm_id,
            QcChecklistItem.engagement_id == engagement_id,
        )
        .order_by(
            QcChecklistItem.order,
            QcChecklistItem.created_at,
        )
    ).scalars().all()


def get_item(db: Session, firm_id, item_id):
    return db.execute(
        select(QcChecklistItem).where(
            QcChecklistItem.id == item_id,
            QcChecklistItem.firm_id == firm_id,
        )
    ).scalars().first()


def check_item(db: Session, obj: QcChecklistItem, user_id):
    obj.is_checked = True
    obj.checked_by_id = user_id
    obj.checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


def uncheck_item(db: Session, obj: QcChecklistItem):
    obj.is_checked = False
    obj.checked_by_id = None
    obj.checked_at = None
    db.commit()
    db.refresh(obj)
    return obj


def update_item(db: Session, obj: QcChecklistItem, data: QcChecklistItemUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_item(db: Session, obj: QcChecklistItem):
    db.delete(obj)
    db.commit()


def populate_from_template(db: Session, firm_id, engagement_id, engagement_type: str):
    template = get_template_for_engagement_type(db, firm_id, engagement_type)
    if not template:
        return []
    items = []
    for i, title in enumerate(template.items):
        item = QcChecklistItem(
            firm_id=firm_id,
            engagement_id=engagement_id,
            title=title,
            order=i,
            is_from_template=True,
        )
        db.add(item)
        items.append(item)
    db.commit()
    return items


def get_unchecked_counts(db: Session, firm_id, engagement_ids: list):
    if not engagement_ids:
        return {}
    rows = db.execute(
        select(QcChecklistItem.engagement_id, QcChecklistItem.is_checked)
        .where(
            QcChecklistItem.firm_id == firm_id,
            QcChecklistItem.engagement_id.in_(engagement_ids),
        )
    ).all()
    counts: dict = {}
    for engagement_id, is_checked in rows:
        if not is_checked:
            counts[engagement_id] = counts.get(engagement_id, 0) + 1
    return counts
