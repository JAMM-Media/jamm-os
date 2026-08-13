# app/schemas/sequence.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import StepType


# ---------------------------------------------------------------------------
# Sequence (mutable -- has created_at and updated_at)
# ---------------------------------------------------------------------------

class SequenceBase(BaseModel):
    name: str
    is_active: bool = True


class SequenceCreate(SequenceBase):
    pass


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class SequenceOut(SequenceBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    current_version_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# SequenceVersion (immutable after creation -- no Create/Update schemas)
# ---------------------------------------------------------------------------

class SequenceVersionOut(BaseModel):
    id: uuid.UUID
    sequence_id: uuid.UUID
    version_number: int
    preset_lineage_key: Optional[str] = None
    created_by_user_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Step (immutable after creation -- read-only schema only)
# ---------------------------------------------------------------------------

class StepOut(BaseModel):
    id: uuid.UUID
    sequence_version_id: uuid.UUID
    step_key: str
    step_type: StepType
    channel: str
    phase: Optional[str] = None
    is_modified_from_preset: bool
    config: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# StepEdge (immutable -- read-only)
# ---------------------------------------------------------------------------

class StepEdgeOut(BaseModel):
    id: uuid.UUID
    from_step_id: uuid.UUID
    to_step_id: uuid.UUID
    condition_label: Optional[str] = None
    loop_cap: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# SequenceGoal (immutable -- read-only)
# ---------------------------------------------------------------------------

class SequenceGoalOut(BaseModel):
    id: uuid.UUID
    sequence_version_id: uuid.UUID
    goal_event: str
    target_step_id: uuid.UUID
    applies_to_phase: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
