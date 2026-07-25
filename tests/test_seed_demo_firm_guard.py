# tests/test_seed_demo_firm_guard.py

import os
import sys

import pytest

from scripts.seed_demo_firm import (
    ALLOWLISTED_DB_HOSTS,
    _database_url_from_dotenv_files,
    _enforce_environment_guard,
    _resolve_database_host,
    _resolve_effective_database_url,
)

PROD_URL = "postgresql+psycopg://user:pass@prod-db.example.com:5432/db"
LOCAL_URL = "postgresql+psycopg://user:pass@localhost:5432/db"


def _isolate_cwd(monkeypatch, tmp_path):
    """_database_url_from_dotenv_files reads '.env.local'/'.env' as relative
    paths, resolved against cwd. Running from an empty tmp_path keeps these
    tests from ever picking up this repo's real .env, and lets each test
    control exactly which dotenv files exist."""
    monkeypatch.chdir(tmp_path)


def test_resolve_database_host_missing():
    assert _resolve_database_host(None) == "(DATABASE_URL not set)"
    assert _resolve_database_host("") == "(DATABASE_URL not set)"


def test_resolve_database_host_unparseable():
    assert _resolve_database_host("not-a-url-at-all") == "(DATABASE_URL unparseable)"


def test_resolve_database_host_parses_hostname():
    assert _resolve_database_host(LOCAL_URL) == "localhost"
    assert _resolve_database_host(PROD_URL) == "prod-db.example.com"


# --- DATABASE_URL source resolution -----------------------------------------
# Mirrors pydantic-settings' actual precedence, confirmed empirically (not
# assumed): a real process env var always wins over both dotenv files, and
# between the two dotenv files, .env overrides .env.local for the same key
# (later entries in the env_file=('.env.local', '.env') tuple win on
# conflict). Also verifies source labeling (Phase 8 item 2): the guard must
# report exactly which of "shell environment", ".env", or ".env.local" a
# value came from.

def test_dotenv_resolution_returns_none_when_no_files_exist(monkeypatch, tmp_path):
    _isolate_cwd(monkeypatch, tmp_path)
    assert _database_url_from_dotenv_files() == (None, None)


def test_dotenv_resolution_reads_env_local_when_env_absent(monkeypatch, tmp_path):
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env.local").write_text("DATABASE_URL=postgresql://x/from-local\n")
    assert _database_url_from_dotenv_files() == ("postgresql://x/from-local", ".env.local")


def test_dotenv_resolution_env_overrides_env_local(monkeypatch, tmp_path):
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env.local").write_text("DATABASE_URL=postgresql://x/from-local\n")
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://x/from-dotenv\n")
    assert _database_url_from_dotenv_files() == ("postgresql://x/from-dotenv", ".env")


def test_resolve_effective_database_url_prefers_shell_env_var(monkeypatch, tmp_path):
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://x/from-dotenv\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/from-shell")

    env_var_url, dotenv_url, dotenv_source = _resolve_effective_database_url()
    assert env_var_url == "postgresql://x/from-shell"
    assert dotenv_url == "postgresql://x/from-dotenv"
    assert dotenv_source == ".env"


def test_resolve_effective_database_url_falls_back_to_dotenv(monkeypatch, tmp_path):
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(f"DATABASE_URL={LOCAL_URL}\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    env_var_url, dotenv_url, dotenv_source = _resolve_effective_database_url()
    assert env_var_url is None
    assert dotenv_url == LOCAL_URL
    assert dotenv_source == ".env"


# --- Guard behavior ----------------------------------------------------------
# Every guard test isolates cwd (no stray .env files) and explicitly sets or
# clears the DATABASE_URL env var, so results reflect only what each test
# deliberately sets up, never this repo's real .env.

def test_guard_proceeds_against_localhost_with_no_flag(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    _enforce_environment_guard(False)
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "Target database host: localhost (source: shell environment)"
    assert lines[1] == f"Working directory: {os.getcwd()}"


def test_guard_reads_host_from_dotenv_when_env_var_absent(monkeypatch, tmp_path, capsys):
    """The bug the Phase 7 correction fixed: DATABASE_URL present only in
    .env (as it is on this dev machine) must resolve to the real host, not
    the '(DATABASE_URL not set)' sentinel."""
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(f"DATABASE_URL={LOCAL_URL}\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    _enforce_environment_guard(False)
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "Target database host: localhost (source: .env)"


def test_guard_reports_env_local_as_source(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env.local").write_text(f"DATABASE_URL={LOCAL_URL}\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    _enforce_environment_guard(False)
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "Target database host: localhost (source: .env.local)"


def test_guard_aborts_non_allowlisted_host_no_flag(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    monkeypatch.setenv("DATABASE_URL", PROD_URL)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with pytest.raises(SystemExit) as exc_info:
        _enforce_environment_guard(False)
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "ABORT" in out
    assert "--allow-production" in out


def test_guard_aborts_flag_present_mismatched_confirmation(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    monkeypatch.setenv("DATABASE_URL", PROD_URL)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "wrong-host")

    with pytest.raises(SystemExit) as exc_info:
        _enforce_environment_guard(True)
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "did not match" in out


def test_guard_proceeds_flag_present_matching_confirmation(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    monkeypatch.setenv("DATABASE_URL", PROD_URL)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "prod-db.example.com")

    _enforce_environment_guard(True)
    out = capsys.readouterr().out
    assert "Confirmed. Proceeding" in out


def test_guard_aborts_missing_database_url(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with pytest.raises(SystemExit) as exc_info:
        _enforce_environment_guard(False)
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "Target database host: (DATABASE_URL not set)"
    assert "ABORT" in out


def test_guard_aborts_when_stdin_not_a_tty(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    monkeypatch.setenv("DATABASE_URL", PROD_URL)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    with pytest.raises(SystemExit) as exc_info:
        _enforce_environment_guard(True)
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "not a TTY" in out


def test_guard_proceeds_when_shell_and_dotenv_share_host_but_differ_otherwise(monkeypatch, tmp_path, capsys):
    """Same host, different port/db/credentials (e.g. a dev .env vs a
    shell-injected test DATABASE_URL, both on localhost) is not a
    safety-relevant disagreement and must not abort."""
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://postgres:postgres123@localhost:5432/accounting_dev\n"
    )
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://testuser:testpass@localhost:5433/accounting_test"
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    _enforce_environment_guard(False)
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "Target database host: localhost (source: shell environment)"
    assert "ABORT" not in out


def test_guard_aborts_when_shell_and_dotenv_disagree(monkeypatch, tmp_path, capsys):
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(f"DATABASE_URL={PROD_URL}\n")
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with pytest.raises(SystemExit) as exc_info:
        _enforce_environment_guard(True)
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "ABORT" in out
    assert "different hosts" in out
    assert "shell environment host: localhost" in out
    assert ".env host:   prod-db.example.com" in out
    assert f"working directory: {os.getcwd()}" in out


def test_guard_aborts_on_disagreement_even_with_allow_production_flag(monkeypatch, tmp_path, capsys):
    """Phase 8 item 2: disagreement must abort regardless of flags."""
    _isolate_cwd(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(f"DATABASE_URL={PROD_URL}\n")
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "should-not-be-reached")

    with pytest.raises(SystemExit) as exc_info:
        _enforce_environment_guard(True)  # --allow-production would be True here
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "ABORT" in out


def test_allowlist_contents():
    assert ALLOWLISTED_DB_HOSTS == {"localhost", "127.0.0.1"}
