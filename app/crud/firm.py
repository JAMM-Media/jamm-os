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
    """Apply a partial update to a firm.

    settings is MERGED into the existing blob key by key. Every other field is
    replaced normally. Before this, a caller sending a partial settings object
    silently destroyed every key it did not mention, because the whole blob was
    overwritten by setattr: a PATCH setting one key wiped the other two dozen.

    A NULL existing blob merges as if it were empty, which matters because NULL
    is a real production state and not the same thing as {}.

    The merged value is a NEW dict assigned to the attribute, never an in place
    mutation of the existing one. Firm.settings is a plain JSON column with no
    mutation tracking, so an in place update would not be seen by SQLAlchemy and
    would never reach the database.

    An explicit settings of None still nulls the blob, which is left intact as
    the one deliberate way to clear it.
    """
    for key, value in firm_in.model_dump(exclude_unset=True).items():
        if key == "settings" and value is not None:
            value = {**(firm.settings or {}), **value}
        setattr(firm, key, value)
    db.commit()
    db.refresh(firm)
    return firm


def delete_firm(db: Session, firm: Firm) -> None:
    db.delete(firm)
    db.commit()