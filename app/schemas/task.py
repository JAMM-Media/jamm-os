import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class TaskBase(BaseModel):
    title: str
    status: str = "todo"
    due_date: date | None = None
    assigned_to: str | None = None
    notes: str | None = None
    is_completed: bool = False


class TaskCreate(TaskBase):
    client_id: uuid.UUID
    project_id: uuid.UUID


class TaskUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    due_date: date | None = None
    assigned_to: str | None = None
    notes: str | None = None
    is_completed: bool | None = None
    client_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class TaskOut(TaskBase):
    id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    due_date: date | None = None

    model_config = ConfigDict(from_attributes=True)
