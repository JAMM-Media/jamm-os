# app/services/surface_item_service.py

"""
Request-time behavior for the two curated surfaces.

The governing rule in this module, and the easiest thing to get wrong: THE ROW
GOVERNS AND THE LOG ECHOES. Every owner action writes the surface row first, as
operational truth, inside the request transaction. Only once that has committed
does the behavioral event fire, fire and forget. If the event write fails the
action still succeeded, because the action was the row.

Nothing here reads behavioral_events to decide anything.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import DismissalReason, SurfaceKind
from app.core.surface_constants import (
    BRIEFING_ACTIVE_CAP,
    BRIEFING_SUPPRESSION_DAYS,
    OBSERVATORY_SUPPRESSION_DAYS,
)
from app.models.behavioral_event import BehavioralEvent
from app.models.client import Client
from app.models.document import Document
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.invoice import Invoice
from app.models.irs_authorization import IrsAuthorization
from app.models.signature_envelope import SignatureEnvelope
from app.models.surface_item import SurfaceItem
from app.models.user import User
from app.services.behavioral_log import log_event
from app.services.surface_daily_job import (
    RankShim,
    is_active,
    is_permanently_dismissed,
)
from app.services.surface_generators import (
    CLEAR_CONDITIONS,
    _count_blockers,
    rank_candidates,
    ITEM_DEADLINE_WITH_BLOCKERS,
    ITEM_INVOICE_OVERDUE,
    ITEM_IRS_AUTH_EXPIRING,
    ITEM_SIGNATURE_DECLINED,
    ITEM_SIGNATURE_EXPIRED,
    ITEM_SIGNATURE_STALLED,
    ITEM_WORK_UNBILLED,
)

logger = logging.getLogger(__name__)

# Reasons that start a suppression window rather than ending the item.
SUPPRESSING_REASONS = (DismissalReason.already_handling,)



def _attach_client_names(db: Session, firm_id: UUID, rows: list) -> None:
    """
    Batch-resolves client names and sets row.client_name in place.

    Collects distinct, valid client_id UUIDs from each row's payload, runs
    one query scoped to firm_id, and attaches the name directly to the row
    object. Rows with no client_id key or an unparseable value are silently
    skipped and receive client_name = None.
    """
    client_ids: set = set()
    for row in rows:
        raw = (row.payload or {}).get("client_id")
        if not raw:
            continue
        try:
            client_ids.add(UUID(raw))
        except (ValueError, AttributeError):
            continue

    name_map: dict = {}
    if client_ids:
        clients = db.execute(
            select(Client).where(
                Client.id.in_(client_ids),
                Client.firm_id == firm_id,
            )
        ).scalars().all()
        name_map = {c.id: c.name for c in clients}

    for row in rows:
        raw = (row.payload or {}).get("client_id")
        try:
            cid = UUID(raw) if raw else None
        except (ValueError, AttributeError):
            cid = None
        row.client_name = name_map.get(cid)

# ---------------------------------------------------------------------------
# Tier 1 summary
# ---------------------------------------------------------------------------

def _tier1_groups(items: list) -> dict:
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for item in items:
        groups[item.item_type].append(item)
    return groups


def _tier1_invoice_stats(items: list) -> tuple:
    from decimal import Decimal
    n = len(items)
    total = float(sum(Decimal(str(i.payload.get("balance", 0))) for i in items))
    return n, total


def _tier1_deadline_stats(items: list) -> tuple:
    n = len(items)
    total_blockers = sum(i.payload.get("open_blockers", 0) for i in items)
    return n, total_blockers


def build_tier1_summary(items: list) -> str:
    """
    Deterministic summary sentence from real payload counts and sums.
    Reads only payload fields written by the generators. Zero additional queries.
    """
    groups = _tier1_groups(items)
    parts: list[str] = []

    overdue = groups.get(ITEM_INVOICE_OVERDUE, [])
    if overdue:
        n, total = _tier1_invoice_stats(overdue)
        noun = "invoice" if n == 1 else "invoices"
        parts.append(f"{n} {noun} overdue, balances totaling ${total:,.0f}")

    irs = groups.get(ITEM_IRS_AUTH_EXPIRING, [])
    if irs:
        n = len(irs)
        noun = "IRS authorization" if n == 1 else "IRS authorizations"
        parts.append(f"{n} {noun} expiring")

    sigs = (
        groups.get(ITEM_SIGNATURE_STALLED, [])
        + groups.get(ITEM_SIGNATURE_DECLINED, [])
        + groups.get(ITEM_SIGNATURE_EXPIRED, [])
    )
    if sigs:
        n = len(sigs)
        noun = "signature request" if n == 1 else "signature requests"
        parts.append(f"{n} {noun} pending")

    deadlines = groups.get(ITEM_DEADLINE_WITH_BLOCKERS, [])
    if deadlines:
        n, total_blockers = _tier1_deadline_stats(deadlines)
        noun = "deadline" if n == 1 else "deadlines"
        item_noun = "open item" if total_blockers == 1 else "open items"
        parts.append(f"{n} {noun} with {total_blockers} {item_noun}")

    unbilled = groups.get(ITEM_WORK_UNBILLED, [])
    if unbilled:
        n = len(unbilled)
        noun = "engagement" if n == 1 else "engagements"
        parts.append(f"{n} completed {noun} not yet invoiced")

    if not parts:
        return "You're all caught up."
    return "; ".join(parts) + "."


def build_tier1_facts(items: list) -> list:
    """
    Per-category fact list for Tier 1 structured display.
    Returns one dict per category that has items, each with:
      category: str, text: str, count: int, amount: Optional[float]
    If no items, returns a single "none" entry with the caught-up message.
    """
    groups = _tier1_groups(items)
    facts: list[dict] = []

    overdue = groups.get(ITEM_INVOICE_OVERDUE, [])
    if overdue:
        n, total = _tier1_invoice_stats(overdue)
        noun = "invoice" if n == 1 else "invoices"
        facts.append({
            "category": "overdue_invoices",
            "text": f"{n} {noun} are overdue, with balances totaling ${total:,.0f}",
            "count": n,
            "amount": total,
        })

    irs = groups.get(ITEM_IRS_AUTH_EXPIRING, [])
    if irs:
        n = len(irs)
        noun = "IRS authorization" if n == 1 else "IRS authorizations"
        facts.append({
            "category": "irs_authorizations",
            "text": f"{n} {noun} expiring",
            "count": n,
            "amount": None,
        })

    sigs = (
        groups.get(ITEM_SIGNATURE_STALLED, [])
        + groups.get(ITEM_SIGNATURE_DECLINED, [])
        + groups.get(ITEM_SIGNATURE_EXPIRED, [])
    )
    if sigs:
        n = len(sigs)
        noun = "signature request" if n == 1 else "signature requests"
        facts.append({
            "category": "signature_requests",
            "text": f"{n} {noun} pending",
            "count": n,
            "amount": None,
        })

    deadlines = groups.get(ITEM_DEADLINE_WITH_BLOCKERS, [])
    if deadlines:
        n, total_blockers = _tier1_deadline_stats(deadlines)
        noun = "deadline" if n == 1 else "deadlines"
        item_noun = "open item" if total_blockers == 1 else "open items"
        facts.append({
            "category": "deadlines",
            "text": f"{n} {noun} with {total_blockers} {item_noun}",
            "count": n,
            "amount": float(total_blockers),
        })

    unbilled = groups.get(ITEM_WORK_UNBILLED, [])
    if unbilled:
        n = len(unbilled)
        noun = "engagement" if n == 1 else "engagements"
        facts.append({
            "category": "unbilled_work",
            "text": f"{n} completed {noun} not yet invoiced",
            "count": n,
            "amount": None,
        })

    if not facts:
        return [{"category": "none", "text": "You're all caught up.", "count": 0, "amount": None}]
    return facts


def _now() -> datetime:
    return datetime.now(timezone.utc)


def suppression_days_for(kind: SurfaceKind) -> int:
    """7 days on the Briefing, 14 in the Observatory, counted from the click."""
    return (
        OBSERVATORY_SUPPRESSION_DAYS
        if kind == SurfaceKind.observatory
        else BRIEFING_SUPPRESSION_DAYS
    )


def get_item_for_firm(db: Session, item_id: UUID, firm_id: UUID) -> Optional[SurfaceItem]:
    """
    Absent or another firm's reads the same from here: None, which the router
    turns into a 404. A cross-firm probe learns nothing about what exists.
    """
    return db.execute(
        select(SurfaceItem).where(
            SurfaceItem.id == item_id,
            SurfaceItem.firm_id == firm_id,
        )
    ).scalars().first()


def _fire(event_type: str, row: SurfaceItem, metadata: dict, actor_id) -> None:
    """
    The recorder. Called only after the row write has committed, and never
    allowed to affect the outcome of the action it is recording.
    """
    try:
        log_event(
            firm_id=row.firm_id,
            event_type=event_type,
            entity_type="surface_item",
            entity_id=row.id,
            actor_type="staff",
            actor_id=actor_id,
            metadata=metadata,
        )
    except Exception as exc:  # pragma: no cover - recorder must never raise
        logger.warning("%s recorder failed for %s: %s", event_type, row.id, exc)


def _measured_now(row: SurfaceItem) -> dict:
    return (row.payload or {}).get("measured") or {}


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------

def get_briefing(db: Session, firm_id: UUID, actor_id=None) -> dict:
    """
    Serve today's Briefing.

    Re-checks the clear condition of ONLY the rows being served, so a row that
    cleared since this morning is shown resolved in place, keeping its slot for
    the rest of the day rather than reshuffling the list under the reader. A
    dismissed or implemented row is already unslotted and simply is not here.

    appearance_count counts times served, not calendar days, and last_served_on
    makes that increment idempotent within a day.
    """
    now = _now()
    today = now.date()

    rows = list(db.execute(
        select(SurfaceItem).where(
            SurfaceItem.firm_id == firm_id,
            SurfaceItem.kind == SurfaceKind.briefing,
            SurfaceItem.slotted_at.isnot(None),
        ).order_by(SurfaceItem.rank)
    ).scalars().all())

    resolved_in_place = 0
    for row in rows:
        if row.resolved_at is not None:
            continue
        clear_condition = CLEAR_CONDITIONS.get(row.item_type)
        if clear_condition is None:
            continue
        try:
            result = clear_condition(db, firm_id, row.dedup_key)
        except (ValueError, AttributeError, TypeError):
            continue
        if result.cleared:
            row.resolved_at = now
            if result.outcome:
                payload = dict(row.payload or {})
                payload["resolved_outcome"] = result.outcome
                row.payload = payload
            resolved_in_place += 1

    for row in rows:
        if row.last_served_on != today:
            row.appearance_count = (row.appearance_count or 0) + 1
            row.last_served_on = today

    db.commit()

    for row in rows:
        db.refresh(row)

    _attach_client_names(db, firm_id, rows)

    # Recorder, after every row write has committed. The entity is the firm,
    # because a view is about the surface rather than any one item on it.
    try:
        log_event(
            firm_id=firm_id,
            event_type="briefing.viewed",
            entity_type="firm",
            entity_id=firm_id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={
                "served_item_ids": [str(row.id) for row in rows],
                "count": len(rows),
                "resolved_in_place": resolved_in_place,
            },
        )
    except Exception as exc:  # pragma: no cover - recorder must never raise
        logger.warning("briefing.viewed recorder failed for firm %s: %s", firm_id, exc)

    return {
        "items": rows,
        "count": len(rows),
        "resolved_in_place": resolved_in_place,
        "summary": build_tier1_summary(rows),
        "facts": build_tier1_facts(rows),
        # Honest state: nothing has cleared the intelligence bar yet, because no
        # technique exists to clear it. The frontend renders this as
        # "collecting", never as an empty result that implies all is well.
        "intelligence_pending": True,
    }


def get_observatory(db: Session, firm_id: UUID) -> dict:
    """
    Active material signals. Empty on day one by construction: nothing can be
    promoted while the promotion registry is empty.

    The response says emptiness unambiguously with an explicit count and an
    explicit flag, so the frontend never has to infer it from a bare list.
    """
    now = _now()
    rows = [
        row for row in db.execute(
            select(SurfaceItem).where(
                SurfaceItem.firm_id == firm_id,
                SurfaceItem.kind == SurfaceKind.observatory,
                SurfaceItem.resolved_at.is_(None),
            ).order_by(SurfaceItem.rank)
        ).scalars().all()
        if is_active(row, now)
    ]

    _attach_client_names(db, firm_id, rows)

    return {
        "items": rows,
        "count": len(rows),
        "is_empty": len(rows) == 0,
        "intelligence_pending": True,
    }


# ---------------------------------------------------------------------------
# Owner actions
# ---------------------------------------------------------------------------

def dismiss_item(
    db: Session,
    item: SurfaceItem,
    reason: DismissalReason,
    actor_id=None,
) -> SurfaceItem:
    """
    Record a dismissal. The row is the truth; the event is the echo.

    already_handling starts a suppression window and the item comes back at
    expiry with delta copy. not_relevant and was_wrong never resurface, and
    was_wrong additionally flags the row for later human review. v1 records and
    does nothing automatic: no threshold anywhere responds to this yet.
    """
    now = _now()

    item.dismissed_at = now
    item.dismissal_reason = reason
    item.value_at_action = _measured_now(item)
    item.slotted_at = None

    if reason in SUPPRESSING_REASONS:
        item.suppressed_until = now + timedelta(days=suppression_days_for(item.kind))
    else:
        item.suppressed_until = None

    if reason == DismissalReason.was_wrong:
        item.flagged_for_review = True

    db.commit()
    db.refresh(item)

    _fire("surface_item.dismissed", item, {
        "item_type": item.item_type,
        "kind": str(item.kind.value),
        "reason": reason.value,
        "value_at_action": item.value_at_action,
        "appearance_count": item.appearance_count,
    }, actor_id)

    return item


def implement_item(db: Session, item: SurfaceItem, actor_id=None) -> SurfaceItem:
    """
    Record that the owner has dealt with the item.

    A separate action from dismissal, with its own event. The frontend labels it
    Done on the Briefing and Addressed in the Observatory; the backend serves
    the kind and never the label.
    """
    now = _now()

    item.implemented_at = now
    item.value_at_action = _measured_now(item)
    item.suppressed_until = now + timedelta(days=suppression_days_for(item.kind))
    item.slotted_at = None

    db.commit()
    db.refresh(item)

    _fire("surface_item.implemented", item, {
        "item_type": item.item_type,
        "kind": str(item.kind.value),
        "value_at_action": item.value_at_action,
        "appearance_count": item.appearance_count,
    }, actor_id)

    return item


def promote_next_briefing_item(db: Session, firm_id: UUID) -> Optional[SurfaceItem]:
    """
    Slot the single next-ranked active unslotted briefing row.

    Slots never auto-fill. When one opens because the owner dismissed or
    implemented something, it stays open until they explicitly ask for another,
    which is this endpoint. Returns None when there is nothing left to promote,
    which the router reports honestly rather than as an error.
    """
    now = _now()

    slotted_count = len([
        row for row in db.execute(
            select(SurfaceItem).where(
                SurfaceItem.firm_id == firm_id,
                SurfaceItem.kind == SurfaceKind.briefing,
                SurfaceItem.slotted_at.isnot(None),
                SurfaceItem.resolved_at.is_(None),
            )
        ).scalars().all()
    ])
    if slotted_count >= BRIEFING_ACTIVE_CAP:
        return None

    candidates = [
        row for row in db.execute(
            select(SurfaceItem).where(
                SurfaceItem.firm_id == firm_id,
                SurfaceItem.kind == SurfaceKind.briefing,
                SurfaceItem.slotted_at.is_(None),
                SurfaceItem.resolved_at.is_(None),
            )
        ).scalars().all()
        if is_active(row, now) and not is_permanently_dismissed(row)
    ]
    if not candidates:
        return None

    ordered = rank_candidates([RankShim(row) for row in candidates])
    winner = ordered[0].row
    winner.slotted_at = now
    db.commit()
    db.refresh(winner)
    return winner


# ---------------------------------------------------------------------------
# Tier 2 per-item detail
# ---------------------------------------------------------------------------

def get_item_detail(db: Session, item: SurfaceItem, firm_id: UUID) -> dict:
    """
    Compute the ten approved detail fields for one surface item.
    All ten fields are always present. "Not recorded" is the honest fallback
    for any field with no real source for this item type.
    This is a display-only computation; nothing here makes a lifecycle decision.
    """
    NOT_RECORDED = "Not recorded"
    p = item.payload or {}
    t = item.item_type

    client_id_str = p.get("client_id")
    engagement_id_str = p.get("engagement_id")
    invoice_id_str = p.get("invoice_id")
    auth_id_str = p.get("authorization_id")
    envelope_id_str = p.get("envelope_id")

    # Fetch all entity objects we may need.
    client_obj = None
    if client_id_str:
        try:
            client_obj = db.execute(
                select(Client).where(Client.id == UUID(client_id_str), Client.firm_id == firm_id)
            ).scalars().first()
        except (ValueError, AttributeError):
            pass

    engagement_obj = None
    if engagement_id_str:
        try:
            engagement_obj = db.execute(
                select(Engagement).where(
                    Engagement.id == UUID(engagement_id_str), Engagement.firm_id == firm_id
                )
            ).scalars().first()
        except (ValueError, AttributeError):
            pass

    invoice_obj = None
    if t == ITEM_INVOICE_OVERDUE and invoice_id_str:
        try:
            invoice_obj = db.execute(
                select(Invoice).where(Invoice.id == UUID(invoice_id_str), Invoice.firm_id == firm_id)
            ).scalars().first()
        except (ValueError, AttributeError):
            pass

    auth_obj = None
    if t == ITEM_IRS_AUTH_EXPIRING and auth_id_str:
        try:
            auth_obj = db.execute(
                select(IrsAuthorization).where(
                    IrsAuthorization.id == UUID(auth_id_str), IrsAuthorization.firm_id == firm_id
                )
            ).scalars().first()
        except (ValueError, AttributeError):
            pass

    envelope_obj = None
    if t in (ITEM_SIGNATURE_STALLED, ITEM_SIGNATURE_DECLINED, ITEM_SIGNATURE_EXPIRED) and envelope_id_str:
        try:
            envelope_obj = db.execute(
                select(SignatureEnvelope).where(
                    SignatureEnvelope.id == UUID(envelope_id_str), SignatureEnvelope.firm_id == firm_id
                )
            ).scalars().first()
        except (ValueError, AttributeError):
            pass

    # 1. CLIENT
    client = client_obj.name if client_obj else NOT_RECORDED

    # 2. ENGAGEMENT
    if p.get("engagement_name"):
        engagement = p["engagement_name"]
    elif engagement_obj:
        engagement = engagement_obj.name
    else:
        engagement = NOT_RECORDED

    # 3. ASSIGNED STAFF
    assigned_staff = NOT_RECORDED
    if engagement_id_str:
        try:
            eid = UUID(engagement_id_str)
            members = db.execute(
                select(EngagementMember).where(
                    EngagementMember.engagement_id == eid,
                    EngagementMember.firm_id == firm_id,
                ).order_by(EngagementMember.is_administrator.desc())
            ).scalars().all()
            if members:
                user_obj = db.execute(
                    select(User).where(User.id == members[0].user_id)
                ).scalars().first()
                if user_obj and user_obj.full_name:
                    assigned_staff = user_obj.full_name
        except (ValueError, AttributeError):
            pass

    # 4. INVOICE / BALANCE
    if t == ITEM_INVOICE_OVERDUE and invoice_obj:
        bal = p.get("balance")
        if bal is not None:
            invoice_balance = f"Invoice {invoice_obj.invoice_number}, balance ${float(bal):,.2f}"
        else:
            invoice_balance = f"Invoice {invoice_obj.invoice_number}"
    else:
        invoice_balance = NOT_RECORDED

    # 5. DAYS OVERDUE (time metric appropriate to item type)
    def _fmt_days(n: int, label: str) -> str:
        return f"{n} {'day' if n == 1 else 'days'} {label}"

    days_overdue = NOT_RECORDED
    if t == ITEM_INVOICE_OVERDUE and p.get("days_overdue") is not None:
        days_overdue = _fmt_days(p["days_overdue"], "overdue")
    elif t == ITEM_IRS_AUTH_EXPIRING and p.get("days_to_expiry") is not None:
        days_overdue = _fmt_days(p["days_to_expiry"], "to expiry")
    elif t == ITEM_SIGNATURE_STALLED and p.get("days_waiting") is not None:
        days_overdue = _fmt_days(p["days_waiting"], "waiting")
    elif t in (ITEM_SIGNATURE_DECLINED, ITEM_SIGNATURE_EXPIRED) and p.get("days_since") is not None:
        days_overdue = _fmt_days(p["days_since"], "ago")
    elif t == ITEM_DEADLINE_WITH_BLOCKERS and p.get("days_remaining") is not None:
        n = p["days_remaining"]
        days_overdue = _fmt_days(n, "remaining") if n >= 0 else _fmt_days(abs(n), "past deadline")
    elif t == ITEM_WORK_UNBILLED and p.get("days_since_completion") is not None:
        days_overdue = _fmt_days(p["days_since_completion"], "since completion")

    # 6. CURRENT WORKFLOW STATUS
    if t == ITEM_INVOICE_OVERDUE and invoice_obj:
        st = invoice_obj.status
        current_status = st.value if hasattr(st, "value") else str(st)
    elif t in (ITEM_DEADLINE_WITH_BLOCKERS, ITEM_WORK_UNBILLED) and engagement_obj:
        current_status = str(engagement_obj.status)
    elif t in (ITEM_SIGNATURE_STALLED, ITEM_SIGNATURE_DECLINED, ITEM_SIGNATURE_EXPIRED) and envelope_obj:
        current_status = str(envelope_obj.status)
    elif t == ITEM_IRS_AUTH_EXPIRING and auth_obj:
        current_status = str(auth_obj.status)
    else:
        current_status = NOT_RECORDED

    # 7. ISSUED DATE
    # IrsAuthorization has valid_from (real column confirmed); no engagement_id.
    # deadline_with_blockers and work_unbilled: "Not recorded" (no real issued concept).
    if t == ITEM_INVOICE_OVERDUE and invoice_obj and invoice_obj.sent_at:
        issued_date = invoice_obj.sent_at.strftime("%Y-%m-%d")
    elif t in (ITEM_SIGNATURE_STALLED, ITEM_SIGNATURE_DECLINED, ITEM_SIGNATURE_EXPIRED) and envelope_obj and envelope_obj.sent_at:
        issued_date = envelope_obj.sent_at.strftime("%Y-%m-%d")
    elif t == ITEM_IRS_AUTH_EXPIRING and auth_obj and auth_obj.valid_from:
        issued_date = auth_obj.valid_from.isoformat()
    else:
        issued_date = NOT_RECORDED

    # 8. LAST CLIENT COMMUNICATION
    # Display-only read of BehavioralEvent -- makes no lifecycle decision.
    last_communication = NOT_RECORDED
    if client_id_str:
        try:
            cid = UUID(client_id_str)
            comm_event = db.execute(
                select(BehavioralEvent).where(
                    BehavioralEvent.firm_id == firm_id,
                    BehavioralEvent.entity_type == "client",
                    BehavioralEvent.entity_id == cid,
                    BehavioralEvent.event_type.in_([
                        "email.reply_sent",
                        "email.composed_sent",
                        "portal.message_sent",
                    ]),
                ).order_by(BehavioralEvent.occurred_at.desc()).limit(1)
            ).scalars().first()

            signal_event = db.execute(
                select(BehavioralEvent).where(
                    BehavioralEvent.firm_id == firm_id,
                    BehavioralEvent.entity_type == "client",
                    BehavioralEvent.entity_id == cid,
                    BehavioralEvent.event_type.in_([
                        "gmail.signals_extracted",
                        "outlook.signals_extracted",
                    ]),
                ).order_by(BehavioralEvent.occurred_at.desc()).limit(1)
            ).scalars().first()

            candidates_dt: list[datetime] = []
            if comm_event:
                ts = comm_event.occurred_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                candidates_dt.append(ts)

            if signal_event and signal_event.extra_metadata:
                lcd = signal_event.extra_metadata.get("last_contact_date")
                if lcd:
                    try:
                        lcd_str = str(lcd)
                        if "T" in lcd_str:
                            parsed = datetime.fromisoformat(lcd_str)
                        else:
                            parsed = datetime.combine(
                                date.fromisoformat(lcd_str), time.min, tzinfo=timezone.utc
                            )
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        candidates_dt.append(parsed)
                    except (ValueError, TypeError, AttributeError):
                        pass

            if candidates_dt:
                last_communication = max(candidates_dt).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            pass

    # 9. RELATED DOCUMENTS ON FILE
    related_documents_count = 0
    if engagement_id_str:
        try:
            eid = UUID(engagement_id_str)
            related_documents_count = db.execute(
                select(func.count()).select_from(Document).where(
                    Document.firm_id == firm_id,
                    Document.engagement_id == eid,
                    Document.deleted_at.is_(None),
                    Document.is_superseded.is_(False),
                )
            ).scalar() or 0
        except (ValueError, AttributeError):
            pass
    elif client_id_str:
        try:
            cid = UUID(client_id_str)
            related_documents_count = db.execute(
                select(func.count()).select_from(Document).where(
                    Document.firm_id == firm_id,
                    Document.client_id == cid,
                    Document.deleted_at.is_(None),
                    Document.is_superseded.is_(False),
                )
            ).scalar() or 0
        except (ValueError, AttributeError):
            pass

    # 10. OPEN ITEMS ALREADY IN THE RECORD
    if t == ITEM_INVOICE_OVERDUE and invoice_obj:
        rc = invoice_obj.reminder_count or 0
        lrsa = invoice_obj.last_reminder_sent_at
        if rc == 0:
            open_items = "No reminders sent"
        elif lrsa:
            open_items = (
                f"{rc} {'reminder' if rc == 1 else 'reminders'} sent, "
                f"most recently {lrsa.strftime('%Y-%m-%d')}"
            )
        else:
            open_items = f"{rc} {'reminder' if rc == 1 else 'reminders'} sent"
    elif engagement_id_str and t in (
        ITEM_DEADLINE_WITH_BLOCKERS,
        ITEM_WORK_UNBILLED,
        ITEM_SIGNATURE_STALLED,
        ITEM_SIGNATURE_DECLINED,
        ITEM_SIGNATURE_EXPIRED,
    ):
        try:
            eid = UUID(engagement_id_str)
            bc = _count_blockers(db, firm_id, eid)
            if bc == 0:
                open_items = "No open items"
            else:
                open_items = f"{bc} open {'item' if bc == 1 else 'items'}"
        except (ValueError, AttributeError):
            open_items = NOT_RECORDED
    else:
        open_items = NOT_RECORDED

    return {
        "client": client,
        "engagement": engagement,
        "assigned_staff": assigned_staff,
        "invoice_balance": invoice_balance,
        "days_overdue": days_overdue,
        "current_workflow_status": current_status,
        "issued_date": issued_date,
        "last_client_communication": last_communication,
        "related_documents_count": related_documents_count,
        "open_items": open_items,
    }
