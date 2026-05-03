# tests/test_portal_magic_link.py

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TestingSessionLocal

_MSG = "If a portal account exists for that email, a login link has been sent."


@pytest.fixture
def _db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_client_magic_link_request_returns_200_for_valid_email(client: TestClient, _db):
    from app.models.firm import Firm
    from app.models.client import Client

    firm = Firm(name="Test Firm ML", slug="test-firm-ml")
    _db.add(firm)
    _db.commit()
    _db.refresh(firm)

    portal_client = Client(
        firm_id=firm.id,
        name="Magic Link Client",
        email="ml-client@example.com",
        portal_access_enabled=True,
    )
    _db.add(portal_client)
    _db.commit()

    res = client.post(
        "/portal/request-magic-link",
        json={"email": "ml-client@example.com"},
    )
    assert res.status_code == 200
    assert res.json()["message"] == _MSG


def test_client_magic_link_request_returns_200_for_unknown_email(client: TestClient):
    res = client.post(
        "/portal/request-magic-link",
        json={"email": "nobody@unknown-domain-xyz.com"},
    )
    assert res.status_code == 200
    assert res.json()["message"] == _MSG
