# app/services/time_entry_service.py

import csv
import io
from collections import defaultdict
from datetime import date as date_type, datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import NotificationType, RecipientType, UserRole
from app.crud import notification as crud_notification
from app.crud import time_entry as crud_time_entry
from app.models.engagement import Engagement
from app.models.user import User
from app.schemas.notification import NotificationCreate
from app.schemas.time_entry import SubmittedEditPayload, TimesheetSummaryRow
from app.services.behavioral_log import log_event


def create_time_entry(
    *,
    db: Session,
    payload,  # TimeEntryCreate
    firm_id: UUID,
    current_user: User,
):
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == payload.engagement_id,
            Engagement.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    entry = crud_time_entry.create_time_entry(
        db,
        entry_in=payload,
        firm_id=firm_id,
        user_id=current_user.id,
    )

    log_event(
        firm_id=firm_id,
        event_type="time_entry.created",
        entity_type="time_entry",
        entity_id=entry.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "hours": float(entry.hours) if entry.hours else None,
            "billable": entry.is_billable if hasattr(entry, 'is_billable') else None,
            "engagement_id": str(entry.engagement_id) if entry.engagement_id else None,
            "engagement_type": str(engagement.engagement_type)
                if engagement.engagement_type else None,
        }
    )

    return entry


def update_time_entry(
    *,
    db: Session,
    entry_id: UUID,
    payload,  # TimeEntryUpdate
    firm_id: UUID,
    current_user: User,
):
    entry = crud_time_entry.get_time_entry(db, entry_id, firm_id=firm_id)
    if not entry:
        return None, "not_found"
    if current_user.role == UserRole.staff and entry.user_id != current_user.id:
        return None, "access_denied"
    if entry.is_billed:
        return None, "billed"

    updated = crud_time_entry.update_time_entry(db, entry, payload)
    log_event(
        firm_id=updated.firm_id,
        event_type="time_entry.edited",
        entity_type="time_entry",
        entity_id=updated.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "hours": float(updated.hours) if updated.hours else None,
            "is_billable": updated.is_billable,
            "engagement_id": str(updated.engagement_id) if updated.engagement_id else None,
        }
    )
    return updated, None


def delete_time_entry(
    *,
    db: Session,
    entry_id: UUID,
    firm_id: UUID,
    current_user: User,
):
    entry = crud_time_entry.get_time_entry(db, entry_id, firm_id=firm_id)
    if not entry:
        return None, "not_found"
    if entry.is_billed:
        return None, "billed"

    hours = float(entry.hours) if entry.hours else None
    entry_firm_id = entry.firm_id

    crud_time_entry.delete_time_entry(db, entry)

    log_event(
        firm_id=entry_firm_id,
        event_type="time_entry.deleted",
        entity_type="time_entry",
        entity_id=entry_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "hours": hours,
        }
    )

    return True, None


def submit_day(
    *,
    db: Session,
    firm_id: UUID,
    current_user: User,
    entry_date: date_type,
):
    entries = crud_time_entry.get_entries_for_date(
        db, user_id=current_user.id, firm_id=firm_id,
        entry_date=entry_date, is_submitted=False,
    )
    if not entries:
        return None, "no_entries"

    now = datetime.now(timezone.utc)
    for entry in entries:
        entry.is_submitted = True
        entry.submitted_at = now
    db.commit()

    return len(entries), None


def get_timesheet_summary(
    *,
    db: Session,
    firm_id: UUID,
    start_date: date_type,
    end_date: date_type,
    user_id: UUID | None,
    current_user: User,
) -> list[TimesheetSummaryRow]:
    if current_user.role == UserRole.staff:
        user_id = current_user.id

    entries = crud_time_entry.get_entries_for_range(
        db, firm_id=firm_id, start_date=start_date, end_date=end_date, user_id=user_id
    )

    user_ids = {e.user_id for e in entries}
    users: dict[UUID, User] = {}
    if user_ids:
        users = {
            u.id: u
            for u in db.execute(
                select(User).where(User.id.in_(user_ids))
            ).scalars().all()
        }

    groups: dict[tuple, list] = defaultdict(list)
    for entry in entries:
        groups[(entry.user_id, entry.date)].append(entry)

    result = []
    for (uid, d), group_entries in sorted(groups.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        user = users.get(uid)
        total_hours = sum(float(e.hours) for e in group_entries)
        billable_hours = sum(float(e.hours) for e in group_entries if e.is_billable)
        billable_pct = round(billable_hours / total_hours * 100, 1) if total_hours > 0 else 0.0
        is_submitted = all(e.is_submitted for e in group_entries)
        has_edits = any(e.edited_after_submission for e in group_entries)
        result.append(TimesheetSummaryRow(
            user_id=uid,
            user_name=user.full_name or user.email if user else "Unknown",
            date=d,
            total_hours=total_hours,
            billable_hours=billable_hours,
            billable_pct=billable_pct,
            entry_count=len(group_entries),
            is_submitted=is_submitted,
            has_edits=has_edits,
        ))

    return result


def edit_submitted_entry(
    *,
    db: Session,
    entry_id: UUID,
    payload: SubmittedEditPayload,
    firm_id: UUID,
    current_user: User,
):
    from app.models.time_entry import TimeEntry
    entry = crud_time_entry.get_time_entry(db, entry_id, firm_id=firm_id)
    if not entry:
        return None, "not_found"
    if not entry.is_submitted:
        return None, "not_submitted"
    if current_user.role == UserRole.staff and entry.user_id != current_user.id:
        return None, "access_denied"

    update_data = payload.model_dump(exclude_unset=True)
    edit_note = update_data.pop("edit_note", None)
    for field, value in update_data.items():
        setattr(entry, field, value)
    entry.edited_after_submission = True
    if edit_note is not None:
        entry.edit_note = edit_note
    db.commit()
    db.refresh(entry)

    managers = db.execute(
        select(User).where(
            User.firm_id == firm_id,
            User.role.in_([UserRole.manager.value, UserRole.firm_owner.value]),
        )
    ).scalars().all()

    note_text = f" {edit_note}" if edit_note else ""
    notif_body = (
        f"{current_user.full_name or current_user.email} edited a submitted time entry "
        f"for {entry.date}.{note_text}"
    ).strip()

    for manager in managers:
        crud_notification.create_notification(
            db=db,
            firm_id=firm_id,
            data=NotificationCreate(
                recipient_id=manager.id,
                recipient_type=RecipientType.staff,
                title="Timesheet entry edited after submission",
                body=notif_body,
                notification_type=NotificationType.system,
                related_entity_type="time_entry",
                related_entity_id=entry.id,
            ),
        )

    return entry, None


def approve_entry(
    *,
    db: Session,
    entry_id: UUID,
    firm_id: UUID,
    current_user: User,
):
    entry = crud_time_entry.get_time_entry(db, entry_id, firm_id=firm_id)
    if not entry:
        return None, "not_found"
    if not entry.is_submitted:
        return None, "not_submitted"

    entry.is_approved = True
    entry.approved_at = datetime.now(timezone.utc)
    entry.approved_by_id = current_user.id
    db.commit()
    db.refresh(entry)

    return entry, None


def get_csv_export(
    *,
    db: Session,
    firm_id: UUID,
    start_date: date_type,
    end_date: date_type,
    user_id: UUID | None,
    current_user: User,
) -> StreamingResponse:
    if current_user.role == UserRole.staff:
        user_id = current_user.id

    entries = crud_time_entry.get_entries_for_range(
        db, firm_id=firm_id, start_date=start_date, end_date=end_date, user_id=user_id
    )

    user_ids = {e.user_id for e in entries}
    engagement_ids = {e.engagement_id for e in entries}

    users: dict[UUID, User] = {}
    if user_ids:
        users = {
            u.id: u
            for u in db.execute(
                select(User).where(User.id.in_(user_ids))
            ).scalars().all()
        }

    engagements: dict[UUID, Engagement] = {}
    if engagement_ids:
        engagements = {
            eng.id: eng
            for eng in db.execute(
                select(Engagement).where(Engagement.id.in_(engagement_ids))
            ).scalars().all()
        }

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Staff", "Engagement", "Activity Type", "Description",
        "Start Time", "End Time", "Hours", "Billable", "Rate", "Value",
        "Submitted", "Approved",
    ])

    for entry in entries:
        user = users.get(entry.user_id)
        engagement = engagements.get(entry.engagement_id)
        hours = float(entry.hours)
        rate = float(entry.hourly_rate)
        value = hours * rate if entry.is_billable else 0.0
        writer.writerow([
            str(entry.date),
            user.full_name or user.email if user else "",
            engagement.name if engagement else "",
            entry.activity_type or "",
            entry.description,
            str(entry.start_time) if entry.start_time else "",
            str(entry.end_time) if entry.end_time else "",
            hours,
            "Yes" if entry.is_billable else "No",
            rate,
            round(value, 2),
            "Yes" if entry.is_submitted else "No",
            "Yes" if entry.is_approved else "No",
        ])

    output.seek(0)
    filename = f"timesheets_{start_date}_{end_date}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
