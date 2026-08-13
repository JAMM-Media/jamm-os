# app/schemas/lead_message.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LeadMessageOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    lead_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None
    sender_role: str
    body: str
    source: Optional[str] = None
    is_deleted: bool
    created_at: datetime
    # Populated by service layer, not stored in DB -- matching ClientMessageOut.
    sender_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
