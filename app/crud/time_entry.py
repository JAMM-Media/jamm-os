# app/crud/time_entry.py

import uuid
from datetime import date as date_type
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.time_entry import TimeEntry
from app.schemas.time_entry import TimeEntryCreate, TimeEntryUpdate


def get_time_entry(db: Session, entry_id: uuid.UUID, firm_id: uuid.UUID) -> Optional[TimeEntry]:
    stmt = select(TimeEntry).where(
        TimeEntry.id == entry_id,
        TimeEntry.firm_id == firm_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_time_entries(
    db: Session,
    firm_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    engagement_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    is_billable: Optional[bool] = None,
    is_billed: Optional[bool] = None,
    entry_date: Optional[date_type] = None,
    start_date: Optional[date_type] = None,
    end_date: Optional[date_type] = None,
) -> list[TimeEntry]:
    stmt = select(TimeEntry).where(TimeEntry.firm_id == firm_id)
    if engagement_id is not None:
        stmt = stmt.where(TimeEntry.engagement_id == engagement_id)
    if user_id is not None:
        stmt = stmt.where(TimeEntry.user_id == user_id)
    if is_billable is not None:
        stmt = stmt.where(TimeEntry.is_billable == is_billable)
    if is_billed is not None:
        stmt = stmt.where(TimeEntry.is_billed == is_billed)
    if entry_date is not None:
        stmt = stmt.where(TimeEntry.date == entry_date)
    if start_date is not None:
        stmt = stmt.where(TimeEntry.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(TimeEntry.date <= end_date)
    stmt = stmt.order_by(TimeEntry.date.desc(), TimeEntry.created_at.desc())
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_time_entries_count(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    is_billable: Optional[bool] = None,
    is_billed: Optional[bool] = None,
    entry_date: Optional[date_type] = None,
    start_date: Optional[date_type] = None,
    end_date: Optional[date_type] = None,
) -> int:
    stmt = select(func.count()).select_from(TimeEntry).where(TimeEntry.firm_id == firm_id)
    if engagement_id is not None:
        stmt = stmt.where(TimeEntry.engagement_id == engagement_id)
    if user_id is not None:
        stmt = stmt.where(TimeEntry.user_id == user_id)
    if is_billable is not None:
        stmt = stmt.where(TimeEntry.is_billable == is_billable)
    if is_billed is not None:
        stmt = stmt.where(TimeEntry.is_billed == is_billed)
    if entry_date is not None:
        stmt = stmt.where(TimeEntry.date == entry_date)
    if start_date is not None:
        stmt = stmt.where(TimeEntry.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(TimeEntry.date <= end_date)
    return db.execute(stmt).scalar_one()


def create_time_entry(
    db: Session,
    entry_in: TimeEntryCreate,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TimeEntry:
    entry = TimeEntry(
        **entry_in.model_dump(),
        firm_id=firm_id,
        user_id=user_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_time_entry(db: Session, entry: TimeEntry, entry_in: TimeEntryUpdate) -> TimeEntry:
    for field, value in entry_in.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


def delete_time_entry(db: Session, entry: TimeEntry) -> None:
    db.delete(entry)
    db.commit()


def get_unbilled_entries_for_engagement(
    db: Session,
    engagement_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> list[TimeEntry]:
    stmt = select(TimeEntry).where(
        TimeEntry.engagement_id == engagement_id,
        TimeEntry.firm_id == firm_id,
        TimeEntry.is_billable == True,
        TimeEntry.is_billed == False,
    )
    return list(db.execute(stmt).scalars().all())


def mark_entries_as_billed(
    db: Session,
    entry_ids: list[uuid.UUID],
    invoice_id: uuid.UUID,
) -> None:
    stmt = select(TimeEntry).where(TimeEntry.id.in_(entry_ids))
    entries = list(db.execute(stmt).scalars().all())
    for entry in entries:
        entry.is_billed = True
        entry.invoice_id = invoice_id
    db.commit()


def get_entries_for_date(
    db: Session,
    user_id: uuid.UUID,
    firm_id: uuid.UUID,
    entry_date: date_type,
    is_submitted: Optional[bool] = None,
) -> list[TimeEntry]:
    stmt = select(TimeEntry).where(
        TimeEntry.firm_id == firm_id,
        TimeEntry.user_id == user_id,
        TimeEntry.date == entry_date,
    )
    if is_submitted is not None:
        stmt = stmt.where(TimeEntry.is_submitted == is_submitted)
    return list(db.execute(stmt).scalars().all())


def get_entries_for_range(
    db: Session,
    firm_id: uuid.UUID,
    start_date: date_type,
    end_date: date_type,
    user_id: Optional[uuid.UUID] = None,
) -> list[TimeEntry]:
    stmt = select(TimeEntry).where(
        TimeEntry.firm_id == firm_id,
        TimeEntry.date >= start_date,
        TimeEntry.date <= end_date,
    )
    if user_id is not None:
        stmt = stmt.where(TimeEntry.user_id == user_id)
    stmt = stmt.order_by(TimeEntry.date.asc(), TimeEntry.user_id.asc())
    return list(db.execute(stmt).scalars().all())
