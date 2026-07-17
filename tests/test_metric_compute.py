# tests/test_metric_compute.py

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import BetterDirection, MetricWindowType
from app.core.metric_seed_data import SEED_METRICS
from app.models.behavioral_event import BehavioralEvent
from app.models.firm import Firm
from app.models.metric_registry import MetricRegistry
from app.models.metric_value import MetricValue
from app.services.metric_compute import compute_metric, _week_start, _current_week_start

_SEED_BY_KEY = {row[0]: row for row in SEED_METRICS}


def _make_firm(db, created_at=None) -> Firm:
    firm = Firm(name=f"Test Firm {uuid.uuid4()}", slug=f"test-firm-{uuid.uuid4()}")
    db.add(firm)
    db.commit()
    db.refresh(firm)
    if created_at is not None:
        db.query(Firm).filter(Firm.id == firm.id).update({"created_at": created_at})
        db.commit()
        db.refresh(firm)
    return firm


def _make_metric(db, key: str) -> MetricRegistry:
    _, display_name, unit, better_direction, benchmark_eligible, tier, window_type = _SEED_BY_KEY[key]
    row = MetricRegistry(
        key=key,
        display_name=display_name,
        unit=unit,
        better_direction=BetterDirection(better_direction),
        benchmark_eligible=benchmark_eligible,
        tier=tier,
        window_type=MetricWindowType(window_type),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _event(db, firm_id, event_type, entity_id=None, occurred_at=None, metadata=None):
    ev = BehavioralEvent(
        firm_id=firm_id,
        event_type=event_type,
        entity_type="test",
        entity_id=entity_id,
        actor_type="system",
        actor_id=None,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        extra_metadata=metadata or {},
    )
    db.add(ev)
    db.commit()
    return ev


def _values(db, firm_id, metric_id):
    return (
        db.query(MetricValue)
        .filter(MetricValue.firm_id == firm_id, MetricValue.metric_id == metric_id)
        .order_by(MetricValue.week_start)
        .all()
    )


def _at(y, m, d, hour=12):
    return datetime(y, m, d, hour, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Happy path -- one test per active metric
# ---------------------------------------------------------------------------

def test_engagement_velocity_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "engagement_velocity")
        eng_id = uuid.uuid4()

        _event(db, firm.id, "engagement.created", entity_id=eng_id, occurred_at=_at(2026, 5, 4, 0))
        _event(db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 6, 12))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(_at(2026, 5, 6, 12))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(2.5, abs=0.01)
        assert row.sample_size == 1
        assert row.std_dev is None
    finally:
        db.close()


def test_deadline_adherence_original_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "deadline_adherence_original")
        eng_id = uuid.uuid4()
        deadline = date(2026, 5, 15)

        _event(
            db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 10),
            metadata={"filing_deadline": deadline.isoformat(), "extended_deadline": None},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(datetime.combine(deadline, datetime.min.time(), tzinfo=timezone.utc))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(100.0)
        assert row.sample_size == 1
    finally:
        db.close()


def test_deadline_adherence_extended_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "deadline_adherence_extended")
        eng_id = uuid.uuid4()
        extended = date(2026, 5, 22)

        _event(
            db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 20),
            metadata={"filing_deadline": "2026-05-15", "extended_deadline": extended.isoformat()},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(datetime.combine(extended, datetime.min.time(), tzinfo=timezone.utc))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(100.0)
        assert row.sample_size == 1
    finally:
        db.close()


def test_deadline_adherence_operative_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "deadline_adherence_operative")
        eng_id = uuid.uuid4()
        extended = date(2026, 5, 22)

        # extended_deadline set -- operative track uses it, not the original.
        _event(
            db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 20),
            metadata={"filing_deadline": "2026-05-15", "extended_deadline": extended.isoformat()},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(datetime.combine(extended, datetime.min.time(), tzinfo=timezone.utc))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(100.0)
    finally:
        db.close()


def test_document_collection_speed_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "document_collection_speed")
        req_id = uuid.uuid4()
        item_id = str(uuid.uuid4())

        _event(db, firm.id, "document_request.sent", entity_id=req_id, occurred_at=_at(2026, 5, 4, 0))
        _event(
            db, firm.id, "document_request.item_uploaded", entity_id=req_id,
            occurred_at=_at(2026, 5, 5, 12), metadata={"item_id": item_id},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(_at(2026, 5, 5, 12))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(1.5, abs=0.01)
        assert row.sample_size == 1
    finally:
        db.close()


def test_invoice_payment_time_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "invoice_payment_time")
        inv_id = uuid.uuid4()

        _event(db, firm.id, "invoice.sent", entity_id=inv_id, occurred_at=_at(2026, 5, 4, 0))
        _event(db, firm.id, "invoice.paid", entity_id=inv_id, occurred_at=_at(2026, 5, 10, 12))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(_at(2026, 5, 10, 12))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(6.5, abs=0.01)
        assert row.sample_size == 1
    finally:
        db.close()


def test_portal_utilization_documents_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "portal_utilization_documents")
        req_id = uuid.uuid4()
        portal_item = str(uuid.uuid4())
        staff_item = str(uuid.uuid4())

        _event(
            db, firm.id, "portal.todo_completed", entity_id=req_id,
            occurred_at=_at(2026, 5, 5), metadata={"item_id": portal_item},
        )
        _event(
            db, firm.id, "document_request.item_uploaded", entity_id=req_id,
            occurred_at=_at(2026, 5, 6), metadata={"item_id": staff_item},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(_at(2026, 5, 5))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(50.0)
        assert row.sample_size == 2
    finally:
        db.close()


def test_portal_utilization_invoices_happy_path():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "portal_utilization_invoices")
        portal_inv = uuid.uuid4()
        staff_inv = uuid.uuid4()

        _event(db, firm.id, "portal.invoice_paid", entity_id=portal_inv, occurred_at=_at(2026, 5, 4))
        _event(db, firm.id, "invoice.paid", entity_id=portal_inv, occurred_at=_at(2026, 5, 5))
        _event(db, firm.id, "invoice.paid", entity_id=staff_inv, occurred_at=_at(2026, 5, 5))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(_at(2026, 5, 5))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(50.0)
        assert row.sample_size == 2
    finally:
        db.close()


def test_automation_utilization_happy_path_and_versioned_denominator():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 18))  # Monday
        metric = _make_metric(db, "automation_utilization")

        fired_rule = uuid.uuid4()
        never_fired_rule = uuid.uuid4()
        custom_rule = uuid.uuid4()

        # R1: enabled, fired -- a customized preset-derived rule still counts.
        _event(db, firm.id, "firm.automation_enabled", entity_id=fired_rule, occurred_at=_at(2026, 5, 19))
        _event(
            db, firm.id, "automation.fired", entity_id=fired_rule, occurred_at=_at(2026, 5, 20),
            metadata={"preset_key": "doc_request_reminder_3day", "is_customized": True},
        )

        # R2: enabled but never fired -- excluded from numerator.
        _event(db, firm.id, "firm.automation_enabled", entity_id=never_fired_rule, occurred_at=_at(2026, 5, 19))

        # R3: pure custom rule, fired, but preset_key is null -- excluded entirely.
        _event(db, firm.id, "firm.automation_enabled", entity_id=custom_rule, occurred_at=_at(2026, 5, 19))
        _event(
            db, firm.id, "automation.fired", entity_id=custom_rule, occurred_at=_at(2026, 5, 20),
            metadata={"preset_key": None},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = {r.week_start: r for r in _values(db, firm.id, metric.id)}

        pre_batch_week = _week_start(_at(2026, 5, 25))  # before budget_variance_alert (2026-06-05)
        post_batch_week = _week_start(_at(2026, 6, 8))  # after morning_briefing (2026-06-06)

        assert rows[pre_batch_week].sample_size == 15
        assert float(rows[pre_batch_week].value) == pytest.approx(1 / 15 * 100, abs=0.01)

        assert rows[post_batch_week].sample_size == 17
        assert float(rows[post_batch_week].value) == pytest.approx(1 / 17 * 100, abs=0.01)

        assert rows[pre_batch_week].std_dev is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Deadline adherence -- hit/miss mechanics
# ---------------------------------------------------------------------------

def test_deadline_hit_and_miss_same_week_produce_correct_percentage():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "deadline_adherence_original")
        deadline = date(2026, 5, 15)

        hit_eng = uuid.uuid4()
        miss_eng = uuid.uuid4()

        _event(
            db, firm.id, "engagement.completed", entity_id=hit_eng, occurred_at=_at(2026, 5, 10),
            metadata={"filing_deadline": deadline.isoformat(), "extended_deadline": None},
        )
        _event(
            db, firm.id, "engagement.deadline_missed", entity_id=miss_eng, occurred_at=_at(2026, 5, 16),
            metadata={"deadline_type": "original", "deadline_date": deadline.isoformat()},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(datetime.combine(deadline, datetime.min.time(), tzinfo=timezone.utc))
        row = next(r for r in rows if r.week_start == target_week)
        assert float(row.value) == pytest.approx(50.0)
        assert row.sample_size == 2
    finally:
        db.close()


def test_deadline_miss_attribution_is_deadline_week_even_when_completion_is_later():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "deadline_adherence_original")
        eng_id = uuid.uuid4()
        deadline = date(2026, 5, 15)

        # Deadline passes without completion -- sweep records the miss.
        _event(
            db, firm.id, "engagement.deadline_missed", entity_id=eng_id, occurred_at=_at(2026, 5, 16),
            metadata={"deadline_type": "original", "deadline_date": deadline.isoformat()},
        )
        # Engagement completes two weeks later. The miss must not be deferred
        # to the completion week -- it stays pinned to the deadline week.
        _event(
            db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 29),
            metadata={"filing_deadline": deadline.isoformat(), "extended_deadline": None},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        deadline_week = _week_start(datetime.combine(deadline, datetime.min.time(), tzinfo=timezone.utc))
        completion_week = _week_start(_at(2026, 5, 29))
        assert deadline_week != completion_week

        row = next(r for r in rows if r.week_start == deadline_week)
        assert float(row.value) == pytest.approx(0.0)
        assert row.sample_size == 1

        completion_row = next((r for r in rows if r.week_start == completion_week), None)
        assert completion_row is None or completion_row.sample_size == 0
    finally:
        db.close()


def test_future_deadline_week_not_written_yet():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "deadline_adherence_original")
        near_term_eng = uuid.uuid4()
        future_eng = uuid.uuid4()

        current_week = _current_week_start()
        future_deadline = current_week + timedelta(days=365)

        # A normal, already-resolved deadline so first_week gets established
        # and rows actually get written.
        _event(
            db, firm.id, "engagement.completed", entity_id=near_term_eng, occurred_at=_at(2026, 5, 10),
            metadata={"filing_deadline": "2026-05-15", "extended_deadline": None},
        )
        # Completed well before a deadline that is over a year in the future.
        _event(
            db, firm.id, "engagement.completed", entity_id=future_eng, occurred_at=_at(2026, 5, 10),
            metadata={"filing_deadline": future_deadline.isoformat(), "extended_deadline": None},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        assert len(rows) > 0
        assert all(r.week_start != future_deadline for r in rows)
        assert all(r.week_start <= current_week for r in rows)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Document collection speed -- edge cases
# ---------------------------------------------------------------------------

def test_waived_item_does_not_extend_duration():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "document_collection_speed")
        req_id = uuid.uuid4()
        uploaded_item = str(uuid.uuid4())
        waived_item = str(uuid.uuid4())

        _event(db, firm.id, "document_request.sent", entity_id=req_id, occurred_at=_at(2026, 5, 4))
        _event(
            db, firm.id, "document_request.item_uploaded", entity_id=req_id,
            occurred_at=_at(2026, 5, 5), metadata={"item_id": uploaded_item},
        )
        _event(
            db, firm.id, "document_request.item_waived", entity_id=req_id,
            occurred_at=_at(2026, 6, 1), metadata={"item_id": waived_item},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(_at(2026, 5, 5))
        row = next(r for r in rows if r.week_start == target_week)
        assert row.sample_size == 1
        assert float(row.value) == pytest.approx(1.0, abs=0.01)
    finally:
        db.close()


def test_rejected_then_reuploaded_counts_at_final_upload():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "document_collection_speed")
        req_id = uuid.uuid4()
        item_id = str(uuid.uuid4())

        _event(db, firm.id, "document_request.sent", entity_id=req_id, occurred_at=_at(2026, 5, 1))
        _event(
            db, firm.id, "document_request.item_uploaded", entity_id=req_id,
            occurred_at=_at(2026, 5, 2), metadata={"item_id": item_id},
        )
        _event(
            db, firm.id, "document_request.item_rejected", entity_id=req_id,
            occurred_at=_at(2026, 5, 3), metadata={"item_id": item_id},
        )
        _event(
            db, firm.id, "document_request.item_uploaded", entity_id=req_id,
            occurred_at=_at(2026, 5, 8), metadata={"item_id": item_id},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        final_week = _week_start(_at(2026, 5, 8))
        row = next(r for r in rows if r.week_start == final_week)
        assert row.sample_size == 1
        assert float(row.value) == pytest.approx(7.0, abs=0.01)
    finally:
        db.close()


def test_all_waived_request_contributes_no_duration_observation():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "document_collection_speed")
        req_id = uuid.uuid4()
        item_id = str(uuid.uuid4())

        _event(db, firm.id, "document_request.sent", entity_id=req_id, occurred_at=_at(2026, 5, 4))
        _event(
            db, firm.id, "document_request.item_waived", entity_id=req_id,
            occurred_at=_at(2026, 5, 6), metadata={"item_id": item_id},
        )

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        assert len(rows) > 0
        assert all(r.sample_size == 0 and r.value is None for r in rows)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Invoice payment time -- partial payment / clock stop
# ---------------------------------------------------------------------------

def test_partial_payment_does_not_stop_clock_zero_balance_does():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "invoice_payment_time")
        inv_id = uuid.uuid4()

        _event(db, firm.id, "invoice.sent", entity_id=inv_id, occurred_at=_at(2026, 5, 1))
        _event(
            db, firm.id, "invoice.partial_payment", entity_id=inv_id, occurred_at=_at(2026, 5, 3),
            metadata={"amount_paid": "50.00", "remaining_balance": "50.00"},
        )
        _event(db, firm.id, "invoice.paid", entity_id=inv_id, occurred_at=_at(2026, 5, 11))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        target_week = _week_start(_at(2026, 5, 11))
        row = next(r for r in rows if r.week_start == target_week)
        assert row.sample_size == 1
        assert float(row.value) == pytest.approx(10.0, abs=0.01)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Engagement velocity -- reopen extends to final completion
# ---------------------------------------------------------------------------

def test_reopened_engagement_extends_to_final_completion():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "engagement_velocity")
        eng_id = uuid.uuid4()

        _event(db, firm.id, "engagement.created", entity_id=eng_id, occurred_at=_at(2026, 5, 1))
        _event(db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 5))
        _event(db, firm.id, "engagement.reopened", entity_id=eng_id, occurred_at=_at(2026, 5, 6))
        _event(db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 15))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        final_week = _week_start(_at(2026, 5, 15))
        early_week = _week_start(_at(2026, 5, 5))

        row = next(r for r in rows if r.week_start == final_week)
        assert float(row.value) == pytest.approx(14.0, abs=0.01)

        if early_week != final_week:
            early_row = next((r for r in rows if r.week_start == early_week), None)
            assert early_row is None or early_row.sample_size == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Zero-sample weeks and upsert
# ---------------------------------------------------------------------------

def test_zero_sample_week_written_explicitly():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "engagement_velocity")
        eng_id = uuid.uuid4()

        # Created but never completed -- no observation ever, but the week
        # range must still be backfilled with explicit zero-sample rows.
        _event(db, firm.id, "engagement.created", entity_id=eng_id, occurred_at=_at(2026, 5, 4))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = _values(db, firm.id, metric.id)
        assert len(rows) > 1
        assert all(r.sample_size == 0 and r.value is None and r.std_dev is None for r in rows)
    finally:
        db.close()


def test_upsert_running_twice_produces_no_duplicates():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "engagement_velocity")
        eng_id = uuid.uuid4()

        _event(db, firm.id, "engagement.created", entity_id=eng_id, occurred_at=_at(2026, 5, 4))
        _event(db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 6))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()
        first_count = len(_values(db, firm.id, metric.id))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()
        second_count = len(_values(db, firm.id, metric.id))

        assert first_count == second_count
        assert first_count > 0
    finally:
        db.close()
