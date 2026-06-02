# app/crud/contact.py

from sqlalchemy.orm import Session
from uuid import UUID

from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate


def get_contact_for_firm(db: Session, contact_id: UUID, firm_id: UUID) -> Contact | None:
    return db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.firm_id == firm_id,
    ).first()


def get_contact(db: Session, contact_id: UUID) -> Contact | None:
    return db.query(Contact).filter(Contact.id == contact_id).first()


def get_contacts_for_firm(db: Session, firm_id: UUID, client_id: UUID | None = None):
    """Returns a query scoped to the firm, for use with paginate()."""
    query = db.query(Contact).filter(Contact.firm_id == firm_id)
    if client_id:
        query = query.filter(Contact.client_id == client_id)
    return query


def get_contacts(db: Session, client_id: UUID | None = None):
    query = db.query(Contact)
    if client_id:
        query = query.filter(Contact.client_id == client_id)
    return query


def create_contact(db: Session, contact_in: ContactCreate, firm_id: UUID) -> Contact:
    data = contact_in.model_dump()
    contact = Contact(**data, firm_id=firm_id)
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