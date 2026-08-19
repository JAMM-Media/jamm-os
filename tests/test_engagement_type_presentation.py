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

THE TWO MAPS ARE GUARDED BY OPPOSITE RULES, AND THAT IS THE MOST IMPORTANT
THING IN THIS FILE.

    ENGAGEMENT_TYPE_CATEGORIES  must be COMPLETE. Guarded here.
    LEAD_FACING_LABELS          must NOT be. Deliberately unguarded.

They started under one shared rule on August 18, 2026: both shipped empty, both
unguarded, absence treated as a harmless default in each. That held for exactly
as long as it took docs/Public_Intake_Form_Structure_Contract_v1.md to land the
same day and make category a ROUTING field. Step 1 of the intake form offers
three fixed answers (Tax / Bookkeeping / Advisory); Step 2 shows only the firm's
active engagement types IN THE CHOSEN CATEGORY; there is no flat list anywhere
in that spine. A type with no category therefore belongs to no Step 1 bucket and
cannot be reached by any lead, which is a bug that produces a dead form rather
than an error. Nothing goes red on its own, because an uncategorized service is
a perfectly valid payload.

So the rule split, and the thing that decides which side a map falls on is its
FALLBACK, not its importance. A missing lead-facing label degrades to a formal
label that always exists and that a lead can still read. A missing category
degrades to nothing. One is cosmetic, the other is a dead end.

This is process rule 9 in its ordinary form: the rule changed on purpose, so
the tests encoding the old one changed with it in the same commit. A
completeness test for LEAD_FACING_LABELS would now be asserting the retired
shared rule and would fail on a state that is deliberate, which is why its
absence from this file is load-bearing rather than an oversight.

ON VACUITY, STATED PLAINLY BECAUSE IT MATTERS. The four per-entry tests below
iterate over whatever the maps contain. Now that ENGAGEMENT_TYPE_CATEGORIES is
populated they examine 43 real values, but the two aimed at LEAD_FACING_LABELS
still iterate over nothing and pass without examining anything, which is
instance nine and fourteen's shape: a watcher that is not watching,
indistinguishable from a healthy one. They are kept anyway, so the content
session lands on top of a guard instead of writing one afterwards, and every
test in this file was watched red against deliberately bad content before being
accepted. The proof they can fail is in the session report, not in their green.

test_service_category_has_exactly_the_ruled_values below has never been vacuous
and never will be. It fails the moment somebody adds a fourth bucket without a
ruling.
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


def test_every_engagement_type_has_a_category():
    """COMPLETENESS. Every EngagementType member is reachable through Step 1.

    This is the test the structure contract created. Category is a routing
    field: Step 1 offers Tax / Bookkeeping / Advisory and Step 2 shows only the
    active types in the chosen bucket, so a member missing from this map sits in
    no bucket and no lead can ever select it. The firm switched the service on,
    the endpoint serves it with a null category, every existing test stays
    green, and the service is simply unsellable through the funnel.

    That failure is invisible from every direction except this one. It is not an
    exception, not a 500, and not a malformed payload; it is a correct response
    describing a service nobody can get to. This test is the only thing that
    turns it into a red line.

    Watched red before being accepted: one entry removed from the map, confirmed
    red naming that exact member, restored, re-run green. Recorded in the
    session report.

    DELIBERATELY NOT MIRRORED FOR LEAD_FACING_LABELS. See the module docstring:
    that map's absences fall back to a label that always exists, so completeness
    there would be asserting a rule that was retired on purpose.
    """
    missing = sorted(
        member.name
        for member in EngagementType
        if member not in ENGAGEMENT_TYPE_CATEGORIES
    )
    assert not missing, (
        f"{len(missing)} engagement type(s) have no category and are therefore "
        f"unreachable through the intake form's Step 1 routing: {missing}. "
        "Every member needs a bucket, because there is no flat list in the "
        "locked four-step spine."
    )


def test_every_engagement_type_has_a_category_and_a_label_together():
    """The two maps that must agree, checked against each other.

    A type reachable at Step 1 has to render at Step 2. Completeness of the
    category map and completeness of the canonical label map are separately
    enforced (here and in tests/test_engagement_type_canon.py), and this asserts
    the intersection actually holds rather than trusting that two independent
    guards imply it.
    """
    unrenderable = sorted(
        member.name
        for member in EngagementType
        if member in ENGAGEMENT_TYPE_CATEGORIES
        and member not in ENGAGEMENT_TYPE_LABELS
    )
    assert not unrenderable, (
        f"These types route at Step 1 but have no label to render at Step 2: "
        f"{unrenderable}"
    )


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
