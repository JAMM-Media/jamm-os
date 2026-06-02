# app/crud/extension.py

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extension import Extension
from app.schemas.extension import ExtensionCreate, ExtensionUpdate, DEFAULT_EXTENDED_DEADLINES


def create_extension(
    db: Session,
    ext_in: ExtensionCreate,
    firm_id: UUID,
) -> Extension:
    """
    Create an Extension record.

    Auto-populates:
    - filed_at: today if not provided
    - extended_deadline: standard IRS extended deadline for the form_type
      if not explicitly provided by the caller
    """
    data = ext_in.model_dump()

    if not data.get("filed_at"):
        data["filed_at"] = date.today()

    if not data.get("extended_deadline"):
        deadline_tuple = DEFAULT_EXTENDED_DEADLINES.get(data["form_type"])
        if deadline_tuple:
            month, day = deadline_tuple
            data["extended_deadline"] = date(date.today().year, month, day)

    ext = Extension(**data, firm_id=firm_id)
    db.add(ext)
    db.commit()
    db.refresh(ext)
    return ext


def get_extension(
    db: Session,
    ext_id: UUID,
    firm_id: UUID,
) -> Extension | None:
    return db.execute(
        select(Extension).where(
            Extension.id == ext_id,
            Extension.firm_id == firm_id,
        )
    ).scalars().first()


def list_extensions(
    db: Session,
    firm_id: UUID,
    engagement_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None,
    status: Optional[str] = None,
) -> list[Extension]:
    stmt = select(Extension).where(Extension.firm_id == firm_id)
    if engagement_id:
        stmt = stmt.where(Extension.engagement_id == engagement_id)
    if client_id:
        stmt = stmt.where(Extension.client_id == client_id)
    if status:
        stmt = stmt.where(Extension.status == status)
    stmt = stmt.order_by(Extension.created_at.desc())
    return db.execute(stmt).scalars().all()


def update_extension(
    db: Session,
    ext: Extension,
    ext_in: ExtensionUpdate,
) -> Extension:
    for key, value in ext_in.model_dump(exclude_unset=True).items():
        setattr(ext, key, value)
    db.commit()
    db.refresh(ext)
    return ext


def get_extension_for_engagement(
    db: Session,
    firm_id: UUID,
    engagement_id: UUID,
) -> Extension | None:
    """
    Returns the most recent extension filed for an engagement.
    Used to check if an extension is already on file.
    """
    return db.execute(
        select(Extension).where(
            Extension.firm_id == firm_id,
            Extension.engagement_id == engagement_id,
        ).order_by(Extension.created_at.desc())
    ).scalars().first()
