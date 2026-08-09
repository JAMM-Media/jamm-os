# app/schemas/engagement_member.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EngagementMemberBase(BaseModel):
    is_administrator: bool = False


class EngagementMemberCreate(EngagementMemberBase):
    """engagement_id and firm_id are never accepted from the request body.
    engagement_id comes from the path, firm_id from the JWT."""

    user_id: uuid.UUID


class EngagementMemberUpdate(BaseModel):
    """Promotion and demotion. is_administrator is the only mutable field --
    moving a membership to a different user or a different engagement is a
    remove plus an add, not an edit."""

    is_administrator: bool | None = None


class EngagementMemberOut(EngagementMemberBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    engagement_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Filled in by the router so a member list is directly renderable, and so
    # the task-assignment dropdown does not need a second call per member.
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
