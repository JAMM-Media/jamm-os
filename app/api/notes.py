# app/api/notes.py

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.models.firm import Firm
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate, NoteOut
from app.services import note_service

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get("/", response_model=list[NoteOut])
def list_notes(
    entity_type: str = Query(...),
    entity_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return note_service.get_notes(
        db,
        firm_id=current_firm.id,
        entity_type=entity_type,
        entity_id=entity_id,
        requesting_user=current_user,
    )


@router.post("/", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    data: NoteCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return note_service.create_note(
        db,
        firm_id=current_firm.id,
        author_id=current_user.id,
        data=data,
    )


@router.patch("/{note_id}", response_model=NoteOut)
def update_note(
    note_id: UUID,
    data: NoteUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return note_service.update_note(
        db,
        note_id=note_id,
        firm_id=current_firm.id,
        requesting_user=current_user,
        data=data,
    )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    note_service.delete_note(
        db,
        note_id=note_id,
        firm_id=current_firm.id,
        requesting_user=current_user,
    )
