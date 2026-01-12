# tests/conftest.py
import pytest
from sqlalchemy.orm import Session
from app.db.base import Base
from tests.test_main import engine, TestingSessionLocal

@pytest.fixture(autouse=True)
def reset_test_db():
    # Drop and recreate tables between tests
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
