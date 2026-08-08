# app/schemas/irs_authorization.py

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


VALID_FORM_TYPES = {"8821", "2848"}

# The status vocabulary, kept here as the written record of it. No schema
# validates against it any more, because no schema accepts status any more:
# see IrsAuthorizationUpdate below. The three code paths that write status
# each write one literal value.
VALID_STATUSES = {"pending_signature", "active", "expired", "revoked", "superseded"}


# Returned as the 422 body when a PATCH tries to write status.
#
# The wording deliberately does NOT say the field does not exist. It does
# exist, on the model and on IrsAuthorizationOut, and telling a caller
# otherwise sends them looking in the wrong place. What it says instead is
# that this endpoint is not where status moves.
#
# It names signature activation and the nightly expiry sweep, and those two
# only. Revocation belongs on this list conceptually, but no code writes
# status = "revoked" today: PATCH was the only thing that ever could, and it
# no longer can. Naming a path that does not exist would send a reader
# hunting for an endpoint that is not there, which is the same failure as
# saying the field does not exist. Add revocation here when it is built, not
# before.
STATUS_NOT_PATCHABLE_MESSAGE = (
    "status cannot be changed through this endpoint. It moves only through "
    "signature activation or the nightly expiry sweep."
)


class IrsAuthorizationBase(BaseModel):
    form_type: str
    tax_years: List[int] = []
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

    @field_validator("form_type")
    @classmethod
    def validate_form_type(cls, v):
        if v not in VALID_FORM_TYPES:
            raise ValueError(f"form_type must be '8821' or '2848', got '{v}'")
        return v

    @field_validator("tax_years")
    @classmethod
    def validate_tax_years(cls, v):
        current_year = date.today().year
        for year in v:
            if not isinstance(year, int):
                raise ValueError("Each tax year must be an integer")
            if year < 2000 or year > current_year + 1:
                raise ValueError(f"Tax year {year} is out of valid range (2000–{current_year + 1})")
        return sorted(set(v))


class IrsAuthorizationCreate(IrsAuthorizationBase):
    client_id: UUID


class IrsAuthorizationUpdate(BaseModel):
    """
    Everything about an authorization that a general update may touch.

    status is deliberately absent, and its absence is the point.

    Moving an authorization to active has to retire whatever it replaces.
    That work lives in _supersede_prior_active_authorizations, which runs
    inside activate_authorization_for_envelope in a single transaction. A
    PATCH that could write status walked straight past it, which is how two
    active rows for the same client and form type could coexist. Removing the
    field means there is nowhere else to write status from, so a future path
    cannot skip supersession by accident.

    The paths that may write it are signature activation and the nightly
    expiry sweep. Revocation would be a third, but nothing writes
    status = "revoked" yet. Repairing a wrongly stated row is a direct
    database write, done deliberately. Do not add a bypass or an override
    flag here.
    """
    tax_years: Optional[List[int]] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    signature_envelope_id: Optional[UUID] = None
    signed_document_id: Optional[UUID] = None

    @model_validator(mode="before")
    @classmethod
    def reject_status(cls, data):
        """
        422 rather than a silent drop.

        Pydantic ignores unknown keys by default, so without this a caller
        who sent status would get a 200 and a response body showing the old
        status, with no indication that anything was refused. Quietly
        discarding a field somebody deliberately sent is the kind of failure
        that costs an afternoon to find.
        """
        if isinstance(data, dict) and "status" in data:
            raise ValueError(STATUS_NOT_PATCHABLE_MESSAGE)
        return data


class IrsAuthorizationOut(IrsAuthorizationBase):
    id: UUID
    firm_id: UUID
    client_id: UUID
    status: str
    signature_envelope_id: Optional[UUID] = None
    signed_document_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IrsAuthorizationSendRequest(BaseModel):
    """Request body for POST /irs-authorizations/send."""
    client_id: UUID
    form_type: str
    tax_years: List[int] = []
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

    @field_validator("form_type")
    @classmethod
    def validate_form_type(cls, v):
        if v not in VALID_FORM_TYPES:
            raise ValueError(f"form_type must be '8821' or '2848', got '{v}'")
        return v

    @field_validator("tax_years")
    @classmethod
    def validate_tax_years(cls, v):
        current_year = date.today().year
        for year in v:
            if not isinstance(year, int):
                raise ValueError("Each tax year must be an integer")
            if year < 2000 or year > current_year + 1:
                raise ValueError(f"Tax year {year} is out of valid range")
        return sorted(set(v))
