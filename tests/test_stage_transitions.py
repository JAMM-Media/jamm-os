# tests/test_stage_transitions.py

"""
Tests for stage-transition behavior in transition_lead_stage().
These tests document REAL CURRENT behavior, including where that behavior
is more permissive than the contract may intend.

KNOWN GAP
---------
transition_lead_stage does not validate that a requested stage transition
is a legitimate forward move, and does not reject transitions away from a
terminal state (won or lost). The function has exactly two special cases:
  - won: triggers Client creation
  - lost: requires a lost_reason
Everything else -- including backward moves and moves off terminal states --
falls into the bare else branch and applies without any validation.

This should be raised with Andrew as a real product decision:
  - Should terminal states (won, lost) be locked against further transitions?
  - Should backward moves require an explicit reason (like lost_reason does)?
  - Or is this intentional flexibility -- e.g. marking a lead as re-engaged
    after being lost?

Until that decision is made, these tests record the current permissive
behavior as fact so that any future enforcement change breaks them visibly
rather than silently.
"""

import uuid
import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.client import Client as ClientModel
from app.crud.lead import transition_lead_stage
from app.core.enums import LeadProvenance, LeadStage, LeadLostReason


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Stage Transition Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.name, firm.slug
        return firm
    finally:
        db.close()


def _make_lead(firm_id, stage: LeadStage = LeadStage.identified, **kwargs) -> Lead:
    """Create a Lead directly in the test DB at the given stage."""
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Stage Test Prospect",
            email=f"stage-{uuid.uuid4()}@example.com",
            provenance=LeadProvenance.firm_entered.value,
            stage=stage.value,
            **kwargs,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.firm_id, lead.stage, lead.lost_reason, lead.converted_client_id
        return lead
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Intentional behavior (contract-confirmed)
# ---------------------------------------------------------------------------

class TestIntentionalTransitions:
    def test_forward_skip_is_allowed(self):
        """A lead at identified can jump directly to proposal, skipping intermediate stages.

        Per the contract's LeadStage docstring: 'ordered but skippable -- a
        walk-in ready to sign can jump straight to proposal.' This is intentional
        design, not a gap.
        """
        firm = _make_firm("skip-firm")
        lead = _make_lead(firm.id, LeadStage.identified)

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            assert fresh_lead.stage == LeadStage.identified.value

            result = transition_lead_stage(db, fresh_lead, LeadStage.proposal)

            assert result.stage == LeadStage.proposal.value, (
                f"Forward skip should be allowed. Got {result.stage!r}"
            )
        finally:
            db.close()

    def test_lost_without_lost_reason_raises_value_error(self):
        """Transitioning to lost with no lost_reason raises ValueError (caught as 400 at API layer)."""
        firm = _make_firm("lost-no-reason-firm")
        lead = _make_lead(firm.id, LeadStage.proposal)

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            with pytest.raises(ValueError, match="lost_reason is required"):
                transition_lead_stage(db, fresh_lead, LeadStage.lost)
        finally:
            db.close()

    def test_lost_with_lost_reason_sets_both_fields(self):
        """Transitioning to lost with a reason sets stage=lost and lost_reason correctly."""
        firm = _make_firm("lost-with-reason-firm")
        lead = _make_lead(firm.id, LeadStage.proposal)

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            result = transition_lead_stage(
                db, fresh_lead, LeadStage.lost,
                lost_reason=LeadLostReason.price,
            )
            assert result.stage == LeadStage.lost.value
            assert result.lost_reason == LeadLostReason.price.value, (
                f"lost_reason should be 'price'. Got {result.lost_reason!r}"
            )
        finally:
            db.close()

    def test_won_creates_client_and_sets_converted_client_id(self):
        """Transitioning to won creates a real Client row and sets converted_client_id.

        This is the automated version of the manual psql verification
        performed live earlier tonight.
        """
        firm = _make_firm("won-firm")
        lead = _make_lead(firm.id, LeadStage.proposal)

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            result = transition_lead_stage(db, fresh_lead, LeadStage.won)

            assert result.stage == LeadStage.won.value
            assert result.converted_client_id is not None, (
                "converted_client_id must be set after won transition"
            )

            client = db.query(ClientModel).filter(
                ClientModel.id == result.converted_client_id
            ).first()
            assert client is not None, "Client row not found after won transition"
            assert client.firm_id == firm.id
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Gap probes -- document real permissive behavior, do NOT assert false safety
# ---------------------------------------------------------------------------

class TestKnownTransitionGaps:
    def test_transition_from_won_backward_is_currently_unblocked(self):
        """GAP: a lead already at won can be transitioned backward with no error.

        The current code's else branch applies any non-won/non-lost stage
        with zero current-state validation. This test asserts the REAL
        permissive behavior -- that the backward transition succeeds -- so
        this gap is on record and any future enforcement change breaks this
        test visibly rather than silently.

        The resulting state is inconsistent: stage='contacted' but
        converted_client_id is still pointing to the Client that was
        created during the won transition. This inconsistency is not caught
        by the current code.
        """
        firm = _make_firm("won-backward-firm")
        lead = _make_lead(firm.id, LeadStage.proposal)

        db = TestingSessionLocal()
        try:
            # First, transition to won.
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            won_lead = transition_lead_stage(db, fresh_lead, LeadStage.won)
            assert won_lead.stage == LeadStage.won.value
            assert won_lead.converted_client_id is not None

            # Now attempt backward transition -- currently unblocked.
            # Re-fetch since the session may have expired objects after commit.
            fresh_won_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            result = transition_lead_stage(db, fresh_won_lead, LeadStage.contacted)

            # GAP: this succeeds when arguably it should be rejected.
            assert result.stage == LeadStage.contacted.value, (
                "GAP CONFIRMED: backward transition from won to contacted succeeded "
                f"(no error raised). Stage is now {result.stage!r}."
            )
        finally:
            db.close()

    def test_transition_from_lost_forward_is_currently_unblocked(self):
        """GAP: a lead already at lost can be transitioned forward with no error.

        Same gap as above -- the else branch applies non-won/non-lost stages
        without validating the current state. This means a lost lead can be
        re-staged as call_booked with no explicit re-engagement mechanism.

        Test asserts the REAL permissive behavior so the gap is documented
        and visible. Whether this is a bug or intentional flexibility (e.g.
        recovering a previously lost lead) is a product decision for Andrew.
        """
        firm = _make_firm("lost-forward-firm")
        lead = _make_lead(firm.id, LeadStage.proposal)

        db = TestingSessionLocal()
        try:
            # First, transition to lost.
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            lost_lead = transition_lead_stage(
                db, fresh_lead, LeadStage.lost,
                lost_reason=LeadLostReason.timing,
            )
            assert lost_lead.stage == LeadStage.lost.value

            # Now attempt forward transition -- currently unblocked.
            fresh_lost_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            result = transition_lead_stage(db, fresh_lost_lead, LeadStage.call_booked)

            # GAP: this succeeds when arguably it should require an explicit re-engagement reason.
            assert result.stage == LeadStage.call_booked.value, (
                "GAP CONFIRMED: transition from lost to call_booked succeeded "
                f"(no error raised). Stage is now {result.stage!r}."
            )
        finally:
            db.close()
