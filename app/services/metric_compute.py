# app/services/metric_compute.py

"""
Pure compute functions for the nightly metric aggregation pipeline.

Percent metrics (unit="percent" in metric_registry) are stored on a 0-100
scale, never 0-1.

All compute functions receive a SQLAlchemy Session and never create one;
session lifecycle belongs to metric_pipeline.run_nightly_metric_recompute.
Every observation and week boundary is computed in UTC. Week convention is
ISO weeks starting Monday; week_start stores the Monday date.

Per docs/metric_clock_definitions.md's Week Attribution section: deadline
adherence tracks bucket to the week the deadline fell in, not the outcome
week, and observations whose deadline week is later than the current week
are not written yet -- they sit in the event stream and materialize on a
future recompute once their week actually arrives.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from statistics import stdev
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.automation_preset_catalog import PRESET_CATALOG
from app.models.behavioral_event import BehavioralEvent
from app.models.document_request import DocumentRequest
from app.models.firm import Firm
from app.models.metric_registry import MetricRegistry
from app.models.metric_value import MetricValue


# ---------------------------------------------------------------------------
# Week / time helpers
# ---------------------------------------------------------------------------

def _week_start_from_date(d: date) -> date:
    """Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


def _week_start(dt: datetime) -> date:
    """Monday of the ISO week containing dt, computed in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return _week_start_from_date(dt.astimezone(timezone.utc).date())


def _week_end(week_start: date) -> datetime:
    """Sunday 23:59:59 UTC of the week starting week_start."""
    return datetime.combine(week_start + timedelta(days=6), time(23, 59, 59), tzinfo=timezone.utc)


def _current_week_start(now: Optional[datetime] = None) -> date:
    return _week_start(now or datetime.now(timezone.utc))


def _parse_date(value) -> Optional[date]:
    if value is None:
        return None
    return date.fromisoformat(value)


# ---------------------------------------------------------------------------
# Event fetch helper
# ---------------------------------------------------------------------------

def _fetch_events(db: Session, firm_id: uuid.UUID, event_types: list[str]) -> list[BehavioralEvent]:
    stmt = (
        select(BehavioralEvent)
        .where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type.in_(event_types),
        )
        .order_by(BehavioralEvent.occurred_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def _upsert_metric_value(
    db: Session,
    *,
    firm_id: uuid.UUID,
    metric_id: uuid.UUID,
    week_start: date,
    value: Optional[float],
    sample_size: int,
    std_dev: Optional[float],
    computed_at: datetime,
) -> None:
    stmt = pg_insert(MetricValue).values(
        id=uuid.uuid4(),
        firm_id=firm_id,
        metric_id=metric_id,
        week_start=week_start,
        value=value,
        sample_size=sample_size,
        std_dev=std_dev,
        computed_at=computed_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["firm_id", "metric_id", "week_start"],
        set_={
            "value": stmt.excluded.value,
            "sample_size": stmt.excluded.sample_size,
            "std_dev": stmt.excluded.std_dev,
            "computed_at": stmt.excluded.computed_at,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    db.execute(stmt)


def _sample_std_dev(values: list[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    return stdev(values)


def _write_weekly_series(
    db: Session,
    *,
    firm_id: uuid.UUID,
    metric_id: uuid.UUID,
    observations: dict[date, list[float]],
    first_week: date,
    last_week: date,
    computed_at: datetime,
) -> None:
    """Writes a contiguous run of weeks [first_week, last_week], zero-sample
    (value=NULL) where observations has nothing for that week."""
    week = first_week
    while week <= last_week:
        values = observations.get(week, [])
        if values:
            value = sum(values) / len(values)
            sample_size = len(values)
            std_dev = _sample_std_dev(values)
        else:
            value = None
            sample_size = 0
            std_dev = None
        _upsert_metric_value(
            db,
            firm_id=firm_id,
            metric_id=metric_id,
            week_start=week,
            value=value,
            sample_size=sample_size,
            std_dev=std_dev,
            computed_at=computed_at,
        )
        week += timedelta(days=7)


# ---------------------------------------------------------------------------
# Metric 1 -- engagement_velocity
# ---------------------------------------------------------------------------

def _build_engagement_velocity(db: Session, firm_id: uuid.UUID, current_week: date):
    events = _fetch_events(db, firm_id, ["engagement.created", "engagement.completed"])

    created_at_by_entity: dict[uuid.UUID, datetime] = {}
    completed_at_by_entity: dict[uuid.UUID, datetime] = {}
    for ev in events:
        if ev.entity_id is None:
            continue
        if ev.event_type == "engagement.created":
            if ev.entity_id not in created_at_by_entity:
                created_at_by_entity[ev.entity_id] = ev.occurred_at
        else:
            prev = completed_at_by_entity.get(ev.entity_id)
            if prev is None or ev.occurred_at > prev:
                completed_at_by_entity[ev.entity_id] = ev.occurred_at

    observations: dict[date, list[float]] = {}
    for entity_id, completed_at in completed_at_by_entity.items():
        created_at = created_at_by_entity.get(entity_id)
        if created_at is None:
            continue
        duration_days = (completed_at - created_at).total_seconds() / 86400
        observations.setdefault(_week_start(completed_at), []).append(duration_days)

    first_week = _week_start(min(created_at_by_entity.values())) if created_at_by_entity else None
    return first_week, observations


# ---------------------------------------------------------------------------
# Metric 2 -- deadline_adherence_{original,extended,operative}
# ---------------------------------------------------------------------------

def _build_deadline_adherence_track(db: Session, firm_id: uuid.UUID, current_week: date, track: str):
    completed_events = _fetch_events(db, firm_id, ["engagement.completed"])
    missed_events = _fetch_events(db, firm_id, ["engagement.deadline_missed"])

    latest_completed: dict[uuid.UUID, BehavioralEvent] = {}
    for ev in completed_events:
        if ev.entity_id is None:
            continue
        prev = latest_completed.get(ev.entity_id)
        if prev is None or ev.occurred_at > prev.occurred_at:
            latest_completed[ev.entity_id] = ev

    misses: dict[tuple[uuid.UUID, str], BehavioralEvent] = {}
    for ev in missed_events:
        if ev.entity_id is None or not ev.extra_metadata:
            continue
        deadline_type = ev.extra_metadata.get("deadline_type")
        if deadline_type:
            misses[(ev.entity_id, deadline_type)] = ev

    entity_ids = set(latest_completed.keys()) | {eid for (eid, _t) in misses.keys()}

    observations: dict[date, list[float]] = {}
    deadline_weeks: list[date] = []

    for entity_id in entity_ids:
        completed_ev = latest_completed.get(entity_id)
        meta = completed_ev.extra_metadata if completed_ev and completed_ev.extra_metadata else {}
        filing_deadline = _parse_date(meta.get("filing_deadline"))
        extended_deadline = _parse_date(meta.get("extended_deadline"))

        miss_ev: Optional[BehavioralEvent] = None
        deadline: Optional[date] = None

        if track == "original":
            miss_ev = misses.get((entity_id, "original"))
            deadline = filing_deadline or (
                _parse_date(miss_ev.extra_metadata.get("deadline_date")) if miss_ev else None
            )
        elif track == "extended":
            # Only where an extension exists.
            miss_ev = misses.get((entity_id, "extended"))
            deadline = extended_deadline or (
                _parse_date(miss_ev.extra_metadata.get("deadline_date")) if miss_ev else None
            )
        else:  # operative -- extended if set, original otherwise
            if extended_deadline is not None:
                deadline = extended_deadline
                miss_ev = misses.get((entity_id, "extended"))
            elif filing_deadline is not None:
                deadline = filing_deadline
                miss_ev = misses.get((entity_id, "original"))
            else:
                miss_ev = misses.get((entity_id, "extended")) or misses.get((entity_id, "original"))
                deadline = _parse_date(miss_ev.extra_metadata.get("deadline_date")) if miss_ev else None

        if deadline is None:
            continue

        deadline_week = _week_start_from_date(deadline)
        if deadline_week > current_week:
            # Future deadline week -- don't write yet; a hit derived from an
            # early completion against a not-yet-arrived deadline week would
            # misrepresent a week that hasn't happened.
            continue

        if miss_ev is not None:
            value = 0.0
        elif completed_ev is not None and completed_ev.occurred_at.date() <= deadline:
            value = 100.0
        else:
            # Not yet resolved either way (still pending, deadline in the
            # future relative to now, or deadline passed but the sweep
            # hasn't recorded the miss yet).
            continue

        observations.setdefault(deadline_week, []).append(value)
        deadline_weeks.append(deadline_week)

    first_week = min(deadline_weeks) if deadline_weeks else None
    return first_week, observations


# ---------------------------------------------------------------------------
# Metric 3 -- document_collection_speed
# ---------------------------------------------------------------------------

def _build_document_collection_speed(db: Session, firm_id: uuid.UUID, current_week: date):
    request_events = _fetch_events(db, firm_id, ["document_request.sent"])
    item_events = _fetch_events(
        db, firm_id, ["document_request.item_uploaded", "document_request.item_waived"]
    )

    sent_at_by_request: dict[uuid.UUID, datetime] = {}
    for ev in request_events:
        if ev.entity_id is None:
            continue
        if ev.entity_id not in sent_at_by_request:
            sent_at_by_request[ev.entity_id] = ev.occurred_at

    waived_items: set[tuple] = set()
    last_uploaded_at: dict[tuple, datetime] = {}
    for ev in item_events:
        if ev.entity_id is None or not ev.extra_metadata:
            continue
        item_id = ev.extra_metadata.get("item_id")
        if item_id is None:
            continue
        key = (ev.entity_id, item_id)
        if ev.event_type == "document_request.item_waived":
            waived_items.add(key)
        else:
            prev = last_uploaded_at.get(key)
            if prev is None or ev.occurred_at > prev:
                last_uploaded_at[key] = ev.occurred_at

    observations: dict[date, list[float]] = {}
    for (request_id, _item_id), uploaded_at in last_uploaded_at.items():
        if (request_id, _item_id) in waived_items:
            # Waive never extends duration -- the firm had what it needed
            # at the final upload, so a waived item contributes nothing.
            continue
        sent_at = sent_at_by_request.get(request_id)
        if sent_at is None:
            continue
        duration_days = (uploaded_at - sent_at).total_seconds() / 86400
        observations.setdefault(_week_start(uploaded_at), []).append(duration_days)

    first_week = _week_start(min(sent_at_by_request.values())) if sent_at_by_request else None
    return first_week, observations


# ---------------------------------------------------------------------------
# Metric 4 -- invoice_payment_time
# ---------------------------------------------------------------------------

def _build_invoice_payment_time(db: Session, firm_id: uuid.UUID, current_week: date):
    sent_events = _fetch_events(db, firm_id, ["invoice.sent"])
    paid_events = _fetch_events(db, firm_id, ["invoice.paid"])

    sent_at_by_invoice: dict[uuid.UUID, datetime] = {}
    for ev in sent_events:
        if ev.entity_id is None:
            continue
        if ev.entity_id not in sent_at_by_invoice:
            sent_at_by_invoice[ev.entity_id] = ev.occurred_at

    paid_at_by_invoice: dict[uuid.UUID, datetime] = {}
    for ev in paid_events:
        if ev.entity_id is None:
            continue
        prev = paid_at_by_invoice.get(ev.entity_id)
        if prev is None or ev.occurred_at > prev:
            paid_at_by_invoice[ev.entity_id] = ev.occurred_at

    observations: dict[date, list[float]] = {}
    for invoice_id, paid_at in paid_at_by_invoice.items():
        sent_at = sent_at_by_invoice.get(invoice_id)
        if sent_at is None:
            continue
        duration_days = (paid_at - sent_at).total_seconds() / 86400
        observations.setdefault(_week_start(paid_at), []).append(duration_days)

    first_week = _week_start(min(sent_at_by_invoice.values())) if sent_at_by_invoice else None
    return first_week, observations


# ---------------------------------------------------------------------------
# Metric 5a -- portal_utilization_documents
# ---------------------------------------------------------------------------

def _dying_with_engagement_document_items(
    db: Session, firm_id: uuid.UUID, resolved_keys: set[tuple]
) -> list[datetime]:
    completion_events = _fetch_events(db, firm_id, ["engagement.completed", "engagement.archived"])
    latest_resolution_by_engagement: dict[uuid.UUID, datetime] = {}
    for ev in completion_events:
        if ev.entity_id is None:
            continue
        prev = latest_resolution_by_engagement.get(ev.entity_id)
        if prev is None or ev.occurred_at > prev:
            latest_resolution_by_engagement[ev.entity_id] = ev.occurred_at

    if not latest_resolution_by_engagement:
        return []

    stmt = select(DocumentRequest).where(
        DocumentRequest.firm_id == firm_id,
        DocumentRequest.engagement_id.in_(latest_resolution_by_engagement.keys()),
    )
    requests = db.execute(stmt).scalars().all()

    dying_timestamps: list[datetime] = []
    for req in requests:
        resolved_at = latest_resolution_by_engagement.get(req.engagement_id)
        if resolved_at is None:
            continue
        for item in (req.checklist_items or []):
            item_id = item.get("id")
            if item_id is None:
                continue
            key = (req.id, item_id)
            if key not in resolved_keys:
                dying_timestamps.append(resolved_at)

    return dying_timestamps


def _build_portal_utilization_documents(db: Session, firm_id: uuid.UUID, current_week: date):
    item_events = _fetch_events(
        db,
        firm_id,
        ["portal.todo_completed", "document_request.item_uploaded", "document_request.item_waived"],
    )

    portal_resolution: dict[tuple, datetime] = {}
    other_resolution: dict[tuple, datetime] = {}
    for ev in item_events:
        if ev.entity_id is None or not ev.extra_metadata:
            continue
        item_id = ev.extra_metadata.get("item_id")
        if item_id is None:
            continue
        key = (ev.entity_id, item_id)
        if ev.event_type == "portal.todo_completed":
            prev = portal_resolution.get(key)
            if prev is None or ev.occurred_at < prev:
                portal_resolution[key] = ev.occurred_at
        else:
            prev = other_resolution.get(key)
            if prev is None or ev.occurred_at < prev:
                other_resolution[key] = ev.occurred_at

    resolved_keys = set(portal_resolution) | set(other_resolution)

    observations: dict[date, list[float]] = {}
    resolution_timestamps: list[datetime] = []

    for key in resolved_keys:
        if key in portal_resolution:
            value, ts = 100.0, portal_resolution[key]
        else:
            value, ts = 0.0, other_resolution[key]
        observations.setdefault(_week_start(ts), []).append(value)
        resolution_timestamps.append(ts)

    for ts in _dying_with_engagement_document_items(db, firm_id, resolved_keys):
        observations.setdefault(_week_start(ts), []).append(0.0)
        resolution_timestamps.append(ts)

    first_week = _week_start(min(resolution_timestamps)) if resolution_timestamps else None
    return first_week, observations


# ---------------------------------------------------------------------------
# Metric 5b -- portal_utilization_invoices
# ---------------------------------------------------------------------------

def _build_portal_utilization_invoices(db: Session, firm_id: uuid.UUID, current_week: date):
    paid_events = _fetch_events(db, firm_id, ["invoice.paid"])
    portal_events = _fetch_events(db, firm_id, ["portal.invoice_paid"])

    portal_marked: set[uuid.UUID] = {ev.entity_id for ev in portal_events if ev.entity_id is not None}

    latest_paid: dict[uuid.UUID, BehavioralEvent] = {}
    for ev in paid_events:
        if ev.entity_id is None:
            continue
        prev = latest_paid.get(ev.entity_id)
        if prev is None or ev.occurred_at > prev.occurred_at:
            latest_paid[ev.entity_id] = ev

    observations: dict[date, list[float]] = {}
    resolution_timestamps: list[datetime] = []
    for invoice_id, ev in latest_paid.items():
        value = 100.0 if invoice_id in portal_marked else 0.0
        observations.setdefault(_week_start(ev.occurred_at), []).append(value)
        resolution_timestamps.append(ev.occurred_at)

    first_week = _week_start(min(resolution_timestamps)) if resolution_timestamps else None
    return first_week, observations


# ---------------------------------------------------------------------------
# Metric 6 -- automation_utilization (rolling_snapshot)
# ---------------------------------------------------------------------------

def _is_enabled_as_of(toggles: list[tuple[datetime, bool]], as_of: datetime) -> bool:
    # AutomationRule.is_enabled defaults False at row creation, and no
    # automation.created event exists, so the pre-toggle state is exactly
    # False -- not an approximation.
    state = False
    for occurred_at, enabled in toggles:
        if occurred_at > as_of:
            break
        state = enabled
    return state


def _compute_automation_utilization(
    db: Session, metric_row: MetricRegistry, computed_at: datetime, current_week: date
) -> None:
    now = datetime.now(timezone.utc)

    for firm_id, firm_created_at in db.execute(select(Firm.id, Firm.created_at)).all():
        first_week = _week_start(firm_created_at)

        fired_events = _fetch_events(db, firm_id, ["automation.fired"])
        toggle_events = _fetch_events(db, firm_id, ["firm.automation_enabled", "firm.automation_disabled"])

        rule_first_fired_at: dict[uuid.UUID, datetime] = {}
        rules_by_preset: dict[str, list[uuid.UUID]] = {}
        for ev in fired_events:
            if ev.entity_id is None or not ev.extra_metadata:
                continue
            preset_key = ev.extra_metadata.get("preset_key")
            if preset_key is None:
                continue  # pure custom rule, excluded from benchmark metric
            prev = rule_first_fired_at.get(ev.entity_id)
            if prev is None or ev.occurred_at < prev:
                rule_first_fired_at[ev.entity_id] = ev.occurred_at
            rules_by_preset.setdefault(preset_key, [])
            if ev.entity_id not in rules_by_preset[preset_key]:
                rules_by_preset[preset_key].append(ev.entity_id)

        toggles_by_rule: dict[uuid.UUID, list[tuple[datetime, bool]]] = {}
        for ev in toggle_events:
            if ev.entity_id is None:
                continue
            enabled = ev.event_type == "firm.automation_enabled"
            toggles_by_rule.setdefault(ev.entity_id, []).append((ev.occurred_at, enabled))
        for lst in toggles_by_rule.values():
            lst.sort(key=lambda t: t[0])

        week = first_week
        while week <= current_week:
            week_end_ts = min(_week_end(week), now)
            eligible_entries = [e for e in PRESET_CATALOG if e.introduced_at <= week_end_ts.date()]
            denominator = len(eligible_entries)

            if denominator == 0:
                _upsert_metric_value(
                    db, firm_id=firm_id, metric_id=metric_row.id, week_start=week,
                    value=None, sample_size=0, std_dev=None, computed_at=computed_at,
                )
                week += timedelta(days=7)
                continue

            numerator = 0
            for entry in eligible_entries:
                for rule_id in rules_by_preset.get(entry.key, []):
                    fired_at = rule_first_fired_at.get(rule_id)
                    if fired_at is None or fired_at > week_end_ts:
                        continue
                    if _is_enabled_as_of(toggles_by_rule.get(rule_id, []), week_end_ts):
                        numerator += 1
                        break

            value = (numerator / denominator) * 100
            # A rolling snapshot is a single point-in-time ratio of catalog
            # slots, not an average of independent weekly observations --
            # there is no variance concept to report here.
            _upsert_metric_value(
                db, firm_id=firm_id, metric_id=metric_row.id, week_start=week,
                value=value, sample_size=denominator, std_dev=None, computed_at=computed_at,
            )
            week += timedelta(days=7)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_WEEKLY_BUILDERS: dict[str, Callable] = {
    "engagement_velocity": _build_engagement_velocity,
    "deadline_adherence_original": lambda db, firm_id, current_week: _build_deadline_adherence_track(
        db, firm_id, current_week, "original"
    ),
    "deadline_adherence_extended": lambda db, firm_id, current_week: _build_deadline_adherence_track(
        db, firm_id, current_week, "extended"
    ),
    "deadline_adherence_operative": lambda db, firm_id, current_week: _build_deadline_adherence_track(
        db, firm_id, current_week, "operative"
    ),
    "document_collection_speed": _build_document_collection_speed,
    "invoice_payment_time": _build_invoice_payment_time,
    "portal_utilization_documents": _build_portal_utilization_documents,
    "portal_utilization_invoices": _build_portal_utilization_invoices,
}


def _compute_weekly_metric(
    db: Session, metric_row: MetricRegistry, computed_at: datetime, current_week: date
) -> None:
    builder = _WEEKLY_BUILDERS[metric_row.key]
    for (firm_id,) in db.execute(select(Firm.id)).all():
        first_week, observations = builder(db, firm_id, current_week)
        if first_week is None:
            continue
        _write_weekly_series(
            db,
            firm_id=firm_id,
            metric_id=metric_row.id,
            observations=observations,
            first_week=first_week,
            last_week=current_week,
            computed_at=computed_at,
        )


def compute_metric(db: Session, metric_row: MetricRegistry, computed_at: datetime) -> None:
    """Entry point used by the nightly pipeline for one active registry row."""
    current_week = _current_week_start()
    if metric_row.key == "automation_utilization":
        _compute_automation_utilization(db, metric_row, computed_at, current_week)
    elif metric_row.key in _WEEKLY_BUILDERS:
        _compute_weekly_metric(db, metric_row, computed_at, current_week)
    else:
        raise ValueError(f"No compute function registered for metric key {metric_row.key!r}")
