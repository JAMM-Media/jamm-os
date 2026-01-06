# app/schemas/task.py

import uuid
from datetime import date, datetime
from pydantic import BaseModel, Field

# ----------------------
# Shared fields
# ----------------------

class TaskBase(BaseModel):
    title: str
    status: str = "todo"
    due_date: date | None = None
    assigned_to: str | None = None
    notes: str | None = None
    is_completed: bool = False


# ----------------------
# On create
# ----------------------

class TaskCreate(TaskBase):
    client_id: uuid.UUID
    project_id: uuid.UUID


# ----------------------
# On update (PATCH)
# ----------------------

class TaskUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    due_date: date | None = None
    assigned_to: str | None = None
    notes: str | None = None
    is_completed: bool | None = None
    client_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


# ----------------------
# Outbound response
# ----------------------

class TaskOut(TaskBase):
    id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # required to serialize SQLAlchemy 2.0 models
# app/schemas/task.py (at the bottom)

from pydantic import BaseModel
from datetime import date
import uuid

class TaskSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    due_date: date | None = None

    class Config:
        from_attributes = True

class TaskSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    due_date: date | None = None

    class Config:
        from_attributes = True
