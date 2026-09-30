# tests/test_invoice_payment_time_source.py

"""
Invoice Payment Time computes from invoice.paid only.

Ruled Sep 22, 2026, alongside the portal.invoice_paid to
portal.payment_initiated rename. The portal event fires when a client starts a
Stripe payment, at payment intent creation. Money may arrive days later, may
arrive by another route, or may never arrive at all, so counting it as the
moment of payment would make the metric measure intent rather than settlement.
invoice.paid, written from the Stripe webhook, is the payment.

These tests call _build_invoice_payment_time directly rather than going through
compute_metric, because the thing being pinned is which events the builder
draws its observations from, and the builder's return value is exactly that,
before any registry row or week rollup can blur it.
"""

import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.models.behavioral_event import BehavioralEvent
from app.models.firm import Firm
from app.services.metric_compute import _build_invoice_payment_time, _week_start


def _make_firm(db) -> Firm:
    firm = Firm(name=f"Payment Time Firm {uuid.uuid4()}", slug=f"payment-time-{uuid.uuid4()}")
    db.add(firm)
    db.commit()
    db.refresh(firm)
    return firm


def _event(db, firm_id, event_type, entity_id, occurred_at) -> BehavioralEvent:
    ev = BehavioralEvent(
        firm_id=firm_id,
        event_type=event_type,
        entity_type="invoice",
        entity_id=entity_id,
        actor_type="system",
        actor_id=None,
        occurred_at=occurred_at,
        extra_metadata={},
    )
    db.add(ev)
    db.commit()
    return ev


def _at(y, m, d, hour=12):
    return datetime(y, m, d, hour, 0, 0, tzinfo=timezone.utc)


def _observation_count(observations) -> int:
    return sum(len(values) for values in observations.values())


def test_started_payment_without_invoice_paid_produces_no_observation():
    """A client who opened the Stripe payment sheet and never completed it has
    an invoice that is still unpaid. The metric must have nothing to say about
    it, not a duration of zero."""
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        invoice_id = uuid.uuid4()

        _event(db, firm.id, "invoice.sent", invoice_id, _at(2026, 5, 4))
        _event(db, firm.id, "portal.payment_initiated", invoice_id, _at(2026, 5, 5))

        first_week, observations = _build_invoice_payment_time(
            db, firm.id, _week_start(_at(2026, 5, 7))
        )

        assert _observation_count(observations) == 0
        assert observations == {}
        # The invoice was sent, so the metric's history still starts that week.
        assert first_week == _week_start(_at(2026, 5, 4))
    finally:
        db.close()


def test_invoice_paid_produces_exactly_one_observation_with_the_duration():
    """The same invoice, now settled by the webhook three days after it was
    sent. The duration is sent to paid, and the portal event between them
    contributes nothing to it."""
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        invoice_id = uuid.uuid4()

        _event(db, firm.id, "invoice.sent", invoice_id, _at(2026, 5, 4))
        _event(db, firm.id, "portal.payment_initiated", invoice_id, _at(2026, 5, 5))
        _event(db, firm.id, "invoice.paid", invoice_id, _at(2026, 5, 7))

        first_week, observations = _build_invoice_payment_time(
            db, firm.id, _week_start(_at(2026, 5, 7))
        )

        assert _observation_count(observations) == 1
        paid_week = _week_start(_at(2026, 5, 7))
        assert list(observations) == [paid_week]
        assert observations[paid_week][0] == pytest.approx(3.0, abs=1e-6)
        assert first_week == _week_start(_at(2026, 5, 4))
    finally:
        db.close()


def test_the_duration_is_measured_from_invoice_paid_not_from_the_portal_event():
    """The sharpest form of the rule. If the builder ever read the portal event
    as the moment of payment, this duration would be one day rather than three,
    and the test above would still pass on its count."""
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        invoice_id = uuid.uuid4()

        _event(db, firm.id, "invoice.sent", invoice_id, _at(2026, 5, 4))
        _event(db, firm.id, "portal.payment_initiated", invoice_id, _at(2026, 5, 5))
        _event(db, firm.id, "invoice.paid", invoice_id, _at(2026, 5, 7))

        _, observations = _build_invoice_payment_time(db, firm.id, _week_start(_at(2026, 5, 7)))

        durations = [value for values in observations.values() for value in values]
        assert durations == pytest.approx([3.0], abs=1e-6)
    finally:
        db.close()
