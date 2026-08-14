# tests/test_stage_transitions.py

"""
Tests for stage-transition behavior in transition_lead_stage().

TRANSITION RULES (per Andrew's ruling):
  Won is terminal. No transition off won is allowed. The won transition
  already created a real Client and flowed attribution forward; reversing
  the stage does not undo that. A dedicated un-convert action is the
  correct path and is not built here.

  Lost is reopenable as a deliberate action. Any forward move off lost
  clears lost_reason and fires a lead.reopened event carrying the prior
  lost_reason, so the intelligence layer sees revival as data, not a
  silent edit.

  Identified through proposal: freely bidirectional, unchanged.
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
# Enforced transition rules per Andrew's ruling
# ---------------------------------------------------------------------------

class TestEnforcedTransitionRules:
    def test_won_stage_refuses_all_transitions(self):
        """Won is terminal: any transition attempt off won raises ValueError.

        Per Andrew's ruling: the won transition already created a real Client
        and flowed attribution forward. Reversing the stage does not undo that
        and would leave a lead that lies about its own history. A real
        un-convert is a separate, future action.

        This is the GUARD TEST for this task. Red/green cycle:
          Break: comment out the 'if lead.stage == LeadStage.won.value' check
                 in transition_lead_stage.
          Run:   this test -- expect RED (ValueError not raised, stage changes).
          Restore: un-comment the check.
          Rerun: confirm GREEN.
        """
        firm = _make_firm("won-terminal-firm")
        lead = _make_lead(firm.id, LeadStage.proposal)

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            won_lead = transition_lead_stage(db, fresh_lead, LeadStage.won)
            assert won_lead.stage == LeadStage.won.value
            assert won_lead.converted_client_id is not None

            fresh_won_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            with pytest.raises(ValueError, match="terminal"):
                transition_lead_stage(db, fresh_won_lead, LeadStage.contacted)

            unchanged = db.query(Lead).filter(Lead.id == lead.id).first()
            assert unchanged.stage == LeadStage.won.value, (
                f"Stage was changed despite ValueError. Got {unchanged.stage!r}"
            )
        finally:
            db.close()

    def test_lost_stage_reopen_clears_reason_and_fires_revival_event(self):
        """Reopening a lost lead: clears lost_reason, advances stage, fires lead.reopened.

        Per Andrew's ruling: lost is reopenable as a deliberate action, not a
        silent edit. The event carries the prior lost_reason so the intelligence
        layer sees revival as real data, not an ordinary stage change.
        """
        from app.models.behavioral_event import BehavioralEvent

        firm = _make_firm("lost-reopen-firm")
        lead = _make_lead(firm.id, LeadStage.proposal)

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            lost_lead = transition_lead_stage(
                db, fresh_lead, LeadStage.lost,
                lost_reason=LeadLostReason.timing,
            )
            assert lost_lead.stage == LeadStage.lost.value
            assert lost_lead.lost_reason == LeadLostReason.timing.value

            fresh_lost_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            result = transition_lead_stage(db, fresh_lost_lead, LeadStage.call_booked)

            assert result.stage == LeadStage.call_booked.value, (
                f"Expected call_booked after reopen, got {result.stage!r}"
            )
            assert result.lost_reason is None, (
                f"lost_reason must be cleared on reopen, got {result.lost_reason!r}"
            )

            event = db.query(BehavioralEvent).filter(
                BehavioralEvent.firm_id == firm.id,
                BehavioralEvent.event_type == "lead.reopened",
            ).first()
            assert event is not None, "lead.reopened event was not fired"
            assert event.extra_metadata["new_stage"] == LeadStage.call_booked.value, (
                f"Revival event new_stage wrong: {event.extra_metadata!r}"
            )
            assert event.extra_metadata["prior_lost_reason"] == LeadLostReason.timing.value, (
                f"Revival event prior_lost_reason wrong: {event.extra_metadata!r}"
            )
        finally:
            db.close()
