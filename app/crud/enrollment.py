# app/crud/enrollment.py

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment


def get_enrollment_for_firm(
    db: Session, enrollment_id: UUID, firm_id: UUID
) -> Enrollment | None:
    return db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.firm_id == firm_id,
    ).first()
