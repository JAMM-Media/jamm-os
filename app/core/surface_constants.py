# app/core/surface_constants.py

"""
Authored constants and lifecycle registries for the surface_items engine
(the Morning Briefing and the Observatory).

Every value in this file is Andrew-owned and changed only by his decision,
matching the posture of app/core/intelligence_constants.py and
app/core/technique_floors.py.

Ratchet rule: tightening any threshold here is allowed without sign-off.
Loosening any threshold requires an explicit manual decision by Andrew after
review.

The day-one thresholds are deliberately round numbers. They are authored
judgement rather than measured values, and they live in one place so a later
session can move them against real data instead of hunting for them inline in
the generators.
"""

import copy

# --- Briefing display -------------------------------------------------

# Andrew-owned. Hard cap on the Active section of the Briefing. The daily job
# slots this many briefing rows; everything else stays active but unslotted
# until it ranks its way in or the owner asks for one more.
BRIEFING_ACTIVE_CAP = 5

# --- Suppression windows ----------------------------------------------

# Andrew-owned. Counted from the click, not from the start of the day, for
# both already_handling and mark_implemented. Briefing items move on a daily
# rhythm; Observatory signals stand for weeks, so their window is longer.
BRIEFING_SUPPRESSION_DAYS = 7
OBSERVATORY_SUPPRESSION_DAYS = 14

# --- Generator thresholds ---------------------------------------------

# Andrew-owned. An IRS authorization inside this many days of valid_until is
# worth the owner's morning attention.
IRS_AUTH_WINDOW_DAYS = 21

# Andrew-owned. An envelope still reading sent this many days after sent_at
# is stalled. Envelopes that reached a real ending (declined, expired) fire
# their own item types on the day the ending lands and carry no threshold.
SIGNATURE_STALLED_DAYS = 5

# Andrew-owned. An engagement deadline inside this many days, with at least
# one open prerequisite, is a Tier 1 item.
DEADLINE_WINDOW_DAYS = 14

# Andrew-owned. An engagement completed this many days ago with no invoice
# raised against it is unbilled work.
UNBILLED_DAYS = 7

# Deliberately absent, ruled September 1, 2026: DOC_REQUEST_STALLED_DAYS and
# CLIENT_QUIET_DAYS. Their generators (doc_request_stalled, client_quiet) are
# deferred, not dropped, and neither is implementable against operational
# tables today. doc_request_stalled needs per-item checklist timestamps, which
# do not exist; client_quiet needs client-attributable upload activity, which
# the documents table cannot express today. Do not restore these constants
# without their generators.

# --- Per-technique lifecycle registries --------------------------------

# Andrew-owned. Keyed by Finding.technique, exactly like FLOORS_BY_TECHNIQUE
# in app/core/technique_floors.py.
#
# Every entry is authored per technique against measured data, never guessed,
# in the build session that creates the technique. Thresholds may tighten
# freely; loosening any of them is a manual decision reserved to Andrew after
# review.
#
# While a technique is ABSENT from a registry the promotion path is inert for
# it: it fails closed and no surface row is written. All three ship empty
# because no ML technique exists yet, which is what makes the promotion path
# fully inert on day one. That emptiness is the safety property, not an
# oversight, and filling one in before there is measured data to author it
# against is exactly what the ratchet rule forbids.

# Minimum severity_score a gated finding must carry before it may be promoted
# to an Observatory row.
PROMOTION_SEVERITY_THRESHOLDS: dict[str, float] = {}

# Margin a rival finding must beat an incumbent by before it displaces it,
# so a surfaced signal does not flicker in and out on noise.
DISPLACEMENT_HYSTERESIS_MARGINS: dict[str, float] = {}

# Consecutive rechecks a finding must read as resolved before its surface row
# echoes the resolution.
RESOLUTION_SUSTAIN_COUNTS: dict[str, int] = {}


def get_promotion_severity_thresholds() -> dict[str, float]:
    """
    Returns a deep copy of the registry.

    A copy rather than the live dict so no caller can mutate Andrew-owned
    numbers at runtime, by accident or otherwise.
    """
    return copy.deepcopy(PROMOTION_SEVERITY_THRESHOLDS)


def get_displacement_hysteresis_margins() -> dict[str, float]:
    """Returns a deep copy of the registry. See the note above on copies."""
    return copy.deepcopy(DISPLACEMENT_HYSTERESIS_MARGINS)


def get_resolution_sustain_counts() -> dict[str, int]:
    """Returns a deep copy of the registry. See the note above on copies."""
    return copy.deepcopy(RESOLUTION_SUSTAIN_COUNTS)
