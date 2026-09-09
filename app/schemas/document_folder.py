# app/schemas/document_folder.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentFolderCreate(BaseModel):
    name: str
    scope: str
    client_id: Optional[uuid.UUID] = None
    engagement_id: Optional[uuid.UUID] = None
    parent_folder_id: Optional[uuid.UUID] = None


class DocumentFolderUpdate(BaseModel):
    name: str


class DocumentFolderOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    scope: str
    name: str
    client_id: Optional[uuid.UUID] = None
    engagement_id: Optional[uuid.UUID] = None
    parent_folder_id: Optional[uuid.UUID] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
