from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate, ContactOut
from app.crud import contact as crud_contact

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.get("/", response_model=List[ContactOut])
def list_contacts(client_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return crud_contact.get_contacts(db, client_id=client_id)

@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: UUID, db: Session = Depends(get_db)):
    contact = crud_contact.get_contact(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.post("/", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(contact_in: ContactCreate, db: Session = Depends(get_db)):
    return crud_contact.create_contact(db, contact_in)

@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: UUID, contact_in: ContactUpdate, db: Session = Depends(get_db)):
    contact = crud_contact.get_contact(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return crud_contact.update_contact(db, contact, contact_in)

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: UUID, db: Session = Depends(get_db)):
    contact = crud_contact.get_contact(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    crud_contact.delete_contact(db, contact)
