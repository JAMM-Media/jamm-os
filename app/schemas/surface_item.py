# app/schemas/surface_item.py

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import DismissalReason, SurfaceKind


class SurfaceItemBase(BaseModel):
    """
    The presentation facts of a surface row.

    Copy vocabulary is the frontend's business. The backend serves kind and
    item_type; it never serves the words "item" or "material signal", and it
    never serves the Done or Addressed button labels.
    """

    kind: SurfaceKind
    item_type: str
    dedup_key: str
    headline: str
    payload: dict = {}


class SurfaceItemCreate(SurfaceItemBase):
    """
    Written by the generators and the promotion path only.

    There is no public create endpoint for surface items, and there is not
    meant to be one: a row exists because a condition in the operational
    tables put it there. This schema exists to satisfy the four-schema rule
    and to give the service layer one typed shape to construct rows from.

    firm_id is intentionally absent, as on every Create schema in this
    codebase. It comes from the tenant context or from the generating job,
    never from a request body.

    finding_id is absent for the same reason in reverse: only the promotion
    path sets it, and that path builds rows in the service layer rather than
    from anything a caller supplied.
    """

    rank: int = 0


class SurfaceItemUpdate(BaseModel):
    """
    Every field optional, and deliberately narrow.

    The owner-facing actions (dismiss, mark implemented, promote next) are
    their own endpoints with their own bodies, because each one writes a
    specific set of columns in a specific order and fires a specific event.
    They do not route through a generic patch, so the lifecycle columns
    (dismissed_at, implemented_at, resolved_at, suppressed_until,
    value_at_action, flagged_for_review) are absent here on purpose. Nothing
    outside the service layer may set them.
    """

    headline: Optional[str] = None
    payload: Optional[dict] = None
    rank: Optional[int] = None


class SurfaceItemOut(SurfaceItemBase):
    id: UUID
    firm_id: UUID
    finding_id: Optional[UUID] = None

    rank: int
    slotted_at: Optional[datetime] = None

    appearance_count: int
    last_served_on: Optional[date] = None

    dismissed_at: Optional[datetime] = None
    dismissal_reason: Optional[DismissalReason] = None
    implemented_at: Optional[datetime] = None
    suppressed_until: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    value_at_action: Optional[dict] = None
    flagged_for_review: bool

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
