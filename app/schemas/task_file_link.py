# app/schemas/task_file_link.py

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.document import DocumentOut


class TaskFileLinkCreate(BaseModel):
    document_id: uuid.UUID


class TaskFileLinkOut(DocumentOut):
    """DocumentOut fields plus the link row's own id and timestamp."""
    link_id: uuid.UUID
    link_created_at: datetime
