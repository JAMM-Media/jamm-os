# app/schemas/task.py

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskType(str, Enum):
    """CLIENT tasks belong to an engagement, and their assignee must be a
    member of that engagement. INTERNAL tasks belong to the firm, need no
    engagement, and may be assigned to any member of the firm."""

    CLIENT = "client"
    INTERNAL = "internal"


class TaskBase(BaseModel):
    title: str
    status: TaskStatus = TaskStatus.TODO
    due_date: date | None = None
    assigned_to: uuid.UUID | None = None
    notes: str | None = None
    is_completed: bool = False


class TaskCreate(TaskBase):
    # Defaults to CLIENT so every existing caller that passes a client_id and
    # an engagement_id keeps its exact current meaning without being changed.
    task_type: TaskType = TaskType.CLIENT
    client_id: uuid.UUID | None = None
    engagement_id: uuid.UUID | None = None  # Renamed from project_id

    @model_validator(mode="after")
    def _enforce_type_branch(self):
        """Shape only. Whether the assignee is actually ON the engagement
        needs the database and is enforced in task_service.create_task."""
        if self.task_type == TaskType.CLIENT:
            if self.engagement_id is None or self.client_id is None:
                raise ValueError(
                    "A client task requires both client_id and engagement_id. "
                    "Use task_type='internal' for a task with no engagement."
                )
        else:
            if self.engagement_id is not None or self.client_id is not None:
                raise ValueError(
                    "An internal task must not carry client_id or engagement_id. "
                    "Use task_type='client' for engagement work."
                )
        return self


class TaskUpdate(BaseModel):
    title: str | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    assigned_to: uuid.UUID | None = None
    notes: str | None = None
    is_completed: bool | None = None
    client_id: uuid.UUID | None = None
    engagement_id: uuid.UUID | None = None  # Renamed from project_id


class TaskOut(TaskBase):
    id: uuid.UUID
    task_type: TaskType
    client_id: uuid.UUID | None = None
    engagement_id: uuid.UUID | None = None  # Renamed from project_id
    is_self_created: bool = False
    created_at: datetime
    updated_at: datetime
    assigned_to_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: TaskStatus
    due_date: date | None = None

    model_config = ConfigDict(from_attributes=True)


class BulkTaskFieldUpdate(BaseModel):
    status: TaskStatus | None = None
    assigned_to: uuid.UUID | None = None
    due_date: date | None = None


class BulkTaskUpdate(BaseModel):
    ids: list[uuid.UUID]
    update: BulkTaskFieldUpdate