# tests/test_behavioral_log.py

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.conftest import TestingSessionLocal
from app.models.behavioral_event import BehavioralEvent
from app.models.firm import Firm
from app.services.behavioral_log import log_event


def _make_firm() -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Test Firm {uuid.uuid4()}", slug=f"test-firm-{uuid.uuid4()}")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1 — log_event() writes a row with correct field values
# ---------------------------------------------------------------------------
def test_log_event_writes_to_db():
    firm_id = _make_firm()
    actor_id = uuid.uuid4()
    entity_id = uuid.uuid4()

    with patch("app.services.behavioral_log.SessionLocal", TestingSessionLocal):
        log_event(
            event_type="engagement.created",
            firm_id=firm_id,
            entity_type="engagement",
            entity_id=entity_id,
            actor_type="staff",
            actor_id=actor_id,
        )

    db = TestingSessionLocal()
    try:
        row = db.query(BehavioralEvent).filter(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "engagement.created",
        ).first()

        assert row is not None
        assert row.entity_type == "engagement"
        assert row.entity_id == entity_id
        assert row.actor_type == "staff"
        assert row.actor_id == actor_id
        assert row.occurred_at is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 2 — log_event() swallows all exceptions silently
# ---------------------------------------------------------------------------
def test_log_event_silently_swallows_errors():
    with patch("app.services.behavioral_log.SessionLocal", side_effect=Exception("db unavailable")):
        try:
            log_event(
                event_type="portal.login",
                firm_id=uuid.uuid4(),
            )
        except Exception as exc:
            pytest.fail(f"log_event raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Test 3 — composite index exists in pg_indexes
# ---------------------------------------------------------------------------
def test_log_event_composite_index_exists():
    db = TestingSessionLocal()
    try:
        result = db.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'behavioral_events' "
                "AND indexname = 'ix_behavioral_events_firm_type_time'"
            )
        ).fetchone()
        assert result is not None, "ix_behavioral_events_firm_type_time index not found"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 4 — metadata round-trips correctly through JSONB
# ---------------------------------------------------------------------------
def test_log_event_metadata_stored():
    firm_id = _make_firm()
    nested_metadata = {
        "amount": 1500.00,
        "tags": ["urgent", "q1"],
        "nested": {"count": 3, "flag": True},
    }

    with patch("app.services.behavioral_log.SessionLocal", TestingSessionLocal):
        log_event(
            event_type="invoice.paid",
            firm_id=firm_id,
            metadata=nested_metadata,
        )

    db = TestingSessionLocal()
    try:
        row = db.query(BehavioralEvent).filter(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "invoice.paid",
        ).first()

        assert row is not None
        assert row.extra_metadata == nested_metadata
        assert row.extra_metadata["nested"]["count"] == 3
    finally:
        db.close()
