# app/services/intake_token_service.py

"""
Lead intake token service.

Follows the unsubscribe-token and magic-link patterns with one deliberate
difference: this token is NOT single-use. It survives multiple requests across
one visit and clears on expiry, not on use.

The request body must never contain lead_id or firm_id. Both are resolved from
the token row alone, preventing cross-tenant token reuse.

Invalid and expired tokens return a neutral dict with status='invalid' rather
than raising HTTP exceptions. The router layer converts this to a 200 response
-- never a 401, since the frontend proxy treats 401 as a staff-token refresh
signal and would misroute a lead-facing response.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.lead_intake_token import LeadIntakeToken

logger = logging.getLogger(__name__)
settings = get_settings()


def mint_intake_token(
    db: Session,
    *,
    firm_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> str:
    """
    Mint a new intake token for a lead.

    Generates a secrets.token_hex(32) raw token, stores only the SHA-256 hash,
    and returns the raw token so the caller can embed it in a link.

    Expiry is INTAKE_TOKEN_EXPIRE_DAYS from now (default 30 days). Multiple
    tokens may exist for the same lead -- old tokens are not explicitly cleared
    here since the lead may have multiple open links (e.g. email resent). They
    expire naturally. The caller may clean them up if desired.
    """
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.INTAKE_TOKEN_EXPIRE_DAYS
    )

    row = LeadIntakeToken(
        firm_id=firm_id,
        lead_id=lead_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    logger.info(
        "intake_token: minted token for lead=%s firm=%s expires=%s",
        lead_id, firm_id, expires_at.isoformat(),
    )
    return raw_token


def validate_intake_token(
    db: Session,
    *,
    raw_token: str,
) -> dict:
    """
    Validate a raw intake token.

    Hashes the incoming token and queries for a matching, non-expired row.
    Derives lead_id and firm_id from the row -- never from the request.

    NOT single-use: a valid token remains valid across multiple requests until
    it expires. Only the expiry check governs token lifecycle.

    Returns a dict with:
      status: 'valid' | 'invalid'
      lead_id: str | None (only when status='valid')
      firm_id: str | None (only when status='valid')

    Callers should surface a neutral 'link expired or invalid' state on
    status='invalid', not raise HTTP errors.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    row: Optional[LeadIntakeToken] = (
        db.query(LeadIntakeToken)
        .filter(
            LeadIntakeToken.token_hash == token_hash,
            LeadIntakeToken.expires_at > now,
        )
        .first()
    )

    if row is None:
        logger.info("intake_token: token not found or expired (hash prefix: %s)", token_hash[:8])
        return {"status": "invalid", "lead_id": None, "firm_id": None}

    logger.info(
        "intake_token: validated token for lead=%s firm=%s", row.lead_id, row.firm_id
    )
    return {
        "status": "valid",
        "lead_id": str(row.lead_id),
        "firm_id": str(row.firm_id),
    }


def expire_intake_tokens_for_lead(
    db: Session,
    *,
    firm_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> int:
    """
    Immediately expire all active intake tokens for a lead.

    Used when the lead converts or when a firm revokes access. Returns the
    count of rows expired.
    """
    now = datetime.now(timezone.utc)
    rows = (
        db.query(LeadIntakeToken)
        .filter(
            LeadIntakeToken.firm_id == firm_id,
            LeadIntakeToken.lead_id == lead_id,
            LeadIntakeToken.expires_at > now,
        )
        .all()
    )
    for row in rows:
        row.expires_at = now
    db.commit()
    return len(rows)
