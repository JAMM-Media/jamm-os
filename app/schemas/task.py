# app/schemas/task.py

import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskBase(BaseModel):
    title: str
    status: TaskStatus = TaskStatus.TODO
    due_date: date | None = None
    assigned_to: str | None = None
    notes: str | None = None
    is_completed: bool = False


class TaskCreate(TaskBase):
    client_id: uuid.UUID
    engagement_id: uuid.UUID  # Renamed from project_id


class TaskUpdate(BaseModel):
    title: str | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    assigned_to: str | None = None
    notes: str | None = None
    is_completed: bool | None = None
    client_id: uuid.UUID | None = None
    engagement_id: uuid.UUID | None = None  # Renamed from project_id


class TaskOut(TaskBase):
    id: uuid.UUID
    client_id: uuid.UUID
    engagement_id: uuid.UUID  # Renamed from project_id
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: TaskStatus
    due_date: date | None = None

    model_config = ConfigDict(from_attributes=True)