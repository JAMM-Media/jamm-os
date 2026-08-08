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


class IrsAuthorizationWarningUpdate(BaseModel):
    threshold_days: Optional[int] = None
    sent_at: Optional[datetime] = None


class IrsAuthorizationWarningOut(IrsAuthorizationWarningBase):
    id: UUID
    firm_id: UUID
    authorization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IrsAuthorizationWarningLadderItem(BaseModel):
    """
    One rung of the ladder as GET /{auth_id}/warnings reports it.

    Which tier fired and when, and nothing else. Deliberately narrower than
    IrsAuthorizationWarningOut, which carries firm_id, authorization_id and
    the row's own timestamps: the caller already knows the firm from its JWT
    and the authorization from the URL, and created_at is an artifact of when
    the row was written rather than a fact about the warning.

    RECIPIENTS ARE NOT HERE, and their absence is a real gap rather than an
    editorial choice. irs_authorization_warnings has no recipient column.
    The sweep resolves recipients at send time through
    crud_user.get_firm_owners_and_managers and keeps no record of who it
    reached, so who a warning went to is not recoverable from this table.
    Reporting it needs a schema change, which Phase F2 did not have. Do not
    synthesise the list by re-running get_firm_owners_and_managers at read
    time: firm membership changes, so that would answer "who would be warned
    today" while appearing to answer "who was warned then", and a compliance
    record that quietly rewrites its own history is worse than one that
    admits a gap.
    """
    threshold_days: int
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)
