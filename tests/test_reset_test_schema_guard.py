# tests/test_reset_test_schema_guard.py

"""
Guards for scripts/reset_test_schema.py, the only sanctioned way to drop and
recreate the test database's public schema.

The script's whole safety story is that every check runs before a connection
is ever opened, so these tests call _enforce_environment_guard directly with a
fabricated environment and assert the refusal, plus one subprocess test that
proves the real process refuses and connects to nothing.

Isolation: the guard reads .env.test, .env and .env.local as paths relative to
the current working directory, exactly like scripts/seed_demo_firm.py does, so
every test runs from an empty tmp_path and writes only the dotenv files it
wants the guard to see. Running from the repo root would let the real .env.test
answer for a fabricated one.

Ordering of the guard invocation relative to imports is a separate concern and
is covered by tests/test_seed_demo_firm_guard_ordering.py, whose glob was
extended to scripts/reset_*.py for this script.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import reset_test_schema as reset

REPO_ROOT = Path(__file__).resolve().parent.parent

# A distinctive token that stands in for a password, so a test can assert the
# refusal path never echoes credentials. It is not a credential for anything.
_SECRET_TOKEN = "zzz-guard-test-token-zzz"

TEST_URL = f"postgresql+psycopg://tester:{_SECRET_TOKEN}@localhost:5432/accounting_test"
DEV_URL = f"postgresql+psycopg://tester:{_SECRET_TOKEN}@localhost:5432/accounting_dev"
LOOPBACK_TEST_URL = f"postgresql+psycopg://tester:{_SECRET_TOKEN}@127.0.0.1:5432/accounting_test"
REMOTE_URL = f"postgresql+psycopg://tester:{_SECRET_TOKEN}@db.fabricated-not-real.example:5432/accounting_test"
DIGITALOCEAN_URL = (
    f"postgresql+psycopg://tester:{_SECRET_TOKEN}@"
    "app-a1b2c3d4-e5f6-7890-abcd-ef1234567890-do-user-9876543-0.b.db.ondigitalocean.com"
    ":25060/accounting_test?sslmode=require"
)

# Every line main() prints once it has a connection. None of these may appear
# on a refusal path.
CONNECTION_MARKERS = (
    "Connected to:",
    "Public tables before:",
    "Public tables after:",
    "Reset complete",
)


def _write_env(tmp_path: Path, *, test_url: str | None = None, dev_url: str | None = None) -> None:
    if test_url is not None:
        (tmp_path / ".env.test").write_text(f"DATABASE_URL={test_url}\n", encoding="utf-8")
    if dev_url is not None:
        (tmp_path / ".env").write_text(f"DATABASE_URL={dev_url}\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Empty cwd, no ambient DATABASE_URL, VALIDATED_URL back to None.

    conftest.py puts a real DATABASE_URL in os.environ before any test runs;
    left in place it would outrank every fabricated dotenv file here and each
    guard test would silently be checking the same real URL."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(reset, "VALIDATED_URL", None)
    yield


def _expect_refusal(capsys) -> str:
    """Assert the guard exited non-zero, validated nothing, and printed exactly
    one refusal line with no connection-shaped output. Returns that line."""
    with pytest.raises(SystemExit) as excinfo:
        reset._enforce_environment_guard()
    assert excinfo.value.code == 1
    assert reset.VALIDATED_URL is None

    out = capsys.readouterr().out
    refusal_lines = [line for line in out.splitlines() if line.startswith("REFUSED: ")]
    assert len(refusal_lines) == 1, out
    for marker in CONNECTION_MARKERS:
        assert marker not in out
    return refusal_lines[0]


def test_url_parts_reads_host_port_and_name():
    assert reset._url_parts(TEST_URL) == ("localhost", 5432, "accounting_test")
    assert reset._url_parts(LOOPBACK_TEST_URL) == ("127.0.0.1", 5432, "accounting_test")


def test_url_parts_never_raises_on_malformed_input():
    """The refusal is worthless if resolving the target crashes first."""
    for bad in (None, "", "not-a-url-at-all", "postgresql://[::1:5432/db", "db.example.com"):
        assert reset._url_parts(bad) is None


def test_accepts_the_local_test_database(tmp_path, capsys):
    _write_env(tmp_path, test_url=TEST_URL, dev_url=DEV_URL)

    reset._enforce_environment_guard()

    assert reset.VALIDATED_URL == TEST_URL
    out = capsys.readouterr().out
    assert "Target database: accounting_test" in out
    assert "REFUSED" not in out


def test_accepts_the_loopback_host(tmp_path, capsys):
    _write_env(tmp_path, test_url=LOOPBACK_TEST_URL, dev_url=DEV_URL)

    reset._enforce_environment_guard()

    assert reset.VALIDATED_URL == LOOPBACK_TEST_URL
    assert "REFUSED" not in capsys.readouterr().out


def test_refuses_a_non_local_host(tmp_path, capsys):
    _write_env(tmp_path, test_url=REMOTE_URL)

    assert "not on the local allowlist" in _expect_refusal(capsys)


def test_refuses_a_production_marker_host(tmp_path, capsys):
    """Caught on the marker, not on the host allowlist: the marker check runs
    first so a production URL is refused even if the allowlist were ever
    loosened."""
    _write_env(tmp_path, test_url=DIGITALOCEAN_URL)

    assert "production marker" in _expect_refusal(capsys)


def test_refuses_a_production_port_marker(tmp_path, capsys):
    _write_env(tmp_path, test_url="postgresql+psycopg://tester:pw@localhost:25060/accounting_test")

    assert "production marker" in _expect_refusal(capsys)


def test_refuses_the_dev_database_by_name(tmp_path, monkeypatch, capsys):
    """The everyday hazard: an operator with the dev DATABASE_URL exported runs
    the reset. Localhost, so the allowlist passes; the name check is what stops
    it."""
    _write_env(tmp_path, test_url=TEST_URL, dev_url=DEV_URL)
    monkeypatch.setenv("DATABASE_URL", DEV_URL)

    assert "is not the test database 'accounting_test'" in _expect_refusal(capsys)


def test_refuses_when_the_target_is_the_dev_url(tmp_path, capsys):
    """The name check alone cannot catch a dev database that happens to carry
    the test database's name, so the dev-identity guard compares host, port and
    name against .env. Nothing in the current checkout can reach this guard
    (dev is accounting_dev), which is why the test fabricates a .env that can."""
    _write_env(tmp_path, test_url=TEST_URL, dev_url=TEST_URL)

    assert "is the dev database named in .env" in _expect_refusal(capsys)


def test_refuses_an_unparseable_url(tmp_path, capsys):
    _write_env(tmp_path, test_url="not-a-url-at-all")

    assert "unparseable" in _expect_refusal(capsys)


def test_refuses_when_no_database_url_is_available(tmp_path, capsys):
    assert "no DATABASE_URL" in _expect_refusal(capsys)


def test_refuses_when_the_test_env_file_is_missing(tmp_path, monkeypatch, capsys):
    """A shell-supplied URL that looks right still has nothing to be checked
    against if .env.test is not there. Fail closed rather than trust the name."""
    monkeypatch.setenv("DATABASE_URL", TEST_URL)

    assert "cannot read the test database name from .env.test" in _expect_refusal(capsys)


def test_shell_environment_outranks_the_dotenv_file(tmp_path, capsys, monkeypatch):
    """Instance seventeen in reverse: if the dotenv file outranked the shell,
    an injected DATABASE_URL could never reach these guards and the live
    refusal check would be measuring nothing. The local .env.test here is
    exactly the value that would hide the injected remote one."""
    _write_env(tmp_path, test_url=TEST_URL, dev_url=DEV_URL)
    monkeypatch.setenv("DATABASE_URL", REMOTE_URL)

    refusal = _expect_refusal(capsys)
    assert "not on the local allowlist" in refusal
    assert "shell environment" in refusal


def test_refusal_never_prints_the_password(tmp_path, capsys):
    _write_env(tmp_path, test_url=REMOTE_URL)

    with pytest.raises(SystemExit):
        reset._enforce_environment_guard()

    captured = capsys.readouterr()
    assert _SECRET_TOKEN not in captured.out
    assert _SECRET_TOKEN not in captured.err


def test_success_path_never_prints_the_password(tmp_path, capsys):
    _write_env(tmp_path, test_url=TEST_URL, dev_url=DEV_URL)

    reset._enforce_environment_guard()

    captured = capsys.readouterr()
    assert _SECRET_TOKEN not in captured.out
    assert _SECRET_TOKEN not in captured.err


def test_live_subprocess_refuses_and_opens_no_connection():
    """The in-process tests prove the guard function refuses. This one proves
    the script does, as a real process, from the repo root, with the URL in the
    child environment only. The host does not resolve, so any connection
    attempt would surface as a driver error rather than a clean refusal."""
    child_env = dict(os.environ)
    child_env["DATABASE_URL"] = REMOTE_URL

    proc = subprocess.run(
        [sys.executable, str(Path("scripts") / "reset_test_schema.py")],
        cwd=str(REPO_ROOT),
        env=child_env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert proc.stdout.startswith("REFUSED: ")
    assert "not on the local allowlist" in proc.stdout
    assert proc.stderr == ""
    for marker in CONNECTION_MARKERS:
        assert marker not in proc.stdout
    assert _SECRET_TOKEN not in proc.stdout
    assert _SECRET_TOKEN not in proc.stderr
