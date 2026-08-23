# app/schemas/folder.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FolderBase(BaseModel):
    name: str
    parent_folder_id: Optional[uuid.UUID] = None


class FolderCreate(FolderBase):
    client_id: uuid.UUID


class FolderUpdate(BaseModel):
    name: str


class FolderOut(FolderBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    client_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
