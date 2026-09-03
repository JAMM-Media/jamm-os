# app/crud/intake_answer.py

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.intake_answer import IntakeAnswer


def create_intake_answer(db: Session, *, answer: IntakeAnswer) -> IntakeAnswer:
    """Append-only write. No update path is exposed on this table."""
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


def bulk_create_intake_answers(
    db: Session, *, answers: list[IntakeAnswer]
) -> list[IntakeAnswer]:
    """Bulk append-only write. All answers committed in a single transaction."""
    for a in answers:
        db.add(a)
    db.commit()
    for a in answers:
        db.refresh(a)
    return answers
