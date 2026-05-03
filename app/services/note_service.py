# app/services/note_service.py

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import note as crud_note
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate, NoteOut
from app.core.enums import UserRole

VALID_ENTITY_TYPES = {"client", "engagement", "task", "document"}


def _enrich(note_out: NoteOut, db: Session) -> NoteOut:
    """Populate author_name from the users table."""
    from sqlalchemy import select
    stmt = select(User).where(User.id == note_out.author_id)
    user = db.execute(stmt).scalar_one_or_none()
    if user and user.full_name:
        note_out.author_name = user.full_name
    return note_out


def get_notes(
    db: Session,
    firm_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    requesting_user: User,
) -> list[NoteOut]:
    notes = crud_note.get_notes_for_entity(
        db,
        firm_id=firm_id,
        entity_type=entity_type,
        entity_id=entity_id,
        requesting_user_id=requesting_user.id,
    )
    result = []
    for note in notes:
        note_out = NoteOut.model_validate(note)
        _enrich(note_out, db)
        result.append(note_out)
    return result


def create_note(
    db: Session,
    firm_id: uuid.UUID,
    author_id: uuid.UUID,
    data: NoteCreate,
) -> NoteOut:
    if data.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type '{data.entity_type}'. Must be one of: {sorted(VALID_ENTITY_TYPES)}",
        )
    note = crud_note.create_note(db, firm_id=firm_id, author_id=author_id, data=data)
    note_out = NoteOut.model_validate(note)
    _enrich(note_out, db)
    return note_out


def update_note(
    db: Session,
    note_id: uuid.UUID,
    firm_id: uuid.UUID,
    requesting_user: User,
    data: NoteUpdate,
) -> NoteOut:
    note = crud_note.get_note_by_id(db, note_id=note_id, firm_id=firm_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if note.author_id != requesting_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author can edit this note",
        )
    note = crud_note.update_note(db, note=note, data=data)
    note_out = NoteOut.model_validate(note)
    _enrich(note_out, db)
    return note_out


def delete_note(
    db: Session,
    note_id: uuid.UUID,
    firm_id: uuid.UUID,
    requesting_user: User,
) -> None:
    note = crud_note.get_note_by_id(db, note_id=note_id, firm_id=firm_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    # staff can only delete their own notes; managers and firm_owners can delete any
    if requesting_user.role == UserRole.staff and note.author_id != requesting_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff can only delete their own notes",
        )

    crud_note.soft_delete_note(db, note=note)
