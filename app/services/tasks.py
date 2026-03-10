# app/services/tasks.py

from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from app.models.task import Task


def get_tasks_filtered(
    db: Session,
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,  # Renamed from project_id
) -> list[Task]:
    query = db.query(Task)

    if client_id:
        query = query.filter(Task.client_id == client_id)

    if engagement_id:
        query = query.filter(Task.engagement_id == engagement_id)  # Renamed from project_id

    return query.all()