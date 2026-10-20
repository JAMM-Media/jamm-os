# app/schemas/irs_authorization_warning.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IrsAuthorizationWarningBase(BaseModel):
    # Days before valid_until that this tier represents. 0 is the expiry date.
    threshold_days: int
    sent_at: datetime


class IrsAuthorizationWarningCreate(IrsAuthorizationWarningBase):
    # firm_id is injected server-side from the JWT and is never accepted here.
    authorization_id: UUID
    # Required, not optional. Every write from Sep 24, 2026 knows who it
    # reached, because the row is only written after that recipient's in-app
    # notification landed. Nulls in this column are history, not new data.
    recipient_user_id: UUID


class IrsAuthorizationWarningUpdate(BaseModel):
    threshold_days: Optional[int] = None
    sent_at: Optional[datetime] = None


class IrsAuthorizationWarningOut(IrsAuthorizationWarningBase):
    id: UUID
    firm_id: UUID
    authorization_id: UUID
    # Optional on the way out: rows written before Sep 24, 2026 have no
    # recipient recorded, and a deleted user nulls it on rows that did.
    recipient_user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IrsAuthorizationWarningLadderItem(BaseModel):
    """
    One rung of the ladder as GET /{auth_id}/warnings reports it.

    Which tier fired, when, and who it reached. Deliberately narrower than
    IrsAuthorizationWarningOut, which carries firm_id, authorization_id and
    the row's own timestamps: the caller already knows the firm from its JWT
    and the authorization from the URL, and created_at is an artifact of when
    the row was written rather than a fact about the warning.

    RECIPIENTS ARE RECORDED from Sep 24, 2026. The table now holds one row per
    recipient per tier, so a rung is a grouping of those rows: sent_at is the
    earliest send in the tier and recipient_user_ids lists every recipient
    recorded for it. Rungs from before that date, and rungs whose recipients
    have since been deleted, return an empty list, which means "not recorded"
    and never "sent to nobody". The list is never synthesised by re-running
    get_firm_owners_and_managers at read time: firm membership changes, so that
    would answer "who would be warned today" while appearing to answer "who was
    warned then", and a compliance record that quietly rewrites its own history
    is worse than one that admits a gap.
    """
    threshold_days: int
    sent_at: datetime
    recipient_user_ids: list[UUID]

    model_config = ConfigDict(from_attributes=True)
