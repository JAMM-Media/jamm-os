# tests/test_spine_floors_registry.py

"""The technique floors registry and the weekly recheck's default.

Ruling 2, Aug 26, 2026: floors live in app/core/technique_floors.py, an
Andrew-owned Python registry, and recheck_failed_findings reads it by default
instead of defaulting to an empty dict. The scheduler calls the job with no
arguments, so the no-argument call shape is the one that matters here and it
had no test at all before this file.

The registry ships EMPTY on purpose. Tests that need a populated registry
monkeypatch app.core.technique_floors.FLOORS_BY_TECHNIQUE. That works only
because recheck reads the dict through get_floors_by_technique() at call
time. If someone rewires it to import the dict at module load, every test
below that monkeypatches goes red, and that is the correct outcome: the
defect would be in the wiring, not in these tests.

FIXTURE RULE, carried from tests/test_platform_events.py: assertions are
scoped to the finding this test created, by id. recheck_failed_findings
re-judges every failed row in the table, including rows other tests left
behind, so nothing here may assert on table-wide counts.
"""

import uuid
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.core import technique_floors
from app.core.enums import GateBar, GateStatus, SubjectType
from app.core.technique_floors import FLOORS_BY_TECHNIQUE, get_floors_by_technique
from app.models.finding import Finding
from app.services.findings_recheck import recheck_failed_findings


def _make_failed_finding(technique="test_technique", **overrides) -> uuid.UUID:
    """A failed finding that would pass if its technique had floors of n >= 1."""
    db = TestingSessionLocal()
    try:
        defaults = dict(
            firm_id=None,
            technique=technique,
            subject_type=SubjectType.pattern,
            subject_key=f"pattern-{uuid.uuid4()}",
            gate_bar=GateBar.firm_facing,
            gate_status=GateStatus.failed,
            statistics={"p_value": 0.001},
            data_sufficiency={"n": 5},
        )
        defaults.update(overrides)
        finding = Finding(**defaults)
        db.add(finding)
        db.commit()
        db.refresh(finding)
        return finding.id
    finally:
        db.close()


def _run_recheck(*args, **kwargs):
    """Runs the job against the test database, with both log writers pointed at it."""
    with patch("app.services.findings_recheck.SessionLocal", TestingSessionLocal), patch(
        "app.services.behavioral_log.SessionLocal", TestingSessionLocal
    ):
        return recheck_failed_findings(*args, **kwargs)


def _reload(finding_id) -> Finding:
    db = TestingSessionLocal()
    try:
        return db.get(Finding, finding_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# The default reads the registry
# ---------------------------------------------------------------------------

def test_recheck_default_reads_registry(monkeypatch):
    """The scheduler's exact call shape: recheck_failed_findings() with no argument.

    Before Ruling 2 this defaulted to {} and could never pass anything.
    """
    monkeypatch.setattr(
        technique_floors, "FLOORS_BY_TECHNIQUE", {"test_technique": {"n": 1}}
    )
    finding_id = _make_failed_finding()

    _run_recheck()

    updated = _reload(finding_id)
    assert updated.gate_status == GateStatus.passed, (
        "the no-argument call must read the registry. gate_status is "
        f"{updated.gate_status} with failure_reason {updated.failure_reason!r}. "
        "A failure_reason naming test_technique as unregistered means the "
        "default is still an empty dict."
    )
    assert updated.last_recheck_at is not None


def test_recheck_default_fails_closed_when_registry_empty():
    """No monkeypatch: the registry is empty as shipped, so the finding stays failed.

    New coverage, not a converted test. tests/test_spine_recheck.py never
    exercised the no-argument call, so nothing pinned this before.
    """
    assert FLOORS_BY_TECHNIQUE == {}, (
        "this test asserts the shipped-empty state. If a technique has authored "
        "floors, rewrite this to use a technique that genuinely has none."
    )
    finding_id = _make_failed_finding(technique="unregistered_technique")

    _run_recheck()

    updated = _reload(finding_id)
    assert updated.gate_status == GateStatus.failed
    assert "no sufficiency floors registered for technique unregistered_technique" in (
        updated.failure_reason
    )
    assert updated.last_recheck_at is not None


def test_explicit_empty_dict_overrides_registry(monkeypatch):
    """An explicit {} is honored over a populated registry.

    Pins judge_finding's documented distinction: passing {} is a deliberate
    choice and is not the same as passing nothing.
    """
    monkeypatch.setattr(
        technique_floors, "FLOORS_BY_TECHNIQUE", {"test_technique": {"n": 1}}
    )
    finding_id = _make_failed_finding()

    _run_recheck(floors_by_technique={})

    updated = _reload(finding_id)
    assert updated.gate_status == GateStatus.failed, (
        "an explicit empty dict must override the registry, not fall back to it"
    )
    assert "no sufficiency floors registered for technique test_technique" in (
        updated.failure_reason
    )


# ---------------------------------------------------------------------------
# The registry itself
# ---------------------------------------------------------------------------

def test_get_floors_returns_a_copy(monkeypatch):
    """No caller can mutate Andrew-owned numbers at runtime.

    Monkeypatched to a non-empty value first: mutating a copy of {} would
    prove nothing about the inner dicts, which a shallow copy would still
    share with the registry.
    """
    monkeypatch.setattr(
        technique_floors, "FLOORS_BY_TECHNIQUE", {"test_technique": {"n": 1}}
    )

    returned = get_floors_by_technique()
    returned["injected_technique"] = {"n": 999}
    returned["test_technique"]["n"] = 999

    assert technique_floors.FLOORS_BY_TECHNIQUE == {"test_technique": {"n": 1}}, (
        "get_floors_by_technique handed out a reference into the registry"
    )


def test_registry_shape():
    """Shape tripwire for the first technique session.

    Trivially true while the registry is empty. It exists so the first
    authored floor is caught if it is written in the wrong shape.
    """
    for technique, floors in FLOORS_BY_TECHNIQUE.items():
        assert isinstance(technique, str), f"technique key {technique!r} is not a str"
        assert isinstance(floors, dict), f"floors for {technique} is not a dict"
        for key, floor in floors.items():
            assert isinstance(key, str), f"floor key {key!r} in {technique} is not a str"
            assert isinstance(floor, (int, float)) and not isinstance(floor, bool), (
                f"floor {key}={floor!r} in {technique} is not an int or float"
            )
