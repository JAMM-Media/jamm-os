# app/schemas/enrollment.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import EnrollmentStatus


class EnrollmentOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    lead_id: uuid.UUID
    sequence_id: uuid.UUID
    sequence_version_id: uuid.UUID
    current_step_id: Optional[uuid.UUID] = None
    next_action_time: Optional[datetime] = None
    status: EnrollmentStatus
    loop_counts: dict
    enrolled_at: datetime
    stopped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
