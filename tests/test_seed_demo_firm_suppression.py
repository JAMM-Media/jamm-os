# tests/test_seed_demo_firm_suppression.py

"""
Covers the seed script's outbound-network suppression from two angles:

1. The subprocess test below runs the actual seed script as a real process
   against the real test database, rather than calling
   EmailService/automation_actions in-process. In-process, the autouse
   mock_email_service fixture in conftest.py already patches
   EmailService._send for every test, so an in-process assertion of "zero
   real sends" would pass even if the seed script's own suppression patch
   were completely broken. Running as a subprocess means conftest's fixture
   never applies, so a passing assertion here can only be explained by the
   seed script's own EmailService._send / _handle_webhook_post patches
   actually intercepting the calls -- proven via the seed script's own
   SUPPRESSED_SEND_COUNTS counters, printed at the end of its run. A
   --months 1 run only ever exercises the email path for real (no seeded
   automation preset uses the webhook_post action type -- confirmed by
   inventory), so that test's webhook assertion is == 0, not > 0: forcing a
   synthetic webhook call into "the smallest possible seed" run would
   misrepresent what that run actually does.

2. test_install_network_suppression_wires_both_patches_with_working_counters
   below directly exercises both patch paths (email and webhook) in-process,
   proving the installer wires both counters correctly with values other
   than 0. This does not need subprocess isolation for the webhook half --
   conftest.py has no fixture that touches automation_actions -- but it does
   for the email half, so it takes the same care conftest's fixture ordering
   would otherwise let slip past: see the comment inside the test.

Both also cover the import/mutation boundary: importing this module (or the
guard test module) must never mutate EmailService._send or
automation_actions._handle_webhook_post on its own -- only main() calling
_install_network_suppression() may. See
test_importing_seed_module_does_not_mutate_email_service.
"""

import os
import re
import subprocess
import sys

import pytest

from scripts.seed_demo_firm import ALLOWLISTED_DB_HOSTS, _resolve_database_host

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Captured at collection time -- module-level code in a test file runs during
# pytest's collection phase, before any fixture (including conftest's
# autouse mock_email_service) has run for any test. This is the only
# reliable way to observe whether merely *importing* scripts.seed_demo_firm
# mutated EmailService._send, since every test body runs after the autouse
# fixture has already replaced _send with its own fake.
import scripts.seed_demo_firm as _seed_module_for_import_check
from app.services.email_service import EmailService as _EmailServiceForImportCheck

_EMAIL_SEND_AT_COLLECTION_TIME = _EmailServiceForImportCheck._send


def test_importing_seed_module_does_not_mutate_email_service():
    assert _EMAIL_SEND_AT_COLLECTION_TIME is not _seed_module_for_import_check._suppressed_send


def test_install_network_suppression_wires_both_patches_with_working_counters(monkeypatch):
    import scripts.seed_demo_firm as seed
    from app.services.email_service import EmailService
    import app.services.automation_actions as automation_actions

    # automation_actions._handle_webhook_post has no autouse fixture managing
    # it (unlike EmailService._send, which monkeypatch will restore to its
    # pre-test value regardless of what we do to it below), so this test
    # must restore it itself or the raw assignment inside
    # _install_network_suppression() would leak into every later test in the
    # session.
    real_handle_webhook_post = automation_actions._handle_webhook_post
    try:
        seed._install_network_suppression()

        assert seed.SUPPRESSED_SEND_COUNTS["email"] == 0
        assert seed.SUPPRESSED_SEND_COUNTS["webhook"] == 0

        EmailService._send("a@b.com", "subject", "<p>hi</p>", "Firm")
        webhook_result = automation_actions.execute(
            "webhook_post", {"url": "http://example.com"}, {}, None
        )

        assert seed.SUPPRESSED_SEND_COUNTS["email"] > 0
        assert seed.SUPPRESSED_SEND_COUNTS["webhook"] > 0
        assert "suppressed" in webhook_result
    finally:
        automation_actions._handle_webhook_post = real_handle_webhook_post


def _run_seed_subprocess(*extra_args, stdin_input=None, timeout=600):
    database_url = os.environ["DATABASE_URL"]
    cmd = [sys.executable, os.path.join("scripts", "seed_demo_firm.py"), *extra_args]
    return subprocess.run(
        cmd,
        cwd=_REPO_ROOT,
        env=os.environ.copy(),
        input=stdin_input,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.fixture
def teardown_demo_firm():
    """Removes the demo firm the subprocess seed run creates, via the same
    subprocess path (through the guard), so state doesn't leak into other
    tests that share this database."""
    yield
    database_url = os.environ["DATABASE_URL"]
    host = _resolve_database_host(database_url)
    stdin_input = f"{host}\n" if host not in ALLOWLISTED_DB_HOSTS else None
    extra = ["--allow-production"] if host not in ALLOWLISTED_DB_HOSTS else []
    _run_seed_subprocess("--teardown", *extra, stdin_input=stdin_input, timeout=120)


def test_smallest_seed_run_suppresses_email_and_webhook_via_its_own_patch(teardown_demo_firm):
    database_url = os.environ["DATABASE_URL"]
    host = _resolve_database_host(database_url)

    extra_args = []
    stdin_input = None
    if host not in ALLOWLISTED_DB_HOSTS:
        extra_args.append("--allow-production")
        stdin_input = f"{host}\n"

    result = _run_seed_subprocess("--months", "1", *extra_args, stdin_input=stdin_input)

    assert result.returncode == 0, (
        f"seed subprocess failed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    first_line = result.stdout.splitlines()[0]
    assert first_line.startswith(f"Target database host: {host} (source: ")

    email_match = re.search(r"Suppressed email sends: (\d+)", result.stdout)
    webhook_match = re.search(r"Suppressed webhook posts: (\d+)", result.stdout)
    assert email_match is not None, result.stdout
    assert webhook_match is not None, result.stdout

    suppressed_email = int(email_match.group(1))
    assert suppressed_email > 0, "expected the smallest seed run to still trigger at least one email"

    # A --months 1 run enables no custom webhook_post automation (Phase 1
    # inventory confirmed no preset uses it), so this is expected to be 0 --
    # asserting on the counter itself rather than assuming it, so the
    # assertion still means something if that ever changes.
    assert webhook_match.group(1) == "0"
