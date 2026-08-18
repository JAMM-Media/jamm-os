# tests/test_engagement_type_presentation.py

"""Guards for the two presentation maps added August 18, 2026.

LEAD_FACING_LABELS and ENGAGEMENT_TYPE_CATEGORIES are system-shared content
living in app/core/enums.py rather than in a table, by Andrew's August 18, 2026
placement ruling. That ruling bought simplicity and cost the two things a
database would have enforced for free:

    a FOREIGN KEY, which would have refused a key that is not a real
    engagement type
    a CHECK or sa.Enum, which would have refused a category outside the
    three ruled values

This file is what replaces both. It is the only thing standing between a typo
in the catalog content session and a payload served to anonymous visitors.

ON VACUITY, STATED PLAINLY BECAUSE IT MATTERS. Both maps ship EMPTY today, so
the four per-entry tests below currently iterate over nothing and pass without
examining a single value. That is instance nine and fourteen's shape: a watcher
that is not watching, indistinguishable from a healthy one. They are written
now anyway, so the content session lands on top of a guard instead of writing
one afterwards, and each was watched red against a deliberately bad entry
before being accepted. The proof they are capable of failing is in the session
report, not in their current green.

test_service_category_has_exactly_the_ruled_values below is NOT vacuous today
and never will be. It is the one test here that fails the moment somebody adds
a fourth bucket without a ruling.
"""

from app.core.enums import (
    ENGAGEMENT_TYPE_CATEGORIES,
    ENGAGEMENT_TYPE_LABELS,
    LEAD_FACING_LABELS,
    EngagementType,
    ServiceCategory,
)


def test_service_category_has_exactly_the_ruled_values():
    """tax, bookkeeping, advisory. Ruled by Andrew, August 18, 2026.

    Ben's intake form groups services by this string, so adding a fourth bucket
    silently produces a section his form has no heading for. Changing this set
    is a product decision and this test is the place it gets made deliberately
    rather than by accident.
    """
    assert [category.value for category in ServiceCategory] == [
        "tax",
        "bookkeeping",
        "advisory",
    ]


def test_every_lead_facing_label_key_is_a_real_engagement_type():
    """A key that is not an EngagementType member is dead content.

    It would never be looked up, because the service resolves the stored string
    to an enum member before reading the map, so a typo here fails silently and
    forever: the type simply keeps serving its canonical label and nobody can
    tell the override was meant to exist.
    """
    strays = [key for key in LEAD_FACING_LABELS if not isinstance(key, EngagementType)]
    assert not strays, (
        f"LEAD_FACING_LABELS has keys that are not EngagementType members: "
        f"{strays}. These will never be read."
    )


def test_every_lead_facing_label_is_a_usable_string():
    """Empty or whitespace-only defeats the fallback in the worst way.

    The fallback fires on a MISSING key, not on a useless value, so an entry of
    "" would serve a lead an unnamed service rather than falling back to the
    canonical label. Present-but-empty is not absent, which is the same trap as
    instance sixteen one layer up.
    """
    bad = [
        (key, value)
        for key, value in LEAD_FACING_LABELS.items()
        if not isinstance(value, str) or not value.strip()
    ]
    assert not bad, (
        f"LEAD_FACING_LABELS has entries that are not usable display strings: "
        f"{bad}. An empty override does not fall back; it serves the empty "
        "string to a lead."
    )


def test_every_category_key_is_a_real_engagement_type():
    """Same dead-content failure as the label map, same reasoning."""
    strays = [
        key for key in ENGAGEMENT_TYPE_CATEGORIES if not isinstance(key, EngagementType)
    ]
    assert not strays, (
        f"ENGAGEMENT_TYPE_CATEGORIES has keys that are not EngagementType "
        f"members: {strays}. These will never be read."
    )


def test_every_category_value_is_a_service_category_member():
    """THE REPLACEMENT FOR THE sa.Enum COLUMN CONSTRAINT.

    The category was specified as a database enum before the placement ruling
    moved it into code. Nothing at runtime refuses a bare string here, so a
    value of "Tax" or "advisroy" would serialize straight into the public
    payload and reach Ben's form as an unknown bucket.
    """
    bad = [
        (key, value)
        for key, value in ENGAGEMENT_TYPE_CATEGORIES.items()
        if not isinstance(value, ServiceCategory)
    ]
    assert not bad, (
        f"ENGAGEMENT_TYPE_CATEGORIES has values outside ServiceCategory: {bad}. "
        "Use the enum member, not a bare string."
    )


def test_the_label_fallback_target_covers_every_type_a_category_names():
    """Every type these maps mention can always render.

    lead_facing_label falls back to ENGAGEMENT_TYPE_LABELS, which
    tests/test_engagement_type_canon.py keeps complete. This asserts the two
    maps cannot name a type that the fallback cannot serve, which is what makes
    "absence is the designed default" safe to rely on.
    """
    mentioned = set(LEAD_FACING_LABELS) | set(ENGAGEMENT_TYPE_CATEGORIES)
    missing = [key for key in mentioned if key not in ENGAGEMENT_TYPE_LABELS]
    assert not missing, (
        f"These types are named by a presentation map but have no canonical "
        f"label to fall back to: {missing}"
    )
