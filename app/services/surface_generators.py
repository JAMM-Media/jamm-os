# app/services/surface_generators.py

"""
The day-one rule-based generators for surface_items.

Every generator reads OPERATIONAL tables only: invoices, irs_authorizations,
signature_envelopes, engagements, tasks, document_requests, extensions. None of
them reads behavioral_events, and none of them ever may. The behavioral log is
a recorder, never a gatekeeper, so an item clears because the invoice table says
the balance is zero, never because an invoice.paid event was found. A guard test
scans this module for exactly that.

Each generator answers one question ("what conditions are true right now") and
returns Candidates. Each item type also owns a clear condition, which answers
the opposite question about an existing row, and a delta basis, which says how
to describe the change when a suppression window expires.

Nothing here writes to the database and nothing here touches a Finding.
"""

from dataclasses import dataclass, field
from functools import cmp_to_key
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import InvoiceStatus, SurfaceKind
from app.core.surface_constants import (
    DEADLINE_WINDOW_DAYS,
    IRS_AUTH_WINDOW_DAYS,
    SIGNATURE_STALLED_DAYS,
    UNBILLED_DAYS,
)
from app.models.document_request import DocumentRequest
from app.models.engagement import Engagement
from app.models.extension import Extension
from app.models.invoice import Invoice
from app.models.irs_authorization import IrsAuthorization
from app.models.signature_envelope import SignatureEnvelope
from app.models.task import Task

# ---------------------------------------------------------------------------
# Item types and tiers
# ---------------------------------------------------------------------------

ITEM_INVOICE_OVERDUE = "invoice_overdue"
ITEM_IRS_AUTH_EXPIRING = "irs_auth_expiring"
ITEM_SIGNATURE_STALLED = "signature_stalled"
ITEM_SIGNATURE_DECLINED = "signature_declined"
ITEM_SIGNATURE_EXPIRED = "signature_expired"
ITEM_DEADLINE_WITH_BLOCKERS = "deadline_with_blockers"
ITEM_WORK_UNBILLED = "work_unbilled"

# Two urgency tiers, deliberately blunt. Tier 1 outranks tier 2 outright;
# ranking inside a tier is time first, then magnitude as a boost.
TIER_1 = 1
TIER_2 = 2

TIERS: dict[str, int] = {
    ITEM_DEADLINE_WITH_BLOCKERS: TIER_1,
    ITEM_IRS_AUTH_EXPIRING: TIER_1,
    ITEM_SIGNATURE_DECLINED: TIER_1,
    ITEM_INVOICE_OVERDUE: TIER_2,
    ITEM_SIGNATURE_STALLED: TIER_2,
    ITEM_SIGNATURE_EXPIRED: TIER_2,
    ITEM_WORK_UNBILLED: TIER_2,
}

# ---------------------------------------------------------------------------
# Envelope status vocabulary, as the CODE actually writes it
# ---------------------------------------------------------------------------
#
# Read this before changing anything here. The model comment on
# SignatureEnvelope documents the vocabulary as
# draft | sent | completed | declined | expired | cancelled. The code does not
# write that vocabulary. Verified across the whole application on Sep 1, 2026:
#
#   "draft"   written at creation
#   "sent"    written by the send path
#   "signed"  written by process_webhook_signed
#
# and nothing else. No code path anywhere writes "completed", "declined",
# "expired", "cancelled" or "voided". EVENT_STATUS_MAP in app/api/esign.py maps
# webhook events onto those names but is never referenced by anything: it is
# dead code. The only way one of those statuses can appear today is a manual
# staff PATCH, because SignatureEnvelopeUpdate.status is a free-form str.
#
# Consequences, reported rather than absorbed:
#   - signature_declined and signature_expired cannot fire today. They are
#     inert in the same deliberate way the promotion stub is inert, and they
#     start working the day the status writes land. No row, no harm.
#   - ENVELOPE_WAITING_ENDED includes "signed". The ruling listed completed,
#     declined, cancelled and expired. "signed" is the status this codebase
#     actually writes when a signature arrives, and leaving it out would mean a
#     signed envelope never clears its stalled item and sits on the briefing
#     forever. That is the one place the ruled list would have shipped a live
#     defect, so "signed" is included here and flagged for ratification.
ENVELOPE_STATUS_SENT = "sent"
ENVELOPE_STATUS_DECLINED = "declined"
ENVELOPE_STATUS_EXPIRED = "expired"

ENVELOPE_WAITING_ENDED = frozenset(
    {"signed", "completed", "declined", "cancelled", "voided", "expired"}
)


@dataclass(frozen=True)
class Candidate:
    """
    One condition that is true right now, ready to become or refresh a row.

    time_urgency is normalised so that HIGHER always means more urgent,
    whichever direction the underlying clock runs. Days overdue counts up;
    days until an expiry counts down, so it is subtracted from its window.

    magnitude is the boost, and None means there is nothing to boost with.
    None is never coerced to zero: an unpriced engagement gets no boost and no
    penalty. See the NULL-fee law in rank_candidates.
    """

    item_type: str
    dedup_key: str
    headline: str
    payload: dict
    time_urgency: int
    magnitude: Optional[Decimal] = None
    measured: dict = field(default_factory=dict)
    kind: SurfaceKind = SurfaceKind.briefing

    @property
    def tier(self) -> int:
        return TIERS[self.item_type]


@dataclass(frozen=True)
class ClearResult:
    """Whether an open row's condition has gone away, and what to say if so."""

    cleared: bool
    outcome: Optional[str] = None


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _days_since(moment: datetime | None) -> int:
    """Whole days between an aware timestamp and now. Never negative."""
    if moment is None:
        return 0
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - moment).days)


def _invoice_balance(invoice: Invoice) -> Decimal:
    total = Decimal(str(invoice.total_amount or 0))
    paid = Decimal(str(invoice.amount_paid or 0))
    return total - paid


def _plural(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


# ---------------------------------------------------------------------------
# 1. invoice_overdue
# ---------------------------------------------------------------------------

def generate_invoice_overdue(db: Session, firm_id: UUID) -> list[Candidate]:
    """
    An invoice past its due date with a balance outstanding.

    Past-due is computed from due_date and the balance directly, never from
    status == overdue. The nightly overdue sweep flips that status at 7:45 and
    depending on it would make this generator's correctness depend on job
    ordering.

    No installment or payment-plan object exists anywhere in the codebase
    (checked Sep 1, 2026: every "installment" in the repo is IRS
    installment-agreement catalog vocabulary), so the ruled nuance about a plan
    on schedule not being overdue has nothing to read and is a ledger item.
    """
    today = _today()
    rows = db.execute(
        select(Invoice).where(
            Invoice.firm_id == firm_id,
            Invoice.is_deleted.is_(False),
            Invoice.due_date.isnot(None),
            Invoice.due_date < today,
            Invoice.status != InvoiceStatus.void,
        )
    ).scalars().all()

    candidates: list[Candidate] = []
    for invoice in rows:
        balance = _invoice_balance(invoice)
        if balance <= 0:
            continue

        days_overdue = (today - invoice.due_date).days
        measured = {"balance": float(balance), "days_overdue": days_overdue}
        candidates.append(
            Candidate(
                item_type=ITEM_INVOICE_OVERDUE,
                dedup_key=str(invoice.id),
                headline=(
                    f"Invoice {invoice.invoice_number} is {days_overdue} "
                    f"{_plural(days_overdue, 'day', 'days')} overdue"
                ),
                payload={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "client_id": str(invoice.client_id),
                    "balance": float(balance),
                    "days_overdue": days_overdue,
                },
                time_urgency=days_overdue,
                magnitude=balance,
                measured=measured,
            )
        )
    return candidates


def clear_invoice_overdue(db: Session, firm_id: UUID, dedup_key: str) -> ClearResult:
    """Clears when the balance reaches zero, the invoice is voided, or it is deleted."""
    invoice = db.execute(
        select(Invoice).where(Invoice.id == UUID(dedup_key), Invoice.firm_id == firm_id)
    ).scalars().first()

    if invoice is None or invoice.is_deleted:
        return ClearResult(True, "No longer outstanding")
    if invoice.status == InvoiceStatus.void:
        return ClearResult(True, "Voided")
    if _invoice_balance(invoice) <= 0:
        return ClearResult(True, "Paid")
    return ClearResult(False)


# ---------------------------------------------------------------------------
# 2. irs_auth_expiring
# ---------------------------------------------------------------------------

def generate_irs_auth_expiring(db: Session, firm_id: UUID) -> list[Candidate]:
    """An active 8821 or 2848 inside the expiry window."""
    today = _today()
    cutoff = today + timedelta(days=IRS_AUTH_WINDOW_DAYS)
    rows = db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.firm_id == firm_id,
            IrsAuthorization.status == "active",
            IrsAuthorization.valid_until.isnot(None),
            IrsAuthorization.valid_until <= cutoff,
        )
    ).scalars().all()

    candidates: list[Candidate] = []
    for auth in rows:
        days_to_expiry = (auth.valid_until - today).days
        candidates.append(
            Candidate(
                item_type=ITEM_IRS_AUTH_EXPIRING,
                dedup_key=str(auth.id),
                headline=(
                    f"Form {auth.form_type} authorization expires in "
                    f"{days_to_expiry} {_plural(days_to_expiry, 'day', 'days')}"
                    if days_to_expiry >= 0
                    else f"Form {auth.form_type} authorization has lapsed"
                ),
                payload={
                    "authorization_id": str(auth.id),
                    "client_id": str(auth.client_id),
                    "form_type": auth.form_type,
                    "valid_until": auth.valid_until.isoformat(),
                    "days_to_expiry": days_to_expiry,
                },
                # Counts down, so invert it against the window to keep the
                # convention that higher time_urgency means more urgent.
                time_urgency=IRS_AUTH_WINDOW_DAYS - days_to_expiry,
                magnitude=None,
                measured={"days_to_expiry": days_to_expiry},
            )
        )
    return candidates


def clear_irs_auth_expiring(db: Session, firm_id: UUID, dedup_key: str) -> ClearResult:
    """
    Clears when a newer authorization for that client is on file.

    That is durable operational state rather than a derived comparison:
    _supersede_prior_active_authorizations writes status = "superseded" onto the
    old row when the replacement activates, so the row stops reading "active".
    """
    auth = db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.id == UUID(dedup_key),
            IrsAuthorization.firm_id == firm_id,
        )
    ).scalars().first()

    if auth is None:
        return ClearResult(True, "No longer on file")
    if auth.status == "superseded":
        return ClearResult(True, "Renewed")
    if auth.status != "active":
        return ClearResult(True, "No longer active")
    return ClearResult(False)


# ---------------------------------------------------------------------------
# 3, 4, 5. signature items
# ---------------------------------------------------------------------------

def _no_newer_envelope_sent(
    db: Session, firm_id: UUID, envelope: SignatureEnvelope
) -> bool:
    """
    True when nothing has been sent since this envelope to replace it.

    Scoped to the same engagement, or to the same client where the envelope
    carries no engagement, per the ruling.
    """
    stmt = select(func.count()).select_from(SignatureEnvelope).where(
        SignatureEnvelope.firm_id == firm_id,
        SignatureEnvelope.id != envelope.id,
        SignatureEnvelope.sent_at.isnot(None),
    )
    if envelope.engagement_id is not None:
        stmt = stmt.where(SignatureEnvelope.engagement_id == envelope.engagement_id)
    else:
        stmt = stmt.where(
            SignatureEnvelope.client_id == envelope.client_id,
            SignatureEnvelope.engagement_id.is_(None),
        )
    if envelope.sent_at is not None:
        stmt = stmt.where(SignatureEnvelope.sent_at > envelope.sent_at)

    return (db.execute(stmt).scalar() or 0) == 0


def generate_signature_stalled(db: Session, firm_id: UUID) -> list[Candidate]:
    """An envelope still out for signature past the stalled threshold."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SIGNATURE_STALLED_DAYS)
    rows = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.firm_id == firm_id,
            SignatureEnvelope.status == ENVELOPE_STATUS_SENT,
            SignatureEnvelope.sent_at.isnot(None),
            SignatureEnvelope.sent_at <= cutoff,
        )
    ).scalars().all()

    candidates: list[Candidate] = []
    for envelope in rows:
        days_waiting = _days_since(envelope.sent_at)
        candidates.append(
            Candidate(
                item_type=ITEM_SIGNATURE_STALLED,
                dedup_key=str(envelope.id),
                headline=(
                    f"Signature has been outstanding {days_waiting} "
                    f"{_plural(days_waiting, 'day', 'days')}"
                ),
                payload={
                    "envelope_id": str(envelope.id),
                    "client_id": str(envelope.client_id),
                    "engagement_id": (
                        str(envelope.engagement_id) if envelope.engagement_id else None
                    ),
                    "days_waiting": days_waiting,
                },
                time_urgency=days_waiting,
                # The magnitude boost would be the engagement fee. No fee column
                # exists on engagements, so there is nothing to boost with and
                # None stays None. It is never read as zero.
                magnitude=None,
                measured={"days_waiting": days_waiting},
            )
        )
    return candidates


def _clear_when_waiting_ended(
    db: Session, firm_id: UUID, dedup_key: str, outcome: str
) -> ClearResult:
    envelope = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.id == UUID(dedup_key),
            SignatureEnvelope.firm_id == firm_id,
        )
    ).scalars().first()

    if envelope is None:
        return ClearResult(True, "No longer on file")
    if envelope.status in ENVELOPE_WAITING_ENDED:
        return ClearResult(True, outcome)
    return ClearResult(False)


def clear_signature_stalled(db: Session, firm_id: UUID, dedup_key: str) -> ClearResult:
    """
    Clears when the envelope stops waiting, including a decline: a decline ends
    the waiting, which is what this item is about. The decline then raises its
    own item.
    """
    return _clear_when_waiting_ended(db, firm_id, dedup_key, "Signed")


def _generate_envelope_ending(
    db: Session, firm_id: UUID, status: str, item_type: str, verb: str
) -> list[Candidate]:
    """
    Shared shape for the two envelope endings that need the firm to act.

    Both fire the day the ending lands, with no day threshold, and both go quiet
    as soon as a replacement is sent. Neither can produce a row today, because
    nothing in the codebase writes these statuses. See the vocabulary note at
    the top of this module.
    """
    rows = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.firm_id == firm_id,
            SignatureEnvelope.status == status,
        )
    ).scalars().all()

    candidates: list[Candidate] = []
    for envelope in rows:
        if not _no_newer_envelope_sent(db, firm_id, envelope):
            continue

        # There is no declined_at or ended_at column on the envelope. expires_at
        # is the real moment for an expiry; for a decline the only timestamp
        # available is updated_at, which is a weak proxy and is recorded as a
        # ledger item rather than pretended to be exact.
        if status == ENVELOPE_STATUS_EXPIRED and envelope.expires_at is not None:
            days_since = _days_since(envelope.expires_at)
        else:
            days_since = _days_since(envelope.updated_at)

        candidates.append(
            Candidate(
                item_type=item_type,
                dedup_key=str(envelope.id),
                headline=(
                    f"Signature was {verb} {days_since} "
                    f"{_plural(days_since, 'day', 'days')} ago"
                    if days_since
                    else f"Signature was {verb}"
                ),
                payload={
                    "envelope_id": str(envelope.id),
                    "client_id": str(envelope.client_id),
                    "engagement_id": (
                        str(envelope.engagement_id) if envelope.engagement_id else None
                    ),
                    "days_since": days_since,
                    "ending": verb,
                },
                time_urgency=days_since,
                magnitude=None,
                measured={"days_since": days_since},
            )
        )
    return candidates


def generate_signature_declined(db: Session, firm_id: UUID) -> list[Candidate]:
    """A declined envelope with no replacement sent since. Copy says declined."""
    return _generate_envelope_ending(
        db, firm_id, ENVELOPE_STATUS_DECLINED, ITEM_SIGNATURE_DECLINED, "declined"
    )


def generate_signature_expired(db: Session, firm_id: UUID) -> list[Candidate]:
    """An expired envelope with no replacement sent since. Copy says expired."""
    return _generate_envelope_ending(
        db, firm_id, ENVELOPE_STATUS_EXPIRED, ITEM_SIGNATURE_EXPIRED, "expired"
    )


def _clear_envelope_ending(db: Session, firm_id: UUID, dedup_key: str) -> ClearResult:
    """Clears when a replacement envelope is sent, or the engagement closes."""
    envelope = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.id == UUID(dedup_key),
            SignatureEnvelope.firm_id == firm_id,
        )
    ).scalars().first()

    if envelope is None:
        return ClearResult(True, "No longer on file")

    if not _no_newer_envelope_sent(db, firm_id, envelope):
        return ClearResult(True, "Replacement sent")

    if envelope.engagement_id is not None:
        engagement = db.execute(
            select(Engagement).where(
                Engagement.id == envelope.engagement_id,
                Engagement.firm_id == firm_id,
            )
        ).scalars().first()
        if engagement is None or engagement.status in ("completed", "archived"):
            return ClearResult(True, "Engagement closed")

    return ClearResult(False)


clear_signature_declined = _clear_envelope_ending
clear_signature_expired = _clear_envelope_ending


# ---------------------------------------------------------------------------
# 6. deadline_with_blockers
# ---------------------------------------------------------------------------

OPEN_ENGAGEMENT_STATUSES_EXCLUDED = ("completed", "archived")


def _effective_deadline(engagement: Engagement) -> date | None:
    """extended_deadline overrides filing_deadline everywhere in this codebase."""
    return engagement.extended_deadline or engagement.filing_deadline


def _count_blockers(db: Session, firm_id: UUID, engagement_id: UUID) -> int:
    """
    Open prerequisites on an engagement: outstanding document request items,
    open tasks, and unsigned envelopes.

    Checklist items live in a JSON blob with no timestamps, so this counts
    current status only, which is all the blocker count needs.
    """
    outstanding_items = 0
    requests = db.execute(
        select(DocumentRequest).where(
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.engagement_id == engagement_id,
            DocumentRequest.status != "complete",
        )
    ).scalars().all()
    for request in requests:
        for item in (request.checklist_items or []):
            if item.get("status") not in ("approved", "waived"):
                outstanding_items += 1

    open_tasks = db.execute(
        select(func.count()).select_from(Task).where(
            Task.firm_id == firm_id,
            Task.engagement_id == engagement_id,
            Task.is_completed.is_(False),
        )
    ).scalar() or 0

    unsigned_envelopes = db.execute(
        select(func.count()).select_from(SignatureEnvelope).where(
            SignatureEnvelope.firm_id == firm_id,
            SignatureEnvelope.engagement_id == engagement_id,
            SignatureEnvelope.status == ENVELOPE_STATUS_SENT,
        )
    ).scalar() or 0

    return outstanding_items + int(open_tasks) + int(unsigned_envelopes)


def _extension_filed(db: Session, firm_id: UUID, engagement_id: UUID) -> bool:
    return (db.execute(
        select(func.count()).select_from(Extension).where(
            Extension.firm_id == firm_id,
            Extension.engagement_id == engagement_id,
        )
    ).scalar() or 0) > 0


def generate_deadline_with_blockers(db: Session, firm_id: UUID) -> list[Candidate]:
    """
    A deadline inside the window with at least one open prerequisite.

    A bare deadline with nothing open does NOT trigger. Magnitude never creates
    an item; the blockers are what make this urgent, and the count only boosts
    the ranking once urgency exists.
    """
    today = _today()
    horizon = today + timedelta(days=DEADLINE_WINDOW_DAYS)
    rows = db.execute(
        select(Engagement).where(
            Engagement.firm_id == firm_id,
            Engagement.status.notin_(OPEN_ENGAGEMENT_STATUSES_EXCLUDED),
            Engagement.efiled_at.is_(None),
        )
    ).scalars().all()

    candidates: list[Candidate] = []
    for engagement in rows:
        deadline = _effective_deadline(engagement)
        if deadline is None or deadline > horizon:
            continue
        if _extension_filed(db, firm_id, engagement.id):
            continue

        blockers = _count_blockers(db, firm_id, engagement.id)
        if blockers == 0:
            continue

        days_remaining = (deadline - today).days
        candidates.append(
            Candidate(
                item_type=ITEM_DEADLINE_WITH_BLOCKERS,
                dedup_key=str(engagement.id),
                headline=(
                    f"{engagement.name} is due in {days_remaining} "
                    f"{_plural(days_remaining, 'day', 'days')} with {blockers} open "
                    f"{_plural(blockers, 'item', 'items')}"
                    if days_remaining >= 0
                    else f"{engagement.name} is past its deadline with {blockers} open "
                    f"{_plural(blockers, 'item', 'items')}"
                ),
                payload={
                    "engagement_id": str(engagement.id),
                    "client_id": str(engagement.client_id),
                    "engagement_name": engagement.name,
                    "deadline": deadline.isoformat(),
                    "days_remaining": days_remaining,
                    "open_blockers": blockers,
                },
                time_urgency=DEADLINE_WINDOW_DAYS - days_remaining,
                # The ruled boost is blocker count. The engagement fee would
                # also boost it, but no fee column exists, so None stays None.
                magnitude=Decimal(blockers),
                measured={"open_blockers": blockers, "days_remaining": days_remaining},
            )
        )
    return candidates


def clear_deadline_with_blockers(db: Session, firm_id: UUID, dedup_key: str) -> ClearResult:
    """Clears on completion, e-file, a filed extension, or all prerequisites closing."""
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == UUID(dedup_key), Engagement.firm_id == firm_id
        )
    ).scalars().first()

    if engagement is None:
        return ClearResult(True, "No longer on file")
    if engagement.status in OPEN_ENGAGEMENT_STATUSES_EXCLUDED:
        return ClearResult(True, "Engagement closed")
    if engagement.efiled_at is not None:
        return ClearResult(True, "E-filed")
    if _extension_filed(db, firm_id, engagement.id):
        return ClearResult(True, "Extension filed")
    if _count_blockers(db, firm_id, engagement.id) == 0:
        return ClearResult(True, "All prerequisites closed")
    return ClearResult(False)


# ---------------------------------------------------------------------------
# 7. work_unbilled
# ---------------------------------------------------------------------------

def _has_invoice(db: Session, firm_id: UUID, engagement_id: UUID) -> bool:
    return (db.execute(
        select(func.count()).select_from(Invoice).where(
            Invoice.firm_id == firm_id,
            Invoice.engagement_id == engagement_id,
            Invoice.is_deleted.is_(False),
        )
    ).scalar() or 0) > 0


def generate_work_unbilled(db: Session, firm_id: UUID) -> list[Candidate]:
    """
    An engagement completed a while ago with no invoice raised against it.

    Reads engagements.completed_at, which is stamped on every transition into
    completed status. There is no backfill, so engagements completed before that
    column landed have completed_at NULL and never appear here. That is the
    ruled behavior, not a gap to paper over.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=UNBILLED_DAYS)
    rows = db.execute(
        select(Engagement).where(
            Engagement.firm_id == firm_id,
            Engagement.status == "completed",
            Engagement.completed_at.isnot(None),
            Engagement.completed_at <= cutoff,
        )
    ).scalars().all()

    candidates: list[Candidate] = []
    for engagement in rows:
        if _has_invoice(db, firm_id, engagement.id):
            continue

        days_since = _days_since(engagement.completed_at)
        candidates.append(
            Candidate(
                item_type=ITEM_WORK_UNBILLED,
                dedup_key=str(engagement.id),
                headline=(
                    f"{engagement.name} was completed {days_since} "
                    f"{_plural(days_since, 'day', 'days')} ago and has not been invoiced"
                ),
                payload={
                    "engagement_id": str(engagement.id),
                    "client_id": str(engagement.client_id),
                    "engagement_name": engagement.name,
                    "days_since_completion": days_since,
                },
                time_urgency=days_since,
                # The ruled boost is the engagement price. No price column
                # exists on engagements, so there is no boost. Never zero.
                magnitude=None,
                measured={"days_since_completion": days_since},
            )
        )
    return candidates


def clear_work_unbilled(db: Session, firm_id: UUID, dedup_key: str) -> ClearResult:
    """Clears when an invoice exists for that engagement."""
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == UUID(dedup_key), Engagement.firm_id == firm_id
        )
    ).scalars().first()

    if engagement is None:
        return ClearResult(True, "No longer on file")
    if _has_invoice(db, firm_id, engagement.id):
        return ClearResult(True, "Invoiced")
    return ClearResult(False)


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

GENERATORS: dict[str, Callable[[Session, UUID], list[Candidate]]] = {
    ITEM_INVOICE_OVERDUE: generate_invoice_overdue,
    ITEM_IRS_AUTH_EXPIRING: generate_irs_auth_expiring,
    ITEM_SIGNATURE_STALLED: generate_signature_stalled,
    ITEM_SIGNATURE_DECLINED: generate_signature_declined,
    ITEM_SIGNATURE_EXPIRED: generate_signature_expired,
    ITEM_DEADLINE_WITH_BLOCKERS: generate_deadline_with_blockers,
    ITEM_WORK_UNBILLED: generate_work_unbilled,
}

CLEAR_CONDITIONS: dict[str, Callable[[Session, UUID, str], ClearResult]] = {
    ITEM_INVOICE_OVERDUE: clear_invoice_overdue,
    ITEM_IRS_AUTH_EXPIRING: clear_irs_auth_expiring,
    ITEM_SIGNATURE_STALLED: clear_signature_stalled,
    ITEM_SIGNATURE_DECLINED: clear_signature_declined,
    ITEM_SIGNATURE_EXPIRED: clear_signature_expired,
    ITEM_DEADLINE_WITH_BLOCKERS: clear_deadline_with_blockers,
    ITEM_WORK_UNBILLED: clear_work_unbilled,
}

# Which measured number carries the delta, and whether the item is binary.
#
# A binary item is one where the underlying fact is on or off (a signature has
# arrived or it has not), so the only honest delta shapes are "nothing changed"
# and "got worse". A numeric item can also improve without clearing, which is
# the third shape: a partial payment on an overdue invoice, or one blocker
# closing out of four.
DELTA_METRIC: dict[str, str] = {
    ITEM_INVOICE_OVERDUE: "balance",
    ITEM_IRS_AUTH_EXPIRING: "days_to_expiry",
    ITEM_SIGNATURE_STALLED: "days_waiting",
    ITEM_SIGNATURE_DECLINED: "days_since",
    ITEM_SIGNATURE_EXPIRED: "days_since",
    ITEM_DEADLINE_WITH_BLOCKERS: "open_blockers",
    ITEM_WORK_UNBILLED: "days_since_completion",
}

NUMERIC_ITEM_TYPES = frozenset({ITEM_INVOICE_OVERDUE, ITEM_DEADLINE_WITH_BLOCKERS})

DELTA_NOTHING_CHANGED = "nothing_changed"
DELTA_GOT_WORSE = "got_worse"
DELTA_IMPROVED_NOT_MATERIALLY = "improved_not_materially"


def compute_delta_shape(item_type: str, before: dict | None, after: dict | None) -> str:
    """
    Describe the change across a suppression window.

    Compares the item's own measured numbers, never a reconstruction from the
    behavioral log. A material improvement is not a shape: it means the clear
    condition was met, the row resolved, and it never resurfaced to need copy.

    Anything unreadable (a missing snapshot, a metric that was never recorded)
    reads as nothing_changed rather than inventing a story about the change.
    """
    metric = DELTA_METRIC.get(item_type)
    if not metric or not before or not after:
        return DELTA_NOTHING_CHANGED

    old = before.get(metric)
    new = after.get(metric)
    if old is None or new is None:
        return DELTA_NOTHING_CHANGED

    if new == old:
        return DELTA_NOTHING_CHANGED

    if item_type not in NUMERIC_ITEM_TYPES:
        # Binary items only get worse with time. days_to_expiry falls as an
        # authorization ages, so a fall is still a worsening.
        return DELTA_GOT_WORSE

    if new > old:
        return DELTA_GOT_WORSE
    return DELTA_IMPROVED_NOT_MATERIALLY


def _compare_for_rank(a, b) -> int:
    """
    Tier, then time, then magnitude as a boost. Lower sorts first.

    The NULL-fee law lives in the last step. A magnitude of None is not a small
    magnitude and it is not zero: it is the absence of a boost. So when either
    side has no magnitude the comparison stops at time and returns a tie, which
    a stable sort leaves in its existing order. That is what "no boost and no
    penalty" means operationally.

    Treating None as Decimal(0) instead would look almost right and be wrong in
    a specific way: an unpriced item would sort below every priced item whose
    time it tied, which is a penalty for being unpriced. Treating it as
    infinitely large would be a boost. Neither is allowed.
    """
    if a.tier != b.tier:
        return -1 if a.tier < b.tier else 1

    # Higher urgency first.
    if a.time_urgency != b.time_urgency:
        return -1 if a.time_urgency > b.time_urgency else 1

    magnitude_a = getattr(a, "magnitude", None)
    magnitude_b = getattr(b, "magnitude", None)
    if magnitude_a is None or magnitude_b is None:
        return 0
    if magnitude_a != magnitude_b:
        return -1 if magnitude_a > magnitude_b else 1
    return 0


def rank_candidates(rows: list) -> list:
    """
    Order rows most urgent first.

    Callers pass any objects carrying tier, time_urgency and magnitude, so fresh
    Candidates and existing rows sort through exactly the same comparison.

    Python's sort is stable, which is what makes the None tie above mean "leave
    these two where they were" rather than "reorder them arbitrarily".
    """
    return sorted(rows, key=cmp_to_key(_compare_for_rank))
