# app/services/firm_settings.py

"""
Retired key guard for the Firm.settings JSON blob.

One shared definition of what is retired and what the refusal says, because
three separate endpoints can write the blob and they must all refuse the same
thing with the same message.
"""

import re

from fastapi import HTTPException, status

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PORTAL_COLOR_KEYS = ("portal_colors_dark", "portal_colors_light")


def is_email_sync_enabled(firm) -> bool:
    """Whether Gmail mailbox sync may run for this firm.

    Email sync ships DISABLED by default, per the OAuth descope decision of
    August 15 2026: gmail.readonly and gmail.send were removed from the
    requested Google scope list, so a fresh authorization does not grant the
    mailbox access this feature needs.

    Absent, empty, and NULL settings all mean disabled. Only an explicit true
    turns it on, which is why this tests identity against True rather than
    truthiness: a stray non boolean in an unvalidated blob must not read as
    consent to sync a firm's mail.

    Before this existed nothing in the backend read email_sync_enabled at all.
    The toggle was written by the settings tab and consulted only by the
    frontend, which treated anything other than an explicit false as enabled.
    The sweep itself ran for every connected integration regardless.
    """
    settings = getattr(firm, "settings", None) or {}
    return settings.get("email_sync_enabled") is True


# Keys that may no longer be written into the settings blob through any door.
#
# fee_schedule was retired on August 15 2026. Firm pricing moved to the service
# catalog and the firm scoped pricing tables, which can express things the blob
# never could: unpriced versus priced at zero as physically distinct states.
#
# This is a BLOCKLIST, not a whitelist. Only the keys named here are refused;
# the two dozen other keys the settings blob carries continue to flow exactly as
# they did before. A whitelist would have broken all of them.
RETIRED_SETTINGS_KEYS = ("fee_schedule",)


RETIRED_KEY_DETAIL = (
    "fee_schedule is retired and can no longer be written to firm settings. "
    "Firm pricing now lives in the fee schedule system: the service catalog and "
    "the firm scoped pricing tables. See GET /api/pricing/config."
)


def reject_retired_settings_keys(settings) -> None:
    """Refuse a settings payload that carries a retired key.

    Loud by design. An explicit 422 naming the retirement, never a silent strip:
    a caller still writing fee_schedule needs to find out, rather than being
    told the save succeeded while nothing was written.

    Callers must invoke this BEFORE any side effect, not just before the write.
    The settings update path deletes superseded S3 logo objects, so a check
    placed after that would let a refused payload still destroy a firm's logo.

    Matches exact top level keys only. A key that merely contains a retired name
    (fee_schedule_migrated_at) is not itself retired.

    Accepts None or an empty dict and does nothing, so callers do not need to
    guard the call site.
    """
    if not settings:
        return

    for key in RETIRED_SETTINGS_KEYS:
        if key in settings:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=RETIRED_KEY_DETAIL,
            )

def validate_portal_color_settings(payload: dict) -> None:
    """Reject portal color payloads containing non-hex color values.

    Color values are injected as raw CSS property values in the client portal.
    Allowing arbitrary strings would expose a CSS-injection vector in a
    multi-tenant context. Only canonical 6-digit hex values (#rrggbb) pass.

    Accepts None or an empty dict and does nothing.
    """
    if not payload:
        return

    for key in _PORTAL_COLOR_KEYS:
        color_map = payload.get(key)
        if color_map is None:
            continue
        if not isinstance(color_map, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{key} must be an object mapping color names to hex strings.",
            )
        bad = [
            f"{k}: {v!r}"
            for k, v in color_map.items()
            if not isinstance(v, str) or not _HEX_RE.match(v)
        ]
        if bad:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid color values in {key}: {', '.join(bad)}. "
                    "Each color must be a 6-digit hex string such as #1F3148."
                ),
            )
