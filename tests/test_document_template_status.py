# tests/test_document_template_status.py
"""
Guard tests for the document_template_status backend.

Tests:
  a. A firm owner can move an item through the full lifecycle:
     vendor_sample -> firm_draft -> firm_approved.
     Confirms published_by and published_at are set correctly on publish.
  b. A plain staff member is refused both set_draft and publish (403).
     Watched-fail: temporarily bypass _require_template_manager, confirm
     the wrongly-permitted call succeeds, restore, confirm refused.
  c. get_status returns None for an item never added to the lifecycle,
     confirming ordinary client documents are never accidentally swept in.
  d. revert_to_draft moves firm_approved back to firm_draft, and
     preserves published_by/published_at as audit history (not cleared).
  e. Tenant isolation: firm B cannot read or mutate firm A's status rows.
"""
import uuid

import pytest
from fastapi import HTTPException
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import TemplateStatus, UserRole
from app.core.security import get_password_hash
from app.services import document_template_status_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)
        return firm.id
    finally:
        db.close()


def _make_user(firm_id: uuid.UUID, role: UserRole) -> User:
    db = TestingSessionLocal()
    try:
        email = f"{role.value}-{uuid.uuid4().hex[:8]}@test.com"
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("pass"),
            full_name=f"{role.value} user",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        # Detach so it can be used outside this session.
        user_copy = User.__new__(User)
        user_copy.__dict__.update(user.__dict__)
        user_copy.__dict__.pop("_sa_instance_state", None)
        return user_copy
    finally:
        db.close()


def _make_detached_user(firm_id: uuid.UUID, role: UserRole) -> User:
    """Create a user and return a plain object with id/role set, safe to pass to service."""
    db = TestingSessionLocal()
    try:
        email = f"{role.value}-{uuid.uuid4().hex[:8]}@test.com"
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("pass"),
            full_name=f"{role.value} user",
            role=role,
        )
        db.add(user)
        db.commit()
        user_id = user.id
        user_role = user.role
    finally:
        db.close()
    # Build a minimal stand-in that has .id and .role without a live session.
    stub = type("UserStub", (), {"id": user_id, "role": user_role})()
    return stub


# ---------------------------------------------------------------------------
# Test (a): full lifecycle -- vendor_sample -> firm_draft -> firm_approved
# ---------------------------------------------------------------------------

def test_full_lifecycle_firm_owner():
    firm_id = _make_firm(f"lc-{uuid.uuid4().hex[:6]}")
    owner = _make_detached_user(firm_id, UserRole.firm_owner)
    item_id = uuid.uuid4()

    db = TestingSessionLocal()
    try:
        # Nothing there yet.
        assert svc.get_status(db, firm_id=firm_id, item_type="document", item_id=item_id) is None

        # Move to firm_draft.
        row = svc.set_draft(db, firm_id=firm_id, item_type="document", item_id=item_id, user=owner)
        assert row.status == TemplateStatus.firm_draft
        assert row.published_by is None
        assert row.published_at is None

        # Move to firm_approved.
        row = svc.publish(db, firm_id=firm_id, item_type="document", item_id=item_id, user=owner)
        assert row.status == TemplateStatus.firm_approved
        assert row.published_by == owner.id
        assert row.published_at is not None

        # Confirm get_status returns the row.
        fetched = svc.get_status(db, firm_id=firm_id, item_type="document", item_id=item_id)
        assert fetched is not None
        assert fetched.status == TemplateStatus.firm_approved
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (b): staff is refused set_draft and publish
# ---------------------------------------------------------------------------

def test_staff_refused_set_draft_and_publish():
    firm_id = _make_firm(f"st-{uuid.uuid4().hex[:6]}")
    owner = _make_detached_user(firm_id, UserRole.firm_owner)
    staff = _make_detached_user(firm_id, UserRole.staff)
    item_id = uuid.uuid4()

    db = TestingSessionLocal()
    try:
        # Watched-fail: bypass the gate and confirm the operation succeeds.
        with patch.object(svc, "_require_template_manager", return_value=None):
            row = svc.set_draft(db, firm_id=firm_id, item_type="document", item_id=item_id, user=staff)
            assert row.status == TemplateStatus.firm_draft
            svc.publish(db, firm_id=firm_id, item_type="document", item_id=item_id, user=staff)

        # Restore: confirm staff is actually refused.
        with pytest.raises(HTTPException) as exc:
            svc.set_draft(db, firm_id=firm_id, item_type="document", item_id=uuid.uuid4(), user=staff)
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            svc.publish(db, firm_id=firm_id, item_type="document", item_id=item_id, user=staff)
        assert exc.value.status_code == 403
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (c): get_status returns None for an ordinary item
# ---------------------------------------------------------------------------

def test_get_status_none_for_plain_item():
    firm_id = _make_firm(f"gs-{uuid.uuid4().hex[:6]}")
    db = TestingSessionLocal()
    try:
        result = svc.get_status(
            db,
            firm_id=firm_id,
            item_type="document",
            item_id=uuid.uuid4(),
        )
        assert result is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (d): revert_to_draft preserves published_by/published_at
# ---------------------------------------------------------------------------

def test_revert_to_draft_preserves_audit_fields():
    firm_id = _make_firm(f"rv-{uuid.uuid4().hex[:6]}")
    owner = _make_detached_user(firm_id, UserRole.firm_owner)
    item_id = uuid.uuid4()

    db = TestingSessionLocal()
    try:
        svc.set_draft(db, firm_id=firm_id, item_type="folder", item_id=item_id, user=owner)
        row = svc.publish(db, firm_id=firm_id, item_type="folder", item_id=item_id, user=owner)
        published_by_before = row.published_by
        published_at_before = row.published_at

        reverted = svc.revert_to_draft(db, firm_id=firm_id, item_type="folder", item_id=item_id, user=owner)
        assert reverted.status == TemplateStatus.firm_draft
        # Audit fields are preserved, not cleared.
        assert reverted.published_by == published_by_before
        assert reverted.published_at == published_at_before
    finally:
        db.close()


def test_revert_to_draft_from_non_approved_raises_409():
    firm_id = _make_firm(f"rv2-{uuid.uuid4().hex[:6]}")
    owner = _make_detached_user(firm_id, UserRole.firm_owner)
    item_id = uuid.uuid4()

    db = TestingSessionLocal()
    try:
        svc.set_draft(db, firm_id=firm_id, item_type="document", item_id=item_id, user=owner)
        with pytest.raises(HTTPException) as exc:
            svc.revert_to_draft(db, firm_id=firm_id, item_type="document", item_id=item_id, user=owner)
        assert exc.value.status_code == 409
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (e): tenant isolation
# ---------------------------------------------------------------------------

def test_tenant_isolation():
    firm_a_id = _make_firm(f"ta-{uuid.uuid4().hex[:6]}")
    firm_b_id = _make_firm(f"tb-{uuid.uuid4().hex[:6]}")
    owner_a = _make_detached_user(firm_a_id, UserRole.firm_owner)
    owner_b = _make_detached_user(firm_b_id, UserRole.firm_owner)
    item_id = uuid.uuid4()

    db = TestingSessionLocal()
    try:
        # Owner A creates a row for item_id.
        svc.set_draft(db, firm_id=firm_a_id, item_type="document", item_id=item_id, user=owner_a)

        # Firm B cannot see it via get_status.
        assert svc.get_status(db, firm_id=firm_b_id, item_type="document", item_id=item_id) is None

        # Firm B cannot publish it (404, not 403 -- the row does not exist for firm B).
        with pytest.raises(HTTPException) as exc:
            svc.publish(db, firm_id=firm_b_id, item_type="document", item_id=item_id, user=owner_b)
        assert exc.value.status_code == 404

        # Firm B cannot revert it.
        with pytest.raises(HTTPException) as exc:
            svc.revert_to_draft(db, firm_id=firm_b_id, item_type="document", item_id=item_id, user=owner_b)
        assert exc.value.status_code == 404
    finally:
        db.close()