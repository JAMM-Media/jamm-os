# tests/test_lead_attribution.py

"""Tests for app/services/lead_attribution.py, the three pure UTM derivations.

Rulings R4 (placement), R5 (referral_source) and R6 (module layout), Sep 17,
2026; Metric Clock Definitions v2 Sections 1 and 5.

These functions take strings and return enum members. No database, no
fixtures, no client -- if any test here needs a Session, something has been
built in the wrong place.
"""

import inspect

import pytest

from app.core.enums import ReferralSource, SourcePlacement, SourcePlatform
from app.services import lead_attribution
from app.services.lead_attribution import (
    derive_referral_source,
    derive_source_placement,
    derive_source_platform,
)


# ---------------------------------------------------------------------------
# derive_source_placement (R4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("placement", list(SourcePlacement))
def test_every_placement_value_resolves_from_utm_content(placement):
    """All twelve SourcePlacement values resolve from utm_content by their own name.

    in_stream is included and is the interesting one: the underscore is a
    split character, so "in_stream" arrives as the two tokens ("in",
    "stream") and only survives because of the adjacent-token join.
    """
    assert derive_source_placement(placement.value, None, None) == placement


def test_all_twelve_values_are_covered_by_the_parametrize():
    """Guard on the guard above: if a thirteenth value is added, the
    parametrized test grows with it rather than silently covering eleven."""
    assert len(list(SourcePlacement)) == 12


@pytest.mark.parametrize(
    "token,expected",
    [
        ("stories", SourcePlacement.story),
        ("storie", SourcePlacement.story),
        ("reel", SourcePlacement.reels),
        ("short", SourcePlacement.shorts),
        ("newsfeed", SourcePlacement.feed),
        ("instream", SourcePlacement.in_stream),
        ("in-stream", SourcePlacement.in_stream),
        ("msg", SourcePlacement.messaging),
        ("messenger", SourcePlacement.messaging),
    ],
)
def test_every_alias_resolves(token, expected):
    """Each alias in the ruling's table, including both spellings of in_stream."""
    assert derive_source_placement(token, None, None) == expected


def test_scan_order_content_beats_term_beats_medium():
    """utm_content is scanned first, so it wins outright over a resolving medium.

    This is the ruling's own example: medium=video would resolve to video on
    its own, and must not, because utm_content already answered reels.
    """
    assert derive_source_placement("springpromo_reels", None, "video") == SourcePlacement.reels
    # term beats medium when content says nothing
    assert derive_source_placement(None, "shorts", "video") == SourcePlacement.shorts
    # medium is reached only when neither of the first two resolves
    assert derive_source_placement("springpromo", "brandterm", "video") == SourcePlacement.video


def test_first_resolving_token_within_a_field_wins():
    """Within one field the leftmost resolving token decides."""
    assert derive_source_placement("feed_and_reels", None, None) == SourcePlacement.feed


def test_unrecognized_content_gives_none():
    assert derive_source_placement("springpromo", None, None) is None


def test_all_fields_none_gives_none():
    assert derive_source_placement(None, None, None) is None


def test_all_fields_empty_string_gives_none():
    assert derive_source_placement("", "", "") is None


def test_utm_source_is_never_read():
    """A utm_source of "reels" cannot produce a placement.

    Asserted structurally rather than behaviorally. The function takes no
    utm_source parameter at all, so there is no call that could pass one --
    checking the signature is the only way to make this claim capable of
    failing (process rules instance eighteen: a test asserting a leak that
    the setup forbids proves nothing). If someone adds the parameter, this
    goes red immediately, before any behavior depends on it.
    """
    params = list(inspect.signature(derive_source_placement).parameters)
    assert params == ["utm_content", "utm_term", "utm_medium"]
    assert "utm_source" not in params
    # And the behavioral half: a lead whose only tag is utm_source=reels has
    # nothing for the three scanned fields to find.
    assert derive_source_placement(None, None, None) is None


def test_placement_resolves_independently_of_platform():
    """A placement is stored even when source_platform is None (R4).

    The two derivations never consult each other; this pins that they are
    separate observations rather than one gated on the other.
    """
    assert derive_source_platform(None) is None
    assert derive_source_placement("reels", None, None) == SourcePlacement.reels


# ---------------------------------------------------------------------------
# derive_referral_source (R5)
# ---------------------------------------------------------------------------

def _referral(platform, medium, **utm):
    """Call helper: platform and medium are the two that matter, and a
    utm_source is supplied by default so the all-empty website branch is not
    hit by accident."""
    return derive_referral_source(
        platform,
        utm.get("utm_source", "sometag"),
        medium,
        utm.get("utm_campaign"),
        utm.get("utm_content"),
        utm.get("utm_term"),
    )


@pytest.mark.parametrize("platform", [SourcePlatform.google, SourcePlatform.bing])
def test_paid_on_search_is_search_ads(platform):
    assert _referral(platform, "cpc") == ReferralSource.search_ads


@pytest.mark.parametrize("platform", [SourcePlatform.google, SourcePlatform.bing])
def test_organic_on_search_is_google_search(platform):
    """google_search is the ruled mapping for organic search on BOTH search
    platforms. ReferralSource has no bing_search value, so organic Bing is
    deliberately reported as google_search rather than dropped."""
    assert _referral(platform, "organic") == ReferralSource.google_search


@pytest.mark.parametrize(
    "platform",
    [
        SourcePlatform.facebook,
        SourcePlatform.instagram,
        SourcePlatform.tiktok,
        SourcePlatform.linkedin,
        SourcePlatform.youtube,
        SourcePlatform.x,
        SourcePlatform.nextdoor,
    ],
)
def test_paid_on_social_is_social_ads(platform):
    assert _referral(platform, "paid_social") == ReferralSource.social_ads


@pytest.mark.parametrize(
    "platform",
    [
        SourcePlatform.facebook,
        SourcePlatform.instagram,
        SourcePlatform.tiktok,
        SourcePlatform.linkedin,
        SourcePlatform.youtube,
        SourcePlatform.x,
        SourcePlatform.nextdoor,
    ],
)
def test_organic_on_social_is_social_media(platform):
    assert _referral(platform, "social") == ReferralSource.social_media


@pytest.mark.parametrize("medium", ["cpc", "ppc", "cpm", "paid", "paidsocial", "ads", "display"])
def test_every_paid_medium_token_reads_as_paid(medium):
    assert _referral(SourcePlatform.instagram, medium) == ReferralSource.social_ads


@pytest.mark.parametrize("medium", ["organic", "social", "referral"])
def test_every_organic_medium_token_reads_as_organic(medium):
    assert _referral(SourcePlatform.instagram, medium) == ReferralSource.social_media


def test_paid_social_tokenizes_to_paid_not_social():
    """"paid_social" splits into ("paid", "social"), one token from each set.

    Order decides: "paid" is reached first, so the medium is paid. If the
    scan ever flipped to checking organic first this would read as
    social_media, which is the wrong answer for a paid campaign.
    """
    assert _referral(SourcePlatform.instagram, "paid_social") == ReferralSource.social_ads
    assert _referral(SourcePlatform.instagram, "paid-social") == ReferralSource.social_ads


def test_medium_absent_gives_none():
    """A medium nobody set means paid-versus-organic is not knowable."""
    assert _referral(SourcePlatform.instagram, None) is None
    assert _referral(SourcePlatform.google, "") is None


def test_unrecognized_medium_gives_none():
    """A medium with no token in either set means not known, never a guess."""
    assert _referral(SourcePlatform.instagram, "banner") is None
    assert _referral(SourcePlatform.google, "newsletter") is None


@pytest.mark.parametrize(
    "platform",
    [
        SourcePlatform.email,
        SourcePlatform.phone,
        SourcePlatform.dm,
        SourcePlatform.direct_mail,
        SourcePlatform.other,
    ],
)
def test_excluded_platforms_always_give_none(platform):
    """email, phone, dm and direct_mail belong to the cold_outreach mechanism
    and other means unclassified. None of them supports a Layer 1 answer, and
    a paid medium does not rescue them."""
    assert _referral(platform, "cpc") is None
    assert _referral(platform, "organic") is None


def test_all_five_utm_fields_empty_is_website():
    """A visitor who reached the public form with no tracked link is website."""
    assert derive_referral_source(None, None, None, None, None, None) == ReferralSource.website
    assert derive_referral_source(None, "", "", "", "", "") == ReferralSource.website


def test_any_utm_present_with_no_platform_gives_none():
    """One stray UTM tag is enough to leave the website branch, and with no
    platform behind it there is nothing to derive."""
    assert derive_referral_source(None, None, None, "spring_promo", None, None) is None
    assert derive_referral_source(None, None, "cpc", None, None, None) is None
    assert derive_referral_source(None, None, None, None, "creative_a", None) is None


def test_website_requires_all_five_empty_not_just_source():
    """The website answer is about the whole tag set, not utm_source alone.

    Pins the boundary between the two branches: drop any one field from the
    all-empty case and the answer must stop being website.
    """
    assert derive_referral_source(None, None, None, None, None, "term") is None


# ---------------------------------------------------------------------------
# derive_source_platform (R6: moved, behavior unchanged)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "utm_source,expected",
    [
        ("facebook", SourcePlatform.facebook),
        ("fb", SourcePlatform.facebook),
        ("instagram", SourcePlatform.instagram),
        ("ig", SourcePlatform.instagram),
        ("tiktok", SourcePlatform.tiktok),
        ("linkedin", SourcePlatform.linkedin),
        ("youtube", SourcePlatform.youtube),
        ("x", SourcePlatform.x),
        ("twitter", SourcePlatform.x),
        ("google", SourcePlatform.google),
        ("bing", SourcePlatform.bing),
        ("nextdoor", SourcePlatform.nextdoor),
    ],
)
def test_known_utm_sources_map_to_their_platform(utm_source, expected):
    assert derive_source_platform(utm_source) == expected


def test_case_and_whitespace_insensitive():
    assert derive_source_platform(" Facebook ") == SourcePlatform.facebook


def test_unrecognized_non_empty_utm_source_is_other_not_none():
    """The case the old docstring got wrong.

    A non-empty utm_source that matches nothing returns SourcePlatform.other,
    because the lead did arrive through a tracked link. The docstring in
    app/api/intake.py used to claim None here while the code returned other;
    the docstring was corrected when the function moved (R6).
    """
    assert derive_source_platform("some_random_platform") == SourcePlatform.other


def test_absent_or_blank_utm_source_is_none():
    assert derive_source_platform(None) is None
    assert derive_source_platform("") is None


@pytest.mark.parametrize("reserved", ["email", "phone", "dm", "direct_mail"])
def test_cold_outreach_values_are_not_producible_from_utm(reserved):
    """The four reserved cold_outreach mechanisms never come out of a UTM tag.

    They describe how a cold_outreach lead was contacted, not a web platform.
    A tracked link claiming utm_source=email gets other.
    """
    assert derive_source_platform(reserved) == SourcePlatform.other


def test_intake_alias_points_at_the_moved_function():
    """R6: app/api/intake.py keeps _derive_source_platform as a module-level
    alias so any existing import of the old private name keeps working."""
    from app.api import intake

    assert intake._derive_source_platform is derive_source_platform


def test_module_exposes_all_three_derivations():
    """R6: all three live in one module."""
    for name in ("derive_source_platform", "derive_source_placement", "derive_referral_source"):
        assert hasattr(lead_attribution, name), f"{name} is missing from lead_attribution"
