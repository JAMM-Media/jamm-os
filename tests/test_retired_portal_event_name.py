# tests/test_retired_portal_event_name.py

"""
Tripwire: the retired portal.invoice_paid event name must not come back.

Renamed to portal.payment_initiated on Sep 22, 2026, because the event fires
at Stripe payment intent creation, when the client starts a payment, and not
when money arrives. Invoice Payment Time computes from invoice.paid alone.

behavioral_events is append-only, so rows written before the rename keep the
old name forever. That is deliberate, and it is why this scan is source text
only: it is about what the code can write from here on, not about what is
already in the log.

Scope is app/ and scripts/. tests/ is excluded on purpose, since a test may
legitimately seed a historical row under the old name, and this file itself
has to spell the retired name out in order to look for it.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Assembled rather than written out, so this constant is not itself an
# occurrence of the literal a sloppier scan would then find.
RETIRED_EVENT_NAME = "portal." + "invoice_paid"
CURRENT_EVENT_NAME = "portal.payment_initiated"

SCANNED_DIRS = ("app", "scripts")


def _python_sources() -> list[Path]:
    paths: list[Path] = []
    for directory in SCANNED_DIRS:
        for path in sorted((_REPO_ROOT / directory).rglob("*.py")):
            # __pycache__ holds compiled copies of the same sources; scanning
            # them would report a stale hit for a string the .py no longer has.
            if "__pycache__" in path.parts:
                continue
            paths.append(path)
    return paths


def test_there_are_sources_to_scan():
    """A scan over an empty file list passes for the wrong reason. 450 files
    at the time of writing; the floor is deliberately far below that so an
    ordinary deletion does not turn this red."""
    assert len(_python_sources()) > 100


def test_retired_event_name_appears_nowhere_under_app_or_scripts():
    offenders = [
        str(path.relative_to(_REPO_ROOT))
        for path in _python_sources()
        if RETIRED_EVENT_NAME in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"these files still carry the retired event name {RETIRED_EVENT_NAME!r}, "
        f"which became {CURRENT_EVENT_NAME!r} on Sep 22, 2026: {offenders}"
    )


def test_the_current_event_name_is_emitted_and_read():
    """The other half of the rename. If portal_service stopped firing the event
    altogether, the scan above would be green while the portal utilization
    metric silently lost its numerator."""
    carriers = {
        str(path.relative_to(_REPO_ROOT)).replace("\\", "/")
        for path in _python_sources()
        if CURRENT_EVENT_NAME in path.read_text(encoding="utf-8")
    }
    assert "app/services/portal_service.py" in carriers
    assert "app/services/metric_compute.py" in carriers
