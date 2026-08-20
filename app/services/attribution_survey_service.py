# app/services/attribution_survey_service.py
"""
Attribution survey for existing clients whose referral_source is blank.

Per Contract section 4.1: a one-question survey delivered as a special
pinned portal notification. Options are the full ReferralSource enum
with human-readable labels, "Do not remember" appended last. Submitting
an answer writes to Client.referral_source with client_reported provenance
(fills blank only, never overwrites a value already set).
"""

from sqlalchemy.orm import Session

from app.core.enums import ReferralSource
from app.crud import portal_notification as crud_notification
from app.models.client import Client
from app.schemas.portal_notification import PortalNotificationCreate

ATTRIBUTION_SURVEY_TYPE = "attribution_survey"

# Human-readable labels for each ReferralSource value, in survey display order.
# "do_not_remember" is a pseudo-value that maps to ReferralSource.unknown on
# submit; it is appended last so clients scan real options first, per section 4.1.
SURVEY_OPTIONS: list[dict] = [
    {"value": ReferralSource.client_referral.value,         "label": "Referred by a current client"},
    {"value": ReferralSource.professional_referral.value,   "label": "Referred by a professional (attorney, advisor, etc.)"},
    {"value": ReferralSource.returning_client.value,        "label": "I am a returning client"},
    {"value": ReferralSource.google_search.value,           "label": "Google search"},
    {"value": ReferralSource.search_ads.value,              "label": "Online ad (Google, Bing)"},
    {"value": ReferralSource.social_ads.value,              "label": "Social media ad"},
    {"value": ReferralSource.social_media.value,            "label": "Social media (organic)"},
    {"value": ReferralSource.website.value,                 "label": "Found the website"},
    {"value": ReferralSource.association_or_community.value,"label": "Association or community group"},
    {"value": ReferralSource.walk_in.value,                 "label": "Walked in / local discovery"},
    {"value": ReferralSource.cold_outreach.value,           "label": "Outreach from the firm"},
    {"value": ReferralSource.purchased_book.value,          "label": "Acquired with an existing practice"},
    {"value": ReferralSource.other.value,                   "label": "Other"},
    {"value": "do_not_remember",                            "label": "Do not remember"},
]

# The set of valid submission values (real enum members + do_not_remember sentinel).
_VALID_ANSWERS = {opt["value"] for opt in SURVEY_OPTIONS}


def get_survey_options() -> list[dict]:
    """Return the ordered survey option list. "Do not remember" is always last."""
    return SURVEY_OPTIONS


def ensure_attribution_survey_notification(db: Session, client: Client) -> None:
    """Create the pinned attribution survey notification if this client needs one.

    Idempotent: does nothing if attribution is already set, or if the
    notification already exists. Called on every portal dashboard visit.
    """
    if client.referral_source is not None:
        return
    existing = crud_notification.get_pending_by_type(
        db,
        client_id=client.id,
        firm_id=client.firm_id,
        notification_type=ATTRIBUTION_SURVEY_TYPE,
    )
    if existing is not None:
        return
    data = PortalNotificationCreate(
        firm_id=client.firm_id,
        client_id=client.id,
        title="Quick question: how did you hear about us?",
        body=(
            "We would love to know how you found us. Your answer helps us"
            " understand how clients like you discover our firm."
        ),
        notification_type=ATTRIBUTION_SURVEY_TYPE,
        is_pinned=True,
    )
    crud_notification.create_notification(db, data)


def submit_attribution_answer(
    db: Session,
    client: Client,
    answer: str,
) -> dict:
    """Record the client's survey answer and clear the pinned notification.

    answer must be one of the values in SURVEY_OPTIONS (including "do_not_remember").

    Returns a dict with the outcome:
      - "written": True if the field was updated, False if it was already set
        (race condition: another path wrote it between survey display and submit).

    "do_not_remember" maps to ReferralSource.unknown.
    """
    if answer not in _VALID_ANSWERS:
        raise ValueError(
            f"Invalid attribution answer {answer!r}. "
            f"Valid values: {sorted(_VALID_ANSWERS)}"
        )

    written = False
    if client.referral_source is None:
        # Fills blank only. Never overwrites a value that arrived concurrently.
        resolved = ReferralSource.unknown if answer == "do_not_remember" else ReferralSource(answer)
        client.referral_source = resolved
        db.add(client)
        db.flush()
        written = True

    # Always clear the pinned notification on submission regardless of whether
    # the write happened, so the survey does not re-appear on next visit.
    existing = crud_notification.get_pending_by_type(
        db,
        client_id=client.id,
        firm_id=client.firm_id,
        notification_type=ATTRIBUTION_SURVEY_TYPE,
    )
    if existing is not None:
        db.delete(existing)

    db.commit()
    return {"written": written}
