# tests/test_firm_library_seed.py
"""
Guard tests for the firm_library_seed_service.

Tests:
  a. A firm owner can seed starter templates; confirms exactly 8 Document rows
     and 8 DocumentTemplateStatus rows (status=vendor_sample) are created.
  b. A plain staff member is refused 403 attempting to seed.
     Watched-fail: temporarily bypass _require_template_manager, confirm
     8 rows wrongly get created, restore, confirm refused.
  c. Calling seed a second time for the same firm is refused (409).
     Watched-fail: temporarily bypass has_starter_templates, confirm 16 rows
     wrongly get created, restore, confirm refused at 8.
  d. has_starter_templates returns False for a fresh firm and True after seeding.
  e. Tenant isolation: seeding firm A does not create rows for firm B.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from tests.conftest import TestingSessionLocal
from app.models.document import Document
from app.models.document_template_status import DocumentTemplateStatus
from app.core.enums import TemplateStatus, UserRole
from app.core.security import get_password_hash
from app.models.firm import Firm
from app.models.user import User
from app.services import firm_library_seed_service as svc


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


def _make_detached_user(firm_id: uuid.UUID, role: UserRole):
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
    stub = type("UserStub", (), {"id": user_id, "role": user_role})()
    return stub


def _count_rows(firm_id: uuid.UUID):
    db = TestingSessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.firm_id == firm_id,
            Document.source == "system",
            Document.scope == "firm_library",
        ).count()
        ts = db.query(DocumentTemplateStatus).filter(
            DocumentTemplateStatus.firm_id == firm_id,
            DocumentTemplateStatus.status == TemplateStatus.vendor_sample,
        ).count()
        return docs, ts
    finally:
        db.close()


# ---------------------------------------------------------------------------
# (a) Firm owner can seed -- creates exactly 8 Document + 8 TemplateStatus rows
# ---------------------------------------------------------------------------

def test_seed_creates_8_docs_and_8_template_status_rows():
    firm_id = _make_firm(f"seed-a-{uuid.uuid4().hex[:6]}")
    owner = _make_detached_user(firm_id, UserRole.firm_owner)

    with patch("app.services.firm_library_seed_service.s3_service.upload_fileobj"):
        db = TestingSessionLocal()
        try:
            count = svc.seed_starter_templates(db, firm_id=firm_id, user=owner)
        finally:
            db.close()

    assert count == 8
    docs, ts = _count_rows(firm_id)
    assert docs == 8
    assert ts == 8


# ---------------------------------------------------------------------------
# (b) Staff refused 403
# ---------------------------------------------------------------------------

def test_staff_refused_403():
    firm_id = _make_firm(f"seed-b-{uuid.uuid4().hex[:6]}")
    staff = _make_detached_user(firm_id, UserRole.staff)

    with patch("app.services.firm_library_seed_service.s3_service.upload_fileobj"):
        db = TestingSessionLocal()
        try:
            # Watched-fail: bypass gate, confirm rows wrongly created.
            with patch.object(svc, "_require_template_manager", return_value=None):
                count = svc.seed_starter_templates(db, firm_id=firm_id, user=staff)
                assert count == 8  # wrong -- only possible with gate bypassed

            docs, ts = _count_rows(firm_id)
            assert docs == 8  # confirms bypass let it through

            # Real gate: staff is refused.
            db2 = TestingSessionLocal()
            try:
                with pytest.raises(HTTPException) as exc:
                    svc.seed_starter_templates(db2, firm_id=firm_id, user=staff)
                assert exc.value.status_code == 403
            finally:
                db2.close()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# (c) Second seeding attempt refused with 409
# ---------------------------------------------------------------------------

def test_second_seed_refused_409():
    firm_id = _make_firm(f"seed-c-{uuid.uuid4().hex[:6]}")
    owner = _make_detached_user(firm_id, UserRole.firm_owner)

    with patch("app.services.firm_library_seed_service.s3_service.upload_fileobj"):
        db = TestingSessionLocal()
        try:
            # First seed -- succeeds.
            svc.seed_starter_templates(db, firm_id=firm_id, user=owner)
        finally:
            db.close()

        # Watched-fail: bypass idempotency check, confirm 16 rows wrongly created.
        db2 = TestingSessionLocal()
        try:
            with patch.object(svc, "has_starter_templates", return_value=False):
                count2 = svc.seed_starter_templates(db2, firm_id=firm_id, user=owner)
                assert count2 == 8  # wrong -- second seed should be refused
            docs, ts = _count_rows(firm_id)
            assert docs == 16  # confirms bypass created duplicates
            assert ts == 16
        finally:
            db2.close()

        # Real idempotency: second call is refused.
        db3 = TestingSessionLocal()
        try:
            with pytest.raises(HTTPException) as exc:
                svc.seed_starter_templates(db3, firm_id=firm_id, user=owner)
            assert exc.value.status_code == 409
        finally:
            db3.close()


# ---------------------------------------------------------------------------
# (d) has_starter_templates returns False before seeding, True after
# ---------------------------------------------------------------------------

def test_has_starter_templates_false_then_true():
    firm_id = _make_firm(f"seed-d-{uuid.uuid4().hex[:6]}")
    owner = _make_detached_user(firm_id, UserRole.firm_owner)

    db = TestingSessionLocal()
    try:
        assert svc.has_starter_templates(db, firm_id=firm_id) is False
    finally:
        db.close()

    with patch("app.services.firm_library_seed_service.s3_service.upload_fileobj"):
        db2 = TestingSessionLocal()
        try:
            svc.seed_starter_templates(db2, firm_id=firm_id, user=owner)
        finally:
            db2.close()

    db3 = TestingSessionLocal()
    try:
        assert svc.has_starter_templates(db3, firm_id=firm_id) is True
    finally:
        db3.close()


# ---------------------------------------------------------------------------
# (e) Tenant isolation -- seeding firm A does not affect firm B
# ---------------------------------------------------------------------------

def test_tenant_isolation():
    firm_a = _make_firm(f"seed-e-a-{uuid.uuid4().hex[:6]}")
    firm_b = _make_firm(f"seed-e-b-{uuid.uuid4().hex[:6]}")
    owner_a = _make_detached_user(firm_a, UserRole.firm_owner)

    with patch("app.services.firm_library_seed_service.s3_service.upload_fileobj"):
        db = TestingSessionLocal()
        try:
            svc.seed_starter_templates(db, firm_id=firm_a, user=owner_a)
        finally:
            db.close()

    # Firm B unaffected.
    db2 = TestingSessionLocal()
    try:
        assert svc.has_starter_templates(db2, firm_id=firm_b) is False
        docs_b, ts_b = _count_rows(firm_b)
        assert docs_b == 0
        assert ts_b == 0
    finally:
        db2.close()