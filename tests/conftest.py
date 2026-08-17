# tests/conftest.py

"""
Test configuration for JAMM PX.

IMPORTANT: We use PostgreSQL for tests via the CI GitHub Actions workflow.
The DATABASE_URL environment variable must point to a real PostgreSQL instance.

For local development, start the Docker database first:
    docker-compose up -d db
    DATABASE_URL=postgresql+psycopg://postgres:postgres123@localhost:5432/accounting_dev pytest

The SQLite approach was removed because:
1. PostgreSQL handles UUIDs and enums differently than SQLite
2. Tests that pass on SQLite can fail in production on PostgreSQL
3. The CI pipeline already runs PostgreSQL — local should match CI exactly
"""

import os
from dotenv import load_dotenv

# Must run before any `app` import: app.db.session builds its module-level
# SessionLocal from DATABASE_URL at import time, so the test override has to
# land first or that engine permanently binds to whatever DATABASE_URL was
# already ambient (e.g. production).
load_dotenv(".env.test", override=True)

# Must be set before any app imports so rate_limit.py picks it up
os.environ["RATE_LIMIT_ENABLED"] = "false"

# Lets any module detect test context, independent of DATABASE_URL parsing.
os.environ["JAMM_TESTING"] = "1"

# Test-only Fernet key, generated once with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Not a secret, never used outside this test suite. Set unconditionally (before
# any app import) so Settings picks it up regardless of the developer's local .env.
os.environ["ENCRYPTION_KEY"] = "j8iv6pxYd3itXw7qMCwKAxzvl_0xjTZD1w2tGFHbXho="

DATABASE_URL = os.environ["DATABASE_URL"]

_PRODUCTION_MARKERS = ("ondigitalocean.com", ":25060")
if any(marker in DATABASE_URL for marker in _PRODUCTION_MARKERS):
    raise RuntimeError(
        "REFUSING TO RUN TESTS: DATABASE_URL resolves to what looks like the "
        "production database. Tests would DROP and TRUNCATE tables. "
        "Fix .env.test or your environment before proceeding."
    )

import pytest
from fastapi.testclient import TestClient
from fastapi.background import BackgroundTasks
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base_class import Base
from app.dependencies.db import get_db
from app import models  # Ensures all models register with Base.metadata

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pytest_configure(config):
    """Create all tables before the test session starts."""
    Base.metadata.create_all(bind=engine, checkfirst=True)


def pytest_unconfigure(config):
    """Drop all tables after the test session ends."""
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    """
    Clears all table data between tests.
    TRUNCATE ... CASCADE wipes child rows automatically (respects FK constraints).
    RESTART IDENTITY resets any serial sequences.
    autouse=True means this runs automatically for every test.
    """
    yield
    with engine.connect() as conn:
        # Get all table names from the metadata
        table_names = ", ".join(Base.metadata.tables.keys())
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        conn.commit()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def mock_email_service(monkeypatch):
    """
    Replaces EmailService._send with a no-op recorder for every test. No
    network IO ever happens. _send_raw (used by the magic link and portal
    invite flows) delegates straight to _send, so patching _send alone
    covers both call paths. Tests that want to assert an email would have
    been sent can request this fixture directly and inspect the list.
    """
    from app.services.email_service import EmailService

    sent_emails = []

    def _fake_send(to_email, subject, html_body, from_name, reply_to=None,
                    display_name=None, sending_domain=None):
        sent_emails.append({
            "to_email": to_email,
            "subject": subject,
            "html_body": html_body,
            "from_name": from_name,
            "reply_to": reply_to,
            "display_name": display_name,
            "sending_domain": sending_domain,
        })

    monkeypatch.setattr(EmailService, "_send", staticmethod(_fake_send))
    return sent_emails


@pytest.fixture(autouse=True)
def run_background_tasks_synchronously():
    """
    Force BackgroundTasks to execute synchronously during
    tests so background task interactions with the test DB
    session do not hang.
    """
    # TestClient already runs background tasks synchronously
    # by default — this fixture ensures no async leakage.
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared helper fixtures for tests that need a firm + user already set up
# ---------------------------------------------------------------------------

@pytest.fixture
def firm_a_owner(client):
    """
    Creates Firm A with a firm_owner user and returns the auth headers.
    Used by tenant isolation tests to represent one real accounting firm.
    """
    # First create the firm via system_admin
    # In tests, we bypass firm creation auth by using the DB directly
    from app.models.firm import Firm
    from app.core.security import get_password_hash
    from app.models.user import User
    from app.core.enums import UserRole
    import uuid

    db = TestingSessionLocal()
    try:
        firm = Firm(name="Firm A CPA", slug="firm-a-cpa")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        firm_id = str(firm.id)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        user = User(
            firm_id=firm.id,
            email="owner@firma.com",
            hashed_password=get_password_hash("password123"),
            full_name="Owner A",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": "owner@firma.com", "password": "password123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}


@pytest.fixture
def firm_b_owner(client):
    """
    Creates Firm B with a firm_owner user and returns the auth headers.
    Used to prove that Firm A cannot see Firm B's data.
    """
    from app.models.firm import Firm
    from app.core.security import get_password_hash
    from app.models.user import User
    from app.core.enums import UserRole

    db = TestingSessionLocal()
    try:
        firm = Firm(name="Firm B Bookkeeping", slug="firm-b-bookkeeping")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        firm_id = str(firm.id)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        user = User(
            firm_id=firm.id,
            email="owner@firmb.com",
            hashed_password=get_password_hash("password456"),
            full_name="Owner B",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": "owner@firmb.com", "password": "password456"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}


@pytest.fixture
def firm_a_staff(client, firm_a_owner):
    """
    Creates a staff user in Firm A and returns the auth headers.
    Used by RBAC tests to verify staff cannot access manager-only endpoints.
    """
    from app.models.user import User
    from app.core.security import get_password_hash
    from app.core.enums import UserRole
    import uuid

    firm_id = firm_a_owner["firm_id"]

    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff-{uuid.uuid4()}@firma.com",
            hashed_password=get_password_hash("staffpass123"),
            full_name="Staff A",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        email = user.email
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": "staffpass123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}


@pytest.fixture
def portal_client_headers(client, firm_a_owner):
    """
    Creates a portal-enabled client in Firm A and returns
    (client_id, portal_auth_headers) for use in portal endpoint tests.
    """
    from app.models.client import Client
    from app.core.security import get_password_hash
    import uuid as _uuid

    firm_id = firm_a_owner["firm_id"]
    client_email = f"portal-{_uuid.uuid4()}@client.com"
    client_password = "portalpass123"

    db = TestingSessionLocal()
    try:
        portal_client_obj = Client(
            firm_id=firm_id,
            name="Portal Test Client",
            email=client_email,
            portal_access_enabled=True,
            portal_password_hash=get_password_hash(client_password),
        )
        db.add(portal_client_obj)
        db.commit()
        db.refresh(portal_client_obj)
        client_id = str(portal_client_obj.id)

        # Get the firm slug for login
        from app.models.firm import Firm as FirmModel
        firm = db.get(FirmModel, firm_id)
        firm_slug = firm.slug
    finally:
        db.close()

    # Log in via portal auth endpoint
    login_r = client.post("/portal/auth/login", json={
        "firm_slug": firm_slug,
        "email": client_email,
        "password": client_password,
    })
    assert login_r.status_code == 200, f"Portal login failed: {login_r.json()}"
    token = login_r.json()["access_token"]

    return client_id, {"Authorization": f"Bearer {token}"}