# app/crud/note.py

import uuid
from typing import Optional

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.models.note import Note
from app.schemas.note import NoteCreate, NoteUpdate


def create_note(
    db: Session,
    firm_id: uuid.UUID,
    author_id: uuid.UUID,
    data: NoteCreate,
) -> Note:
    note = Note(
        firm_id=firm_id,
        author_id=author_id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        body=data.body,
        is_private=data.is_private,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_notes_for_entity(
    db: Session,
    firm_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    include_private: bool = True,
) -> list[Note]:
    stmt = select(Note).where(
        Note.firm_id == firm_id,
        Note.entity_type == entity_type,
        Note.entity_id == entity_id,
        Note.is_deleted == False,  # noqa: E712
        or_(
            Note.is_private == False,  # noqa: E712
            and_(
                Note.is_private == True,  # noqa: E712
                Note.author_id == requesting_user_id,
            ),
        ),
    )
    return list(db.execute(stmt).scalars().all())


def get_note_by_id(
    db: Session,
    note_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[Note]:
    stmt = select(Note).where(
        Note.id == note_id,
        Note.firm_id == firm_id,
        Note.is_deleted == False,  # noqa: E712
    )
    return db.execute(stmt).scalar_one_or_none()


def update_note(db: Session, note: Note, data: NoteUpdate) -> Note:
    note.body = data.body
    db.commit()
    db.refresh(note)
    return note


def soft_delete_note(db: Session, note: Note) -> Note:
    note.is_deleted = True
    db.commit()
    db.refresh(note)
    return note
