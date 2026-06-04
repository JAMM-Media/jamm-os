# app/schemas/audit_log.py

import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_type: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    extra_metadata: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
