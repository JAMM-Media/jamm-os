# tests/test_engagement_type_canon.py
"""
Coverage guards for the engagement type canon.

The canon is defined in three places that must stay in lockstep:
the EngagementType enum, the ENGAGEMENT_TYPE_LABELS display map, and
the TAX_DEADLINES filing deadline map. Nothing in the application
fails loudly when they drift, so these tests are the only thing that
catches a member added to one and forgotten in the others.
"""

from app.core.enums import EngagementType, ENGAGEMENT_TYPE_LABELS
from app.core.tax_deadlines import TAX_DEADLINES


def test_engagement_type_canon_has_43_members():
    assert len(EngagementType) == 43


def test_every_engagement_type_has_display_label():
    """
    Direct bracket access on purpose. Using .get here would turn a
    missing label into a silent None and defeat the point of the guard.
    """
    for member in EngagementType:
        label = ENGAGEMENT_TYPE_LABELS[member]
        assert isinstance(label, str)
        assert label.strip() != ""


def test_every_engagement_type_has_explicit_deadline_entry():
    """
    get_filing_deadline uses .get and returns None for unknown types, so a
    type missing from TAX_DEADLINES behaves exactly like a type with no
    filing deadline and produces no error anywhere in the app. An explicit
    membership check is the only way to tell those two states apart.
    """
    for member in EngagementType:
        assert member in TAX_DEADLINES, f"{member.value} is missing from TAX_DEADLINES"
