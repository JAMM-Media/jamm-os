# tests/test_spine_metric_registry.py

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.conftest import TestingSessionLocal
from app.core.enums import BetterDirection
from app.core.metric_seed_data import SEED_METRICS
from app.models.metric_registry import MetricRegistry


def _seed_registry(db):
    """
    The test database is built from Base.metadata.create_all, not from
    Alembic migrations, so the migration's seed insert never runs here.
    Seed identically to the migration using the same shared source list
    so this test proves the model/schema can hold and be queried for
    exactly the locked Session 0 core.
    """
    for key, display_name, unit, better_direction, benchmark_eligible, tier in SEED_METRICS:
        db.add(
            MetricRegistry(
                key=key,
                display_name=display_name,
                unit=unit,
                better_direction=BetterDirection(better_direction),
                benchmark_eligible=benchmark_eligible,
                tier=tier,
            )
        )
    db.commit()


def test_seed_rows_exist_after_migration():
    db = TestingSessionLocal()
    try:
        _seed_registry(db)

        rows = db.query(MetricRegistry).all()
        keys_found = {row.key for row in rows}
        expected_keys = {key for key, *_ in SEED_METRICS}

        assert keys_found == expected_keys
        assert len(rows) == 11
    finally:
        db.close()


def test_unique_constraint_on_key_rejects_duplicate():
    db = TestingSessionLocal()
    try:
        db.add(
            MetricRegistry(
                key="engagement_velocity",
                display_name="Engagement Velocity",
                unit="days",
                better_direction=BetterDirection.lower,
                benchmark_eligible=True,
                tier=1,
            )
        )
        db.commit()

        db.add(
            MetricRegistry(
                key="engagement_velocity",
                display_name="Duplicate Key Attempt",
                unit="days",
                better_direction=BetterDirection.lower,
                benchmark_eligible=True,
                tier=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_better_direction_stored_as_non_native_enum_string():
    db = TestingSessionLocal()
    try:
        row = MetricRegistry(
            key="document_collection_speed",
            display_name="Document Collection Speed",
            unit="days",
            better_direction=BetterDirection.lower,
            benchmark_eligible=True,
            tier=1,
        )
        db.add(row)
        db.commit()

        raw = db.execute(
            text("SELECT better_direction FROM metric_registry WHERE key = :key"),
            {"key": "document_collection_speed"},
        ).scalar_one()

        assert raw == "lower"
        assert isinstance(raw, str)

        column_type = db.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'metric_registry' AND column_name = 'better_direction'"
            )
        ).scalar_one()
        assert column_type in ("character varying", "text")
    finally:
        db.close()
