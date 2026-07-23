# tests/test_demo_firm_isolation.py

import uuid
from datetime import datetime, timezone

from tests.conftest import TestingSessionLocal
from app.core.enums import BetterDirection, MetricWindowType
from app.core.metric_seed_data import SEED_METRICS
from app.models.firm import Firm
from app.models.metric_registry import MetricRegistry
from app.models.metric_value import MetricValue
from app.models.behavioral_event import BehavioralEvent
from app.services.metric_compute import compute_metric, _cross_firm_aggregation_firm_ids

_SEED_BY_KEY = {row[0]: row for row in SEED_METRICS}


def _make_firm(db, is_demo=False, created_at=None) -> Firm:
    firm = Firm(
        name=f"Test Firm {uuid.uuid4()}",
        slug=f"test-firm-{uuid.uuid4()}",
        is_demo=is_demo,
    )
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


def _at(y, m, d, hour=12):
    return datetime(y, m, d, hour, 0, 0, tzinfo=timezone.utc)


def test_demo_firm_excluded_from_cross_firm_selection():
    """Test A: a firm with is_demo=True never enters any cross-firm
    aggregate or firm-selection path intended for multi-firm computation."""
    db = TestingSessionLocal()
    try:
        demo_firm = _make_firm(db, is_demo=True)
        real_firm = _make_firm(db, is_demo=False)

        selected_ids = _cross_firm_aggregation_firm_ids(db)

        assert demo_firm.id not in selected_ids
        assert real_firm.id in selected_ids
    finally:
        db.close()


def test_demo_firm_still_gets_its_own_firm_scoped_metric_values():
    """Test B: a firm with is_demo=True still gets its own firm-scoped
    MetricValue rows computed by the pipeline."""
    db = TestingSessionLocal()
    try:
        demo_firm = _make_firm(db, is_demo=True, created_at=_at(2026, 5, 1))
        metric = _make_metric(db, "engagement_velocity")
        eng_id = uuid.uuid4()

        _event(db, demo_firm.id, "engagement.created", entity_id=eng_id, occurred_at=_at(2026, 5, 4, 0))
        _event(db, demo_firm.id, "engagement.completed", entity_id=eng_id, occurred_at=_at(2026, 5, 6, 12))

        compute_metric(db, metric, datetime.now(timezone.utc))
        db.commit()

        rows = (
            db.query(MetricValue)
            .filter(MetricValue.firm_id == demo_firm.id, MetricValue.metric_id == metric.id)
            .all()
        )
        assert len(rows) > 0
        assert any(r.sample_size > 0 for r in rows)
    finally:
        db.close()
