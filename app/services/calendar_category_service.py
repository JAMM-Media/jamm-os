# app/services/calendar_category_service.py

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import calendar_category as crud_cat
from app.models.calendar_category import CalendarCategory
from app.schemas.calendar_category import CalendarCategoryCreate, CalendarCategoryUpdate
from app.services.behavioral_log import log_event


def list_categories(
    db: Session,
    firm_id: UUID,
    include_inactive: bool,
    limit: int,
    offset: int,
) -> dict:
    items, total = crud_cat.list_categories(db, firm_id, include_inactive, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _name_taken(db: Session, firm_id: UUID, name: str, exclude_id: UUID | None = None) -> bool:
    stmt = select(CalendarCategory).where(
        CalendarCategory.firm_id == firm_id,
        func.lower(CalendarCategory.name) == name.strip().lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(CalendarCategory.id != exclude_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def create_category(
    db: Session,
    payload: CalendarCategoryCreate,
    firm_id: UUID,
    current_user_id: UUID,
) -> CalendarCategory:
    if _name_taken(db, firm_id, payload.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists in the firm.",
        )
    try:
        cat = crud_cat.create_category(db, payload, firm_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists in the firm.",
        )
    log_event(
        firm_id=firm_id,
        event_type="calendar_category.created",
        entity_type="calendar_category",
        entity_id=cat.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"sort_order": cat.sort_order},
    )
    return cat


def update_category(
    db: Session,
    category_id: UUID,
    payload: CalendarCategoryUpdate,
    firm_id: UUID,
    current_user_id: UUID,
) -> CalendarCategory:
    cat = crud_cat.get_category_for_firm(db, category_id, firm_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] and _name_taken(db, firm_id, updates["name"], exclude_id=category_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists in the firm.",
        )
    real_changes = {k: v for k, v in updates.items() if getattr(cat, k) != v}
    if not real_changes:
        return cat
    try:
        cat = crud_cat.update_category(db, cat, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists in the firm.",
        )
    log_event(
        firm_id=firm_id,
        event_type="calendar_category.updated",
        entity_type="calendar_category",
        entity_id=cat.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"changed_fields": list(real_changes.keys())},
    )
    return cat
