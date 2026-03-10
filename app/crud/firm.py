# app/crud/firm.py

from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.firm import Firm
from app.schemas.firm import FirmCreate, FirmUpdate


def get_firm(db: Session, firm_id: UUID) -> Firm | None:
    stmt = select(Firm).where(Firm.id == firm_id)
    return db.execute(stmt).scalars().first()


def get_firm_by_slug(db: Session, slug: str) -> Firm | None:
    stmt = select(Firm).where(Firm.slug == slug)
    return db.execute(stmt).scalars().first()


def get_firms(db: Session):
    """Returns a query for use with the paginate() utility."""
    return db.query(Firm)


def create_firm(db: Session, firm_in: FirmCreate) -> Firm:
    firm = Firm(**firm_in.model_dump())
    db.add(firm)
    db.commit()
    db.refresh(firm)
    return firm


def update_firm(db: Session, firm: Firm, firm_in: FirmUpdate) -> Firm:
    for key, value in firm_in.model_dump(exclude_unset=True).items():
        setattr(firm, key, value)
    db.commit()
    db.refresh(firm)
    return firm


def delete_firm(db: Session, firm: Firm) -> None:
    db.delete(firm)
    db.commit()