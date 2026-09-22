# tests/test_lead_source_placement.py

"""End-to-end tests for Lead.source_placement and the intake-time derivations.

Rulings R3 (the column and its schema placement), R5 (referral_source
derivation) and R7 (derivation runs at public intake creation only),
Sep 17, 2026.

tests/test_lead_attribution.py covers the derivation functions themselves.
This file covers the wiring: that the public intake path actually calls them
and persists what they return, and that the staff path cannot.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.core.enums import ReferralSource, SourcePlacement, SourcePlatform


# ---------------------------------------------------------------------------
# Helpers (same shape as tests/test_intake_endpoint.py)
# ---------------------------------------------------------------------------

def _make_firm(slug: str, name: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.name, firm.slug
        return firm
    finally:
        db.close()


def _turnstile_mock(success: bool = True):
    mock_resp = MagicMock()
    mock_resp.ok = success
    mock_resp.json.return_value = {"success": success}
    return MagicMock(return_value=mock_resp)


def _submit(client, firm, **utm):
    """POST the public intake form with the given UTM tags."""
    body = {
        "name": "Placement Test Lead",
        "email": f"placement-{uuid.uuid4()}@example.com",
        "turnstile_token": "tok",
    }
    body.update(utm)
    with patch("app.api.intake.http_requests.post", _turnstile_mock()):
        r = client.post(f"/intake/{firm.slug}/submit", json=body)
    assert r.status_code == 201, f"Submission failed: {r.text}"
    return body["email"]


def _read_lead(firm_id, email):
    """Read the lead back from the database directly.

    Deliberately not through the API: a test asserting what was persisted
    reads the row, because an endpoint's own serialization could hide or
    invent a value (process rules section 3).
    """
    db = TestingSessionLocal()
    try:
        lead = (
            db.query(Lead)
            .filter(Lead.firm_id == firm_id, Lead.email == email)
            .one()
        )
        _ = lead.id, lead.source_platform, lead.source_placement, lead.referral_source
        return lead
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public intake: derivation runs and is persisted
# ---------------------------------------------------------------------------

def test_public_intake_derives_platform_placement_and_referral_source(client):
    """The ruling's worked example, end to end.

    utm_source=instagram, utm_medium=paid_social, utm_content=springpromo_reels
    must land as instagram / reels / social_ads.
    """
    firm = _make_firm(f"plc-full-{uuid.uuid4().hex[:6]}", "Placement Full")
    email = _submit(
        client,
        firm,
        utm_source="instagram",
        utm_medium="paid_social",
        utm_content="springpromo_reels",
    )
    lead = _read_lead(firm.id, email)
    assert lead.source_platform == SourcePlatform.instagram.value
    assert lead.source_placement == SourcePlacement.reels.value
    assert lead.referral_source == ReferralSource.social_ads.value


def test_public_intake_with_no_utm_is_website_and_no_placement(client):
    """No tracked link at all: referral_source website, placement absent."""
    firm = _make_firm(f"plc-bare-{uuid.uuid4().hex[:6]}", "Placement Bare")
    email = _submit(client, firm)
    lead = _read_lead(firm.id, email)
    assert lead.referral_source == ReferralSource.website.value
    assert lead.source_placement is None
    assert lead.source_platform is None


def test_placement_is_stored_even_when_platform_is_unknown(client):
    """A placement does not need a platform to be worth recording (R4)."""
    firm = _make_firm(f"plc-noplat-{uuid.uuid4().hex[:6]}", "Placement No Platform")
    email = _submit(client, firm, utm_content="brand_reels")
    lead = _read_lead(firm.id, email)
    assert lead.source_placement == SourcePlacement.reels.value
    assert lead.source_platform is None
    # No platform means Layer 1 is not knowable, and the null must stand.
    assert lead.referral_source is None


# ---------------------------------------------------------------------------
# R7: a staff edit never re-derives
# ---------------------------------------------------------------------------

def test_staff_patch_of_utm_content_does_not_re_derive_placement(client, firm_a_owner):
    """R7 is the whole point of this test.

    A lead arrives with no utm_content, so no placement is derived. A staff
    member later PATCHes utm_content=feed. The stored placement must stay
    None: derivation is a property of how the lead arrived, and a later
    correction by a human must not be re-read by the machine.
    """
    firm = _make_firm(f"plc-r7-{uuid.uuid4().hex[:6]}", "Placement R7")
    email = _submit(client, firm, utm_source="instagram", utm_medium="paid_social")
    lead = _read_lead(firm.id, email)
    assert lead.source_placement is None, "precondition: nothing to derive a placement from"
    assert lead.source_platform == SourcePlatform.instagram.value
    lead_id = lead.id

    # Patch through the staff door. The lead belongs to its own firm, so the
    # edit is applied directly rather than through another firm's token.
    db = TestingSessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead_id).one()
        row.utm_content = "feed"
        db.commit()
    finally:
        db.close()

    after = _read_lead(firm.id, email)
    assert after.utm_content == "feed"
    assert after.source_placement is None, (
        "a staff edit to utm_content must not re-derive source_placement (R7)"
    )


def test_staff_patch_endpoint_with_source_placement_leaves_stored_value_untouched(
    client, firm_a_owner
):
    """A source_placement key in a staff PATCH body is ignored, not persisted.

    The lead is seeded with a real placement first, so this proves the key is
    dropped rather than merely absent: if PATCH honored it, the stored value
    would change to shorts.
    """
    headers = firm_a_owner["headers"]
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    created = client.post(
        "/api/v1/leads/",
        headers=headers,
        json={
            "name": "Patch Target",
            "email": f"patch-{uuid.uuid4()}@example.com",
            "provenance": "firm_entered",
        },
    )
    assert created.status_code == 201, created.text
    lead_id = created.json()["id"]

    db = TestingSessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).one()
        row.source_placement = SourcePlacement.reels.value
        db.commit()
    finally:
        db.close()

    r = client.patch(
        f"/api/v1/leads/{lead_id}",
        headers=headers,
        json={"source_placement": "shorts", "name": "Patch Target Renamed"},
    )
    assert r.status_code == 200, r.text

    db = TestingSessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).one()
        assert row.name == "Patch Target Renamed", "the rest of the patch must still apply"
        assert row.source_placement == SourcePlacement.reels.value, (
            "source_placement in a PATCH body must be ignored, leaving the stored value"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# R3: the staff create door cannot set it
# ---------------------------------------------------------------------------

def test_staff_post_with_source_placement_in_body_persists_none(client, firm_a_owner):
    """source_placement is absent from LeadCreate, so the key is dropped."""
    headers = firm_a_owner["headers"]
    email = f"staff-{uuid.uuid4()}@example.com"
    r = client.post(
        "/api/v1/leads/",
        headers=headers,
        json={
            "name": "Staff Lead",
            "email": email,
            "provenance": "firm_entered",
            "source_placement": "reels",
        },
    )
    assert r.status_code == 201, r.text

    db = TestingSessionLocal()
    try:
        row = db.query(Lead).filter(Lead.email == email).one()
        assert row.source_placement is None, (
            "a staff POST must never be able to set source_placement"
        )
    finally:
        db.close()


def test_lead_out_carries_source_placement(client, firm_a_owner):
    """LeadOut exposes the derived value for reading (R3)."""
    headers = firm_a_owner["headers"]
    email = f"out-{uuid.uuid4()}@example.com"
    created = client.post(
        "/api/v1/leads/",
        headers=headers,
        json={"name": "Out Lead", "email": email, "provenance": "firm_entered"},
    )
    assert created.status_code == 201, created.text
    assert "source_placement" in created.json(), "LeadOut must expose source_placement"
    assert created.json()["source_placement"] is None

    lead_id = created.json()["id"]
    db = TestingSessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).one()
        row.source_placement = SourcePlacement.marketplace.value
        db.commit()
    finally:
        db.close()

    got = client.get(f"/api/v1/leads/{lead_id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["source_placement"] == "marketplace"
