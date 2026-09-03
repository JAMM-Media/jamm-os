# app/api/intake_token.py

"""
Lead intake token router.

Three sets of endpoints:

1. Staff-authenticated: mint a token for an existing lead.
   POST /intake-token/mint

2. Public, token-validated: validate a token and submit intake answers.
   GET  /intake-token/validate/{token}
   POST /intake-token/answers/{token}

3. Public, qualification answer click (from E2 email button):
   GET  /intake-token/qualify/{token}?field=entity_type&value=individual

All public endpoints are rate-limited using the same limiter as intake_submit.
Responses on invalid/expired tokens are neutral 200s (or redirects) with
status='invalid' -- never 401, which the frontend proxy would misinterpret as
a staff-token signal.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.crud import intake_answer as crud_intake_answer
from app.crud.lead import get_lead_for_firm
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.intake_answer import IntakeAnswer
from app.models.lead import Lead
from app.models.user import User
from app.services.behavioral_log import log_event
from app.services.intake_token_service import mint_intake_token, validate_intake_token

router = APIRouter(prefix="/intake-token", tags=["Intake Token"])


# ---------------------------------------------------------------------------
# Staff-authenticated: mint a token for an existing lead
# ---------------------------------------------------------------------------

class MintIntakeTokenBody(BaseModel):
    lead_id: uuid.UUID


class MintIntakeTokenResponse(BaseModel):
    raw_token: str
    lead_id: str
    expires_in_days: int


@router.post("/mint", response_model=MintIntakeTokenResponse)
def mint_token_for_lead(
    body: MintIntakeTokenBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """
    Mint a new intake token for a lead.

    Staff must belong to the same firm as the lead -- firm_id is taken from
    the authenticated staff context, never from the request body.
    """
    from app.core.config import get_settings
    settings = get_settings()

    lead = get_lead_for_firm(db, lead_id=body.lead_id, firm_id=current_firm.id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    raw_token = mint_intake_token(
        db=db,
        firm_id=current_firm.id,
        lead_id=lead.id,
    )

    return MintIntakeTokenResponse(
        raw_token=raw_token,
        lead_id=str(lead.id),
        expires_in_days=settings.INTAKE_TOKEN_EXPIRE_DAYS,
    )


# ---------------------------------------------------------------------------
# Public, token-validated endpoints
# ---------------------------------------------------------------------------

class ValidateTokenResponse(BaseModel):
    status: str        # 'valid' | 'invalid'
    lead_id: Optional[str] = None
    firm_id: Optional[str] = None


@router.get("/validate/{token}", response_model=ValidateTokenResponse, status_code=200)
@limiter.limit("5/minute")
def validate_token(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Validate an intake token.

    Returns status='valid' with lead_id and firm_id if the token is valid and
    not expired. Returns status='invalid' with null IDs otherwise.

    Always 200 -- never 401 (which the frontend proxy would misinterpret as a
    staff-token refresh signal).
    """
    result = validate_intake_token(db=db, raw_token=token)
    return ValidateTokenResponse(**result)


# ---------------------------------------------------------------------------
# Answer submission schemas
# ---------------------------------------------------------------------------

class IntakeAnswerPayload(BaseModel):
    kind: str                              # flag | dimension_numeric | dimension_categorical | dimension_boolean
    dimension_key: Optional[str] = None
    value_option_id: Optional[uuid.UUID] = None
    value_numeric: Optional[float] = None
    value_boolean: Optional[bool] = None
    value_text: Optional[str] = None


class SubmitAnswersBody(BaseModel):
    answers: list[IntakeAnswerPayload]


class SubmitAnswersResponse(BaseModel):
    status: str           # 'ok' | 'invalid_token'
    written: int          # number of rows written (0 on invalid token)


VALID_KINDS = {"flag", "dimension_numeric", "dimension_categorical", "dimension_boolean"}


@router.post("/answers/{token}", response_model=SubmitAnswersResponse, status_code=200)
@limiter.limit("5/minute")
def submit_answers(
    token: str,
    body: SubmitAnswersBody,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Submit intake answers tied to a token-resolved lead.

    firm_id and lead_id are resolved from the token row only -- the request
    body must not contain either. Returns status='invalid_token' (200) if the
    token is missing or expired; never raises 401.

    Each answer is validated for kind-field consistency before any row is
    written. The write is bulk-committed in a single transaction.
    """
    result = validate_intake_token(db=db, raw_token=token)
    if result["status"] != "valid":
        return SubmitAnswersResponse(status="invalid_token", written=0)

    firm_id = uuid.UUID(result["firm_id"])
    lead_id = uuid.UUID(result["lead_id"])

    rows: list[IntakeAnswer] = []
    for payload in body.answers:
        if payload.kind not in VALID_KINDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid kind: {payload.kind!r}. Must be one of: {sorted(VALID_KINDS)}",
            )
        if payload.kind == "dimension_categorical":
            if not payload.dimension_key or not payload.value_option_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="dimension_categorical answers require both dimension_key and value_option_id",
                )
        elif payload.kind in {"dimension_numeric", "dimension_boolean"}:
            if not payload.dimension_key:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{payload.kind} answers require dimension_key",
                )

        rows.append(
            IntakeAnswer(
                firm_id=firm_id,
                lead_id=lead_id,
                kind=payload.kind,
                dimension_key=payload.dimension_key,
                value_option_id=payload.value_option_id,
                value_numeric=payload.value_numeric,
                value_boolean=payload.value_boolean,
                value_text=payload.value_text,
            )
        )

    if rows:
        crud_intake_answer.bulk_create_intake_answers(db=db, answers=rows)

    return SubmitAnswersResponse(status="ok", written=len(rows))


# ---------------------------------------------------------------------------
# Public: qualification answer click from E2 email button
# ---------------------------------------------------------------------------

# Five real entity_type values, from Lead.entity_type's column comment.
ENTITY_TYPE_VALUES: frozenset[str] = frozenset(
    {"individual", "business", "trust", "estate", "non_profit"}
)

# Whitelist of Lead fields settable via the qualify endpoint today.
# Extend both sets when a new qualification field is added; the endpoint
# rejects any field name not in this set.
QUALIFY_FIELD_WHITELIST: frozenset[str] = frozenset({"entity_type"})

QUALIFY_VALUE_WHITELIST: dict[str, frozenset[str]] = {
    "entity_type": ENTITY_TYPE_VALUES,
}


@router.get("/qualify/{token}", status_code=302)
@limiter.limit("5/minute")
def qualify_answer(
    token: str,
    field: str,
    value: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Process a lead's qualification answer click from an E2 email button.

    Whitelist: today only field='entity_type' with one of its five real values
    is accepted. Any other field name or value returns 422.

    On a valid token + valid field/value pair:
      - Writes the field directly onto the Lead row (scoped to firm_id from token).
      - Fires lead.answer_button_clicked via log_event.
      - Redirects to {FRONTEND_URL}/intake-resume/{token}.

    On an invalid or expired token:
      - Redirects to the same intake-resume URL. The page already validates
        the token itself on load and renders the expired state -- no duplication
        needed here.

    Always a redirect -- never JSON -- since this endpoint is the target of a
    clickable link in an email.
    """
    from app.core.config import get_settings
    settings = get_settings()
    resume_url = f"{settings.FRONTEND_URL}/intake-resume/{token}"

    # Whitelist: field name
    if field not in QUALIFY_FIELD_WHITELIST:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Field {field!r} is not accepted by this endpoint. "
                f"Accepted fields: {sorted(QUALIFY_FIELD_WHITELIST)}"
            ),
        )

    # Whitelist: value for the given field
    allowed = QUALIFY_VALUE_WHITELIST.get(field, frozenset())
    if value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Value {value!r} is not valid for field {field!r}. "
                f"Accepted: {sorted(allowed)}"
            ),
        )

    # Validate token; invalid/expired tokens redirect to the resume page so
    # the page's own state machine renders the correct expired UI.
    result = validate_intake_token(db=db, raw_token=token)
    if result["status"] != "valid":
        return RedirectResponse(url=resume_url, status_code=302)

    firm_id = uuid.UUID(result["firm_id"])
    lead_id = uuid.UUID(result["lead_id"])

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.firm_id == firm_id)
        .first()
    )
    if lead is None:
        return RedirectResponse(url=resume_url, status_code=302)

    setattr(lead, field, value)
    db.commit()

    # PROPOSED NAME -- pending Andrew's sign-off (Contract section 9.1).
    # Fires when a lead clicks an entity_type answer button in an E2 nurture email.
    log_event(
        event_type="lead.answer_button_clicked",
        firm_id=firm_id,
        entity_type="lead",
        entity_id=lead_id,
        actor_type="lead",
        metadata={"field": field, "value": value},
    )

    return RedirectResponse(url=resume_url, status_code=302)
