# tests/test_attribution_rules.py

"""
Attribution rules codified as law, per Andrew's Step 3 instruction.

These tests are the automated, repeatable form of the manual curl/psql
verification performed live earlier. They do not test ordinary behavior --
they test locked product decisions that must never silently regress.

Covered:
  1. Higher tier blocks lower tier overwrite of a non-null field (the guard test)
  2. Lower tier fills a null field (the other half of the substitution rule)
  3. Equal tier allows normal update (proves the rule is not accidentally too broad)
  4. UTM-derived source_platform is protected from firm_entered override by general
     tier mechanism (see docstring for important caveat about per-field vs general)
  5. Attribution flows forward unchanged on lead-to-client conversion
  6. Dropped fields documented in convert_lead_to_client have no equivalent on Client

NOTE on source_platform (test 4):
The protection for a UTM-derived source_platform is NOT a distinct per-field
rule. It is a consequence of the general provenance-tier mechanism: intake
creates leads with crm_lead (tier 3), and the staff PATCH endpoint always
uses firm_entered (tier 2). Since tier 2 < tier 3, lower-tier logic applies
and non-null fields are never overwritten. There is no explicit guard saying
"source_platform from UTMs is special." If a future code path passed crm_lead
provenance in an update, it would overwrite source_platform. The test below
asserts the real current behavior (general-tier protection), not a per-field
guarantee that does not exist.
"""

import uuid
import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.schemas.lead import LeadUpdate
from app.crud.lead import (
    update_lead_with_precedence,
    transition_lead_stage,
    create_lead,
)
from app.schemas.lead import LeadCreate
from app.core.enums import (
    LeadProvenance,
    LeadStage,
    ReferralSource,
    SourcePlatform,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Attribution Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.name, firm.slug
        return firm
    finally:
        db.close()


def _create_lead(firm_id, provenance: LeadProvenance, **kwargs) -> Lead:
    """Create a Lead directly in the DB with the given provenance and field overrides."""
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Attribution Test Prospect",
            email=f"attr-{uuid.uuid4()}@example.com",
            provenance=provenance.value,
            **kwargs,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        # Cache all needed scalar values before session close.
        _ = lead.id, lead.firm_id, lead.provenance, lead.phone
        _ = lead.revenue_band, lead.source_platform, lead.referral_source
        _ = lead.entity_type, lead.referring_client_id, lead.converted_client_id
        return lead
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: Higher tier blocks lower tier overwrite of a non-null field
# (THE GUARD TEST -- must be watched to fail per Andrew's instruction)
# ---------------------------------------------------------------------------

class TestProvenancePrecedence:
    def test_higher_tier_provenance_blocks_lower_tier_overwrite_of_nonnull_field(self):
        """crm_lead (tier 3) blocks firm_entered (tier 2) from overwriting a set field.

        This is the automated form of tonight's live curl+psql proof. The CRUD
        function is tested directly (not via API) so the test is precise about
        which function is under examination.
        """
        firm = _make_firm("guard-test-firm")
        lead = _create_lead(firm.id, LeadProvenance.crm_lead, phone="555-original")

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            update_in = LeadUpdate(phone="555-overwrite-attempt")
            updated = update_lead_with_precedence(
                db=db,
                lead=fresh_lead,
                update_in=update_in,
                new_provenance=LeadProvenance.firm_entered,
            )
            assert updated.phone == "555-original", (
                f"Provenance breach: firm_entered overwrote crm_lead phone. "
                f"Got {updated.phone!r}, expected '555-original'"
            )
            assert updated.provenance == LeadProvenance.crm_lead.value, (
                f"Provenance was downgraded. Got {updated.provenance!r}"
            )
        finally:
            db.close()

    def test_lower_tier_provenance_fills_null_field(self):
        """client_reported (tier 1) IS allowed to fill a currently-null field on a crm_lead.

        The substitution rule has two halves: block overwrites AND allow blank-filling.
        This tests the second half so the rule is fully proven, not just its
        blocking side.
        """
        firm = _make_firm("fill-null-firm")
        # revenue_band is None at creation
        lead = _create_lead(firm.id, LeadProvenance.crm_lead)

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            assert fresh_lead.revenue_band is None, "Precondition: revenue_band must be null"

            update_in = LeadUpdate(revenue_band="100k-250k")
            updated = update_lead_with_precedence(
                db=db,
                lead=fresh_lead,
                update_in=update_in,
                new_provenance=LeadProvenance.client_reported,
            )
            assert updated.revenue_band == "100k-250k", (
                f"Lower tier should fill a null field. Got {updated.revenue_band!r}"
            )
            # Provenance must NOT be downgraded when a lower tier fills a blank.
            assert updated.provenance == LeadProvenance.crm_lead.value, (
                f"Provenance was wrongly downgraded. Got {updated.provenance!r}"
            )
        finally:
            db.close()

    def test_equal_tier_provenance_allows_normal_update(self):
        """firm_entered updating a firm_entered lead applies normally.

        Proves the precedence rule is not accidentally over-broad -- equal tier
        must not block updates, only lower tier does.
        """
        firm = _make_firm("equal-tier-firm")
        lead = _create_lead(firm.id, LeadProvenance.firm_entered, phone="555-original")

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            update_in = LeadUpdate(phone="555-updated")
            updated = update_lead_with_precedence(
                db=db,
                lead=fresh_lead,
                update_in=update_in,
                new_provenance=LeadProvenance.firm_entered,
            )
            assert updated.phone == "555-updated", (
                f"Equal-tier update should apply normally. Got {updated.phone!r}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 4: UTM-derived source_platform protected by general tier mechanism
# (see module docstring for the important caveat about per-field vs general)
# ---------------------------------------------------------------------------

class TestSourcePlatformProtection:
    def test_utm_derived_source_platform_protected_from_firm_entered_override(self):
        """A UTM-assigned source_platform on a crm_lead lead is not overwritten by firm_entered.

        The protection is the GENERAL provenance-tier mechanism, not a per-field
        rule. It works because intake uses crm_lead (tier 3) and the staff PATCH
        endpoint always uses firm_entered (tier 2). Since 2 < 3, non-null fields
        are never overwritten. There is no explicit per-field guard on source_platform
        -- a future crm_lead-provenance write could still overwrite it.
        This test asserts the real current behavior, not a stronger guarantee that
        does not exist in the shipped code.
        """
        firm = _make_firm("source-platform-firm")
        lead = _create_lead(
            firm.id,
            LeadProvenance.crm_lead,
            source_platform=SourcePlatform.google.value,
        )

        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            assert fresh_lead.source_platform == SourcePlatform.google.value, (
                "Precondition: source_platform must be 'google'"
            )

            update_in = LeadUpdate(source_platform=SourcePlatform.facebook)
            updated = update_lead_with_precedence(
                db=db,
                lead=fresh_lead,
                update_in=update_in,
                new_provenance=LeadProvenance.firm_entered,
            )
            assert updated.source_platform == SourcePlatform.google.value, (
                f"firm_entered should not overwrite a crm_lead source_platform. "
                f"Got {updated.source_platform!r}, expected 'google'"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 5: Attribution flows forward unchanged on conversion
# ---------------------------------------------------------------------------

class TestAttributionOnConversion:
    def test_attribution_flows_forward_unchanged_on_conversion(self):
        """referral_source, referring_client_id, and entity_type carry forward to Client.

        This is the automated form of tonight's manual won-conversion proof:
        real convert_lead_to_client verified live via psql showing the exact
        field values on the resulting Client row.
        """
        from app.models.client import Client as ClientModel

        firm = _make_firm("conversion-attr-firm")

        # Create a real client to serve as the referrer (FK target).
        db = TestingSessionLocal()
        try:
            referrer = ClientModel(
                firm_id=firm.id,
                name="The Referrer Client",
            )
            db.add(referrer)
            db.commit()
            db.refresh(referrer)
            referrer_id = referrer.id
        finally:
            db.close()

        # Create the lead with real attribution values.
        lead = _create_lead(
            firm.id,
            LeadProvenance.crm_lead,
            referral_source=ReferralSource.google_search.value,
            entity_type="individual",
            referring_client_id=referrer_id,
        )

        # Transition to won -- this calls convert_lead_to_client internally.
        db = TestingSessionLocal()
        try:
            fresh_lead = db.query(Lead).filter(Lead.id == lead.id).first()
            updated_lead = transition_lead_stage(
                db=db,
                lead=fresh_lead,
                new_stage=LeadStage.won,
            )
            client_id = updated_lead.converted_client_id
            assert client_id is not None, "converted_client_id must be set after won transition"

            resulting_client = db.query(ClientModel).filter(
                ClientModel.id == client_id
            ).first()
            assert resulting_client is not None, "Converted Client row not found"

            assert resulting_client.referral_source == ReferralSource.google_search.value, (
                f"referral_source not carried forward. Got {resulting_client.referral_source!r}"
            )
            assert resulting_client.entity_type == "individual", (
                f"entity_type not carried forward. Got {resulting_client.entity_type!r}"
            )
            assert resulting_client.referring_client_id == referrer_id, (
                f"referring_client_id not carried forward. Got {resulting_client.referring_client_id!r}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 6: Dropped fields have no Client equivalent
# ---------------------------------------------------------------------------

class TestDroppedFieldsHaveNoClientEquivalent:
    def test_dropped_fields_are_absent_from_client_model(self):
        """Fields documented as dropped in convert_lead_to_client have no Client column.

        This test enforces the documented gap as a schema-level assertion, so
        a future migration adding one of these fields to Client would require
        an explicit decision to update both the conversion logic AND this test.
        Checked against Client.__table__.columns (the real DB schema definition),
        not against an ORM object attribute, for maximum precision.

        Representative dropped fields checked: hot, urgency, source_platform.
        Full list documented in convert_lead_to_client docstring in app/crud/lead.py.
        """
        from app.models.client import Client as ClientModel

        client_columns = {col.name for col in ClientModel.__table__.columns}

        assert "hot" not in client_columns, (
            "Client model gained a 'hot' column -- update convert_lead_to_client "
            "to explicitly decide whether and how to carry it forward"
        )
        assert "urgency" not in client_columns, (
            "Client model gained an 'urgency' column -- update convert_lead_to_client "
            "to explicitly decide whether and how to carry it forward"
        )
        assert "source_platform" not in client_columns, (
            "Client model gained a 'source_platform' column -- update convert_lead_to_client "
            "to explicitly decide whether and how to carry it forward"
        )
