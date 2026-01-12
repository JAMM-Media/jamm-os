from sqlalchemy.orm import Session
from uuid import UUID
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate

def get_contact(db: Session, contact_id: UUID) -> Contact | None:
    return db.query(Contact).filter(Contact.id == contact_id).first()

def get_contacts(db: Session, client_id: UUID | None = None):
    query = db.query(Contact)
    if client_id:
        query = query.filter(Contact.client_id == client_id)
    return query.all()

def create_contact(db: Session, contact_in: ContactCreate) -> Contact:
    contact = Contact(**contact_in.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact

def update_contact(db: Session, contact: Contact, contact_in: ContactUpdate) -> Contact:
    for key, value in contact_in.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    db.commit()
    db.refresh(contact)
    return contact

def delete_contact(db: Session, contact: Contact):
    db.delete(contact)
    db.commit()
