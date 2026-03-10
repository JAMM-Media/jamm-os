# tests/conftest.py

"""
Test configuration for JAMM OS.

IMPORTANT: We use PostgreSQL for tests via the CI GitHub Actions workflow.
The DATABASE_URL environment variable must point to a real PostgreSQL instance.

For local development, start the Docker database first:
    docker-compose up -d db
    DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/accounting_dev pytest

The SQLite approach was removed because:
1. PostgreSQL handles UUIDs and enums differently than SQLite
2. Tests that pass on SQLite can fail in production on PostgreSQL
3. The CI pipeline already runs PostgreSQL — local should match CI exactly
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

from app.main import app
from app.db.base_class import Base
from app.dependencies.db import get_db
from app import models  # Ensures all models register with Base.metadata


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres123@localhost:5432/accounting_dev"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pytest_configure(config):
    """Create all tables before the test session starts."""
    Base.metadata.create_all(bind=engine)


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

    login = client.post("/auth/token", data={"username": "owner@firma.com", "password": "password123"})
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

    login = client.post("/auth/token", data={"username": "owner@firmb.com", "password": "password456"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}