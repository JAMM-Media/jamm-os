# tests/test_demo_seed_password_env.py

"""
get_demo_password reads DEMO_SEED_PASSWORD at run time, or refuses clearly.

Ruled Sep 24, 2026. The companion tripwire, tests/test_no_script_password_literals.py,
proves no literal is left behind. This file proves the replacement works and
fails legibly, which is the half a source scan cannot see.

The error has to name the variable. An operator who gets "password not set"
has to go reading code to find out which one, and the failure happens at the
start of a seed run they were about to wait twelve months of history for.
"""

import pytest

from scripts import seed_demo_firm_config
from scripts.seed_demo_firm_config import get_demo_password

# Spelled out here on purpose. The config module deliberately holds no
# constant for it, because a PASSWORD-shaped name bound to a string literal is
# what the companion tripwire refuses.
ENV_VAR = "DEMO_SEED_PASSWORD"

# Not a credential for anything. It exists so the success case asserts on an
# exact value rather than on "something non-empty".
PLACEHOLDER = "placeholder-not-a-real-credential"


def test_importing_the_config_with_the_variable_unset_does_not_raise(monkeypatch):
    """Importing must stay safe.

    seed_demo_firm.py imports this module at module level, the guard ordering
    test parses it, and the suite imports it here. None of them are going to
    use the password, and none may be broken by its absence.
    """
    monkeypatch.delenv(ENV_VAR, raising=False)

    import importlib

    importlib.reload(seed_demo_firm_config)
    assert hasattr(seed_demo_firm_config, "get_demo_password")


def test_unset_variable_raises_and_names_it(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        get_demo_password()

    assert ENV_VAR in str(excinfo.value)


def test_empty_variable_raises_too(monkeypatch):
    """Set but blank is the same as unset, and is the likelier operator error:
    an exported variable with nothing after the equals sign."""
    monkeypatch.setenv(ENV_VAR, "   ")

    with pytest.raises(RuntimeError) as excinfo:
        get_demo_password()

    assert ENV_VAR in str(excinfo.value)


def test_set_variable_is_returned(monkeypatch):
    monkeypatch.setenv(ENV_VAR, PLACEHOLDER)

    assert get_demo_password() == PLACEHOLDER


def test_the_value_is_read_at_call_time_not_at_import(monkeypatch):
    """Two calls either side of a change see the change.

    If the value were captured at import, a rotated password would keep
    seeding the old one until the process restarted, and the module would have
    to be imported after the environment rather than before it.
    """
    monkeypatch.setenv(ENV_VAR, PLACEHOLDER)
    first = get_demo_password()

    monkeypatch.setenv(ENV_VAR, PLACEHOLDER + "-rotated")
    second = get_demo_password()

    assert first == PLACEHOLDER
    assert second == PLACEHOLDER + "-rotated"


def test_env_example_documents_the_variable_with_no_value():
    """.env.example carries the key so an operator knows it exists, and
    carries nothing after the equals sign so the repo never ships a value."""
    from pathlib import Path

    env_example = (Path(__file__).resolve().parent.parent / ".env.example").read_text(
        encoding="utf-8"
    )
    lines = [line.strip() for line in env_example.splitlines()]
    assert f"{ENV_VAR}=" in lines
    assert "PORTAL_SEED_PASSWORD=" in lines
