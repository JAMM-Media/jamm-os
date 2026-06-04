# app/api/contacts.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from uuid import UUID

from app.db.session import get_db
from app.models.contact import Contact
from app.models.firm import Firm
from app.schemas.contact import ContactCreate, ContactUpdate, ContactOut
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import contact as crud_contact
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/", response_model=PaginatedResponse[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    client_id: UUID | None = None,
    limit: int = Query(50, le=1000),
    offset: int = 0,
    desc: bool = False,
):
    query = crud_contact.get_contacts_for_firm(db, current_firm.id, client_id)
    query = query.order_by(Contact.created_at.desc() if desc else Contact.created_at)
    return paginate(query, limit=limit, offset=offset)


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    contact = crud_contact.get_contact_for_firm(db, contact_id, current_firm.id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.post("/", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_in: ContactCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    return crud_contact.create_contact(db, contact_in, firm_id=current_firm.id)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: UUID,
    contact_in: ContactUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    contact = crud_contact.get_contact_for_firm(db, contact_id, current_firm.id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return crud_contact.update_contact(db, contact, contact_in)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    contact = crud_contact.get_contact_for_firm(db, contact_id, current_firm.id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    crud_contact.delete_contact(db, contact)