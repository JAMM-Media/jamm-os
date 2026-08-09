# app/crud/task.py

from sqlalchemy.orm import Session
from uuid import UUID

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


def get_task_for_firm(db: Session, task_id: UUID, firm_id: UUID) -> Task | None:
    return db.query(Task).filter(
        Task.id == task_id,
        Task.firm_id == firm_id,
    ).first()


def get_tasks_for_user(
    db: Session,
    user_id: UUID,
    firm_id: UUID,
    status: str | None = None,
):
    """Returns a query of tasks assigned to a specific user, scoped to the firm."""
    query = db.query(Task).filter(
        Task.assigned_to == user_id,
        Task.firm_id == firm_id,
    )
    if status:
        query = query.filter(Task.status == status)
    return query


def get_tasks_for_firm(
    db: Session,
    firm_id: UUID,
    client_id: UUID | None = None,
    engagement_id: UUID | None = None,
):
    """Returns a query scoped to the firm, for use with paginate()."""
    query = db.query(Task).filter(Task.firm_id == firm_id)
    if client_id:
        query = query.filter(Task.client_id == client_id)
    if engagement_id:
        query = query.filter(Task.engagement_id == engagement_id)
    return query


def create_task(
    db: Session,
    task_in: TaskCreate,
    firm_id: UUID,
    is_self_created: bool = False,
) -> Task:
    data = task_in.model_dump()
    # status and task_type are Enum members on the schema and plain String
    # columns on the model. Both enums subclass str so they would bind
    # correctly anyway, but unwrapping keeps what lands in the row identical
    # to what a raw string caller would have written.
    for _enum_field in ("status", "task_type"):
        value = data.get(_enum_field)
        if value is not None:
            data[_enum_field] = getattr(value, "value", value)
    task = Task(**data, firm_id=firm_id, is_self_created=is_self_created)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: Task, task_in: TaskUpdate) -> Task:
    for key, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task):
    db.delete(task)
    db.commit()