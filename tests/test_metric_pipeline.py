# tests/test_metric_pipeline.py

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.core.enums import BetterDirection, MetricRunStatus, MetricWindowType
from app.core.metric_seed_data import SEED_METRICS
from app.models.behavioral_event import BehavioralEvent
from app.models.firm import Firm
from app.models.metric_registry import MetricRegistry
from app.models.metric_run_log import MetricRunLog
from app.models.metric_value import MetricValue
from app.services.metric_compute import compute_metric as real_compute_metric
from app.services.metric_pipeline import run_nightly_metric_recompute

_SEED_BY_KEY = {row[0]: row for row in SEED_METRICS}


def _make_firm(db, created_at) -> Firm:
    firm = Firm(name=f"Test Firm {uuid.uuid4()}", slug=f"test-firm-{uuid.uuid4()}")
    db.add(firm)
    db.commit()
    db.refresh(firm)
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


def test_one_metric_failure_produces_partial_status_and_writes_the_rest():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, datetime(2026, 5, 1, tzinfo=timezone.utc))
        ok_metric_id = _make_metric(db, "engagement_velocity").id
        broken_metric_id = _make_metric(db, "invoice_payment_time").id

        eng_id = uuid.uuid4()
        _event(db, firm.id, "engagement.created", entity_id=eng_id, occurred_at=datetime(2026, 5, 4, tzinfo=timezone.utc))
        _event(db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=datetime(2026, 5, 6, tzinfo=timezone.utc))
    finally:
        db.close()

    def _flaky_compute_metric(db, metric_row, computed_at):
        if metric_row.key == "invoice_payment_time":
            raise RuntimeError("simulated failure")
        return real_compute_metric(db, metric_row, computed_at)

    with patch("app.services.metric_pipeline.SessionLocal", TestingSessionLocal), \
         patch("app.services.metric_pipeline.compute_metric", side_effect=_flaky_compute_metric):
        result = run_nightly_metric_recompute()

    assert result["status"] == MetricRunStatus.partial.value
    assert "invoice_payment_time" in result["error_summary"]
    assert "RuntimeError" in result["error_summary"]
    assert "simulated failure" in result["error_summary"]
    assert result["succeeded"] == 1
    assert result["total"] == 2

    db = TestingSessionLocal()
    try:
        run_log = db.query(MetricRunLog).order_by(MetricRunLog.started_at.desc()).first()
        assert run_log is not None
        assert run_log.status == MetricRunStatus.partial
        assert run_log.finished_at is not None
        assert "invoice_payment_time" in run_log.error_summary

        ok_values = db.query(MetricValue).filter(MetricValue.metric_id == ok_metric_id).all()
        broken_values = db.query(MetricValue).filter(MetricValue.metric_id == broken_metric_id).all()
        assert len(ok_values) > 0
        assert len(broken_values) == 0
    finally:
        db.close()


def test_all_metrics_succeed_produces_succeeded_status():
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db, datetime(2026, 5, 1, tzinfo=timezone.utc))
        metric = _make_metric(db, "engagement_velocity")
        eng_id = uuid.uuid4()
        _event(db, firm.id, "engagement.created", entity_id=eng_id, occurred_at=datetime(2026, 5, 4, tzinfo=timezone.utc))
        _event(db, firm.id, "engagement.completed", entity_id=eng_id, occurred_at=datetime(2026, 5, 6, tzinfo=timezone.utc))
    finally:
        db.close()

    with patch("app.services.metric_pipeline.SessionLocal", TestingSessionLocal):
        result = run_nightly_metric_recompute()

    assert result["status"] == MetricRunStatus.succeeded.value
    assert result["error_summary"] is None
    assert result["succeeded"] == result["total"] == 1


def test_all_metrics_fail_produces_failed_status():
    db = TestingSessionLocal()
    try:
        _make_metric(db, "engagement_velocity")
        _make_metric(db, "invoice_payment_time")
    finally:
        db.close()

    def _always_fails(db, metric_row, computed_at):
        raise RuntimeError("boom")

    with patch("app.services.metric_pipeline.SessionLocal", TestingSessionLocal), \
         patch("app.services.metric_pipeline.compute_metric", side_effect=_always_fails):
        result = run_nightly_metric_recompute()

    assert result["status"] == MetricRunStatus.failed.value
    assert result["succeeded"] == 0
    assert result["total"] == 2
    assert "boom" in result["error_summary"]
