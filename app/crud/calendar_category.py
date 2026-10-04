# app/crud/calendar_category.py

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.calendar_category import CalendarCategory
from app.schemas.calendar_category import CalendarCategoryCreate, CalendarCategoryUpdate


def get_category_for_firm(
    db: Session, category_id: UUID, firm_id: UUID
) -> CalendarCategory | None:
    return db.execute(
        select(CalendarCategory).where(
            CalendarCategory.id == category_id,
            CalendarCategory.firm_id == firm_id,
        )
    ).scalar_one_or_none()


def list_categories(
    db: Session,
    firm_id: UUID,
    include_inactive: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[CalendarCategory], int]:
    stmt = select(CalendarCategory).where(CalendarCategory.firm_id == firm_id)
    if not include_inactive:
        stmt = stmt.where(CalendarCategory.is_active.is_(True))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(
        CalendarCategory.sort_order,
        CalendarCategory.name,
        CalendarCategory.id,
    ).offset(offset).limit(limit)
    items = list(db.execute(stmt).scalars())
    return items, total


def create_category(
    db: Session,
    payload: CalendarCategoryCreate,
    firm_id: UUID,
) -> CalendarCategory:
    cat = CalendarCategory(
        firm_id=firm_id,
        **payload.model_dump(),
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def update_category(
    db: Session,
    cat: CalendarCategory,
    payload: CalendarCategoryUpdate,
) -> CalendarCategory:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, key, value)
    db.commit()
    db.refresh(cat)
    return cat
