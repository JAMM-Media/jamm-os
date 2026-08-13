# tests/test_sequence_version_pinning.py

"""
Tests for the sequence version-pinning guarantee:
a lead enrolled in a sequence stays on the version it enrolled under.

HONEST SCOPE STATEMENT
-----------------------
Full version-pinning as a behavioral guarantee -- a sequence being actively
edited or a real publish operation correctly leaving mid-walk enrollments
untouched -- is NOT fully testable today. No real sequence-editing or
version-publishing operation exists in the codebase yet.

These tests verify what is genuinely true right now:
  1. sequence_version_id is set correctly at enrollment creation and holds
     its value through a normal read cycle.
  2. No code in app/ currently assigns to .sequence_version_id on an
     enrollment object after creation (the guarantee exists by absence,
     enforced structurally via this guard test).
  3. Creating a new SequenceVersion for a Sequence does not alter existing
     Enrollment.sequence_version_id values -- the only real, existing
     operation that could conceivably interact with pinning.

Testing the full guarantee under real editing conditions (the actual pinning
rule from Section 7.1 of the contract) belongs at the time the sequence-
editing and version-publishing feature is built, and should be added then.
Not simulated now with invented row mutations that no real code path produces.
"""

import subprocess
import uuid
import pathlib

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceVersion
from app.models.enrollment import Enrollment
from app.core.enums import LeadProvenance, EnrollmentStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Pinning Test Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.name, firm.slug
        return firm
    finally:
        db.close()


def _make_lead(firm_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Pinning Test Prospect",
            email=f"pinning-{uuid.uuid4()}@example.com",
            provenance=LeadProvenance.firm_entered.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.firm_id
        return lead
    finally:
        db.close()


def _make_sequence_and_version(firm_id, version_number: int = 1):
    """Create a Sequence and one SequenceVersion. Returns (sequence, version)."""
    db = TestingSessionLocal()
    try:
        sequence = Sequence(firm_id=firm_id, name=f"Test Sequence v{version_number}")
        db.add(sequence)
        db.flush()

        version = SequenceVersion(
            sequence_id=sequence.id,
            version_number=version_number,
        )
        db.add(version)
        db.commit()
        db.refresh(sequence)
        db.refresh(version)
        _ = sequence.id, sequence.firm_id
        _ = version.id, version.sequence_id, version.version_number
        return sequence, version
    finally:
        db.close()


def _make_second_version(sequence_id, version_number: int = 2) -> SequenceVersion:
    """Add a new SequenceVersion to an existing Sequence."""
    db = TestingSessionLocal()
    try:
        version = SequenceVersion(
            sequence_id=sequence_id,
            version_number=version_number,
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        _ = version.id, version.sequence_id, version.version_number
        return version
    finally:
        db.close()


def _make_enrollment(firm_id, lead_id, sequence_id, sequence_version_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        enrollment = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=sequence_id,
            sequence_version_id=sequence_version_id,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        _ = enrollment.id, enrollment.sequence_version_id
        return enrollment
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: Field holds correct value through a normal read cycle
# ---------------------------------------------------------------------------

class TestEnrollmentVersionPinField:
    def test_enrollment_sequence_version_id_is_set_at_creation_and_readable(self):
        """sequence_version_id is set at creation and holds its value on re-fetch.

        This is the truthful, narrow claim currently verifiable: the field
        exists, is set correctly, and survives a DB round-trip unchanged.

        Note on schema read-only enforcement: EnrollmentOut is the only
        enrollment schema (no EnrollmentCreate or EnrollmentUpdate exists),
        which means no generic CRUD endpoint can receive a caller-supplied
        sequence_version_id at all. The structural guarantee is present.
        """
        firm = _make_firm("pin-field-firm")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        enrollment = _make_enrollment(
            firm.id, lead.id, sequence.id, version.id
        )

        # Re-fetch from DB to confirm the value survives a real round-trip.
        db = TestingSessionLocal()
        try:
            fetched = db.query(Enrollment).filter(
                Enrollment.id == enrollment.id
            ).first()
            assert fetched is not None, "Enrollment not found after creation"
            assert fetched.sequence_version_id == version.id, (
                f"sequence_version_id mismatch after round-trip. "
                f"Expected {version.id}, got {fetched.sequence_version_id}"
            )
            assert fetched.sequence_id == sequence.id
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 2: Structural guard -- no code currently assigns to this field
# (THE GUARD TEST for this file)
# ---------------------------------------------------------------------------

class TestNoCodePathModifiesVersionPin:
    def test_no_code_path_currently_modifies_enrollment_sequence_version_id(self):
        """Guard: no attribute assignment to .sequence_version_id exists anywhere in app/.

        Searches the real committed source tree at test time using grep.
        If any code assigns to this field outside the model column definition,
        the test fails and names the file and line -- forcing a conscious
        decision about whether the assignment is safe.

        This test protects a guarantee that currently exists by ABSENCE
        (nothing touches the field) rather than by active enforcement. It
        turns that absence into a real, enforceable assertion that will catch
        a future regression immediately.

        Exclusions: model column definitions (which use the annotation syntax
        'sequence_version_id: Mapped[...] = mapped_column(...)') do not match
        the attribute-access pattern '.<field> =', so no exclusions are needed.
        """
        result = subprocess.run(
            [
                "grep", "-rn",
                r"\.sequence_version_id\s*=",
                "app/",
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )

        matches = [
            line for line in result.stdout.splitlines()
            if line.strip()
        ]

        assert matches == [], (
            f"Found {len(matches)} assignment(s) to .sequence_version_id in app/. "
            f"Each must be reviewed to confirm it does not violate version-pinning:\n"
            + "\n".join(f"  {m}" for m in matches)
        )


# ---------------------------------------------------------------------------
# Test 3: Creating a new SequenceVersion does not alter existing enrollments
# ---------------------------------------------------------------------------

class TestNewVersionDoesNotAlterExistingEnrollments:
    def test_creating_new_sequence_version_does_not_alter_existing_enrollment(self):
        """Existing enrollments are unaffected when a new SequenceVersion is created.

        This tests the only currently-existing operation that could conceivably
        interact with version-pinning: adding a new SequenceVersion row. It
        verifies that creating version 2 leaves an enrollment pinned to version 1
        completely unchanged.

        This would catch a regression if future code carelessly updated all
        enrollments when a new version is created, which is exactly the kind
        of mistake this guarantee exists to prevent.
        """
        firm = _make_firm("pin-version-firm")
        lead = _make_lead(firm.id)
        sequence, version_1 = _make_sequence_and_version(firm.id, version_number=1)

        enrollment = _make_enrollment(
            firm.id, lead.id, sequence.id, version_1.id
        )
        assert enrollment.sequence_version_id == version_1.id

        # Create a second version for the same sequence -- this is the real
        # operation that should not disturb existing enrollments.
        version_2 = _make_second_version(sequence.id, version_number=2)
        assert version_2.sequence_id == sequence.id
        assert version_2.version_number == 2

        # Re-fetch the original enrollment and confirm it is still pinned to v1.
        db = TestingSessionLocal()
        try:
            fetched = db.query(Enrollment).filter(
                Enrollment.id == enrollment.id
            ).first()
            assert fetched is not None, "Enrollment not found after version 2 was created"
            assert fetched.sequence_version_id == version_1.id, (
                f"Enrollment was unpinned: expected version_1.id={version_1.id}, "
                f"got {fetched.sequence_version_id}. "
                f"Creating version 2 must not alter existing enrollments."
            )
            # Confirm the enrollment was NOT silently reassigned to version 2.
            assert fetched.sequence_version_id != version_2.id, (
                "Enrollment was silently reassigned to version 2 -- "
                "this is a version-pinning violation."
            )
        finally:
            db.close()
