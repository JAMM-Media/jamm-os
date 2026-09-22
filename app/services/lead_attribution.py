# app/services/lead_attribution.py

"""Pure derivation of a lead's attribution fields from its UTM tags.

Metric Clock Definitions v2 Section 1 describes attribution as layers:
Layer 1 is referral_source, the how-they-found-us bucket the firm reports on;
Layer 2 is source_platform (the where) and source_placement (the
where-within-the-platform). Section 5 rules how the layers are derived from
UTM tags, and this module is that ruling in code.

Everything here is a pure function: no Session, no I/O, no clock. Each one
takes raw UTM strings and returns an enum member or None. Callers decide
what to do with None -- these functions never overwrite anything themselves,
and Layer 1 in particular fills an empty value only (Section 5), which is
the caller's rule to apply, not this module's.

Derivation runs at public intake creation only. Staff edits to UTM fields on
an existing lead do not re-derive anything (ruled Sep 17, 2026, R7).
"""

import re
from typing import Optional

from app.core.enums import ReferralSource, SourcePlacement, SourcePlatform

# Split on any run of non-alphanumeric characters. Shared by all three
# derivations so "Paid_Social", "paid-social" and "paid social" tokenize
# identically.
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _tokenize(value: Optional[str]) -> list[str]:
    """Lowercase, then split on any run of non-alphanumeric characters."""
    if not value:
        return []
    return [t for t in _TOKEN_SPLIT.split(value.strip().lower()) if t]


# ---------------------------------------------------------------------------
# Layer 2: source_platform (the where)
# ---------------------------------------------------------------------------

_PLATFORM_BY_UTM_SOURCE = {
    "facebook": SourcePlatform.facebook,
    "fb": SourcePlatform.facebook,
    "instagram": SourcePlatform.instagram,
    "ig": SourcePlatform.instagram,
    "tiktok": SourcePlatform.tiktok,
    "linkedin": SourcePlatform.linkedin,
    "youtube": SourcePlatform.youtube,
    "x": SourcePlatform.x,
    "twitter": SourcePlatform.x,
    "google": SourcePlatform.google,
    "bing": SourcePlatform.bing,
    "nextdoor": SourcePlatform.nextdoor,
}


def derive_source_platform(utm_source: Optional[str]) -> Optional[SourcePlatform]:
    """Auto-derive SourcePlatform from a raw utm_source string.

    Per Acquisition Tracker section 3.1 Layer 2: auto-derived from utm_source
    whenever a lead arrives through a tracked link. Returns None only when
    utm_source is absent or blank; a non-empty value that matches no known
    platform returns SourcePlatform.other, because the lead did arrive
    through a tracked link and other is the honest bucket for it. Callers
    must not overwrite an existing manually-picked value with None.

    Deliberately excludes email, phone, dm, and direct_mail: those four
    SourcePlatform values are reserved for the cold_outreach mechanism per
    the enum's own docstring and must never be produced from a UTM tag.
    """
    if not utm_source:
        return None
    normalized = utm_source.strip().lower()
    return _PLATFORM_BY_UTM_SOURCE.get(normalized, SourcePlatform.other)


# ---------------------------------------------------------------------------
# Layer 2: source_placement (the where-within-the-platform)
# ---------------------------------------------------------------------------

# Aliases only. Every SourcePlacement value already resolves by its own name,
# except in_stream, which cannot: the underscore is a split character, so the
# token "in_stream" never survives tokenization. It is reached by the
# "instream" alias below and by the adjacent-token join in _placement_from.
_PLACEMENT_ALIASES = {
    "stories": SourcePlacement.story,
    "storie": SourcePlacement.story,
    "reel": SourcePlacement.reels,
    "short": SourcePlacement.shorts,
    "newsfeed": SourcePlacement.feed,
    "instream": SourcePlacement.in_stream,
    "msg": SourcePlacement.messaging,
    "messenger": SourcePlacement.messaging,
}

_PLACEMENT_BY_VALUE = {p.value: p for p in SourcePlacement}


def _placement_from(value: Optional[str]) -> Optional[SourcePlacement]:
    """First token of one field that resolves to a placement, else None."""
    tokens = _tokenize(value)
    for i, token in enumerate(tokens):
        # "in-stream" and "in stream" tokenize to two tokens, so the pair is
        # rejoined here. Checked before the single-token rules because "in"
        # on its own resolves to nothing.
        if token == "in" and i + 1 < len(tokens) and tokens[i + 1] == "stream":
            return SourcePlacement.in_stream
        if token in _PLACEMENT_ALIASES:
            return _PLACEMENT_ALIASES[token]
        if token in _PLACEMENT_BY_VALUE:
            return _PLACEMENT_BY_VALUE[token]
    return None


def derive_source_placement(
    utm_content: Optional[str],
    utm_term: Optional[str],
    utm_medium: Optional[str],
) -> Optional[SourcePlacement]:
    """Derive the placement by scanning utm_content, then utm_term, then utm_medium.

    The scan order is the ruling (Sep 17, 2026, R4) and is load-bearing: the
    first field that resolves wins outright, so a campaign tagged
    utm_medium=video with utm_content=springpromo_reels is reels, not video.
    Within a field, the first token that resolves wins.

    utm_source is never read. Placement lives inside a platform, and the
    platform field already carries what utm_source says; reading it here
    would let a bare platform name masquerade as a placement.

    Returns None when nothing resolves. A placement is stored even when
    source_platform is None, because the two are independent observations.
    """
    for field in (utm_content, utm_term, utm_medium):
        placement = _placement_from(field)
        if placement is not None:
            return placement
    return None


# ---------------------------------------------------------------------------
# Layer 1: referral_source (the how-they-found-us bucket)
# ---------------------------------------------------------------------------

_PAID_MEDIUM_TOKENS = {
    "cpc",
    "ppc",
    "cpm",
    "paid",
    "paid_social",
    "paidsocial",
    "ads",
    "display",
}

_ORGANIC_MEDIUM_TOKENS = {"organic", "social", "referral"}

_SEARCH_PLATFORMS = {SourcePlatform.google, SourcePlatform.bing}

_SOCIAL_PLATFORMS = {
    SourcePlatform.facebook,
    SourcePlatform.instagram,
    SourcePlatform.tiktok,
    SourcePlatform.linkedin,
    SourcePlatform.youtube,
    SourcePlatform.x,
    SourcePlatform.nextdoor,
}


def _medium_is_paid(utm_medium: Optional[str]) -> Optional[bool]:
    """True for paid, False for organic, None when the medium says neither.

    Tokens are scanned in order and the first one that lands in either set
    decides, which is what makes paid_social paid: it tokenizes to
    ("paid", "social"), and "paid" is reached first. None means the medium
    is not known, never "assume organic".
    """
    for token in _tokenize(utm_medium):
        if token in _PAID_MEDIUM_TOKENS:
            return True
        if token in _ORGANIC_MEDIUM_TOKENS:
            return False
    return None


def derive_referral_source(
    source_platform: Optional[SourcePlatform],
    utm_source: Optional[str],
    utm_medium: Optional[str],
    utm_campaign: Optional[str],
    utm_content: Optional[str],
    utm_term: Optional[str],
) -> Optional[ReferralSource]:
    """Derive Layer 1 from the derived platform plus utm_medium (R5).

    All five UTM fields empty means the visitor reached the public intake
    form with no tracked link behind them at all, which is website.

    Otherwise the platform picks a family and the medium picks paid versus
    organic:

        search  + paid     -> search_ads
        search  + organic  -> google_search
        social  + paid     -> social_ads
        social  + organic  -> social_media

    google_search is the ruled mapping for organic search on either search
    platform, Bing included; ReferralSource has no bing_search value.

    Returns None whenever the answer is not knowable: an absent or
    unrecognized platform, one of the cold_outreach mechanisms (email,
    phone, dm, direct_mail) or other, or a medium carrying no token in
    either set. None means leave it alone -- the caller fills an empty
    value only and never overwrites.
    """
    if not any((utm_source, utm_medium, utm_campaign, utm_content, utm_term)):
        return ReferralSource.website

    if source_platform in _SEARCH_PLATFORMS:
        is_paid = _medium_is_paid(utm_medium)
        if is_paid is None:
            return None
        return ReferralSource.search_ads if is_paid else ReferralSource.google_search

    if source_platform in _SOCIAL_PLATFORMS:
        is_paid = _medium_is_paid(utm_medium)
        if is_paid is None:
            return None
        return ReferralSource.social_ads if is_paid else ReferralSource.social_media

    # Absent platform, or one of email/phone/dm/direct_mail/other. Those
    # four mechanisms belong to cold_outreach and other means unclassified,
    # so none of them supports a Layer 1 answer.
    return None
