# tests/test_seed_demo_firm_guard_ordering.py

"""
Regression guard for the Phase 8 production bug: a production run of
scripts/seed_demo_firm.py died on `from freezegun import freeze_time` before
the guard ever printed a "Target database host" line, because an import that
could fail sat above the guard invocation. Structural fix: only argparse,
os, sys, and urllib(.parse) may precede the guard call. This test parses
each script file\'s own AST and asserts the guard call\'s line number precedes
the line number of the first non-stdlib import (third-party or app/scripts-local),
so a later PR that adds an import above the guard fails CI instead of
failing quietly on a production host.

Scope: all scripts/seed_*.py and scripts/fix_*.py files, with one explicit
exclusion:

  seed_demo_firm_config.py -- pure config module imported by seed_demo_firm.py,
  not a standalone script. It has no __main__ block and no SessionLocal usage,
  so the guard does not apply to it and it is excluded from this scan.

Note: seed_complexity_catalog.py does not yet have the guard installed. This
is a known, intentional state: Andrew owns adding it on his side, and this
test surfaces its absence as a real CI failure until he does. That failure
is the intended outcome, not a bug in this task.
"""

import ast
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

# seed_demo_firm_config.py is a pure config module imported by seed_demo_firm.py,
# not a standalone script -- it has no __main__ block and no SessionLocal usage.
# Including it would be a false positive: the guard pattern does not apply to
# config/helper modules that are never executed directly.
_EXCLUDED_SCRIPTS = {"seed_demo_firm_config.py"}


def _gather_script_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in ("seed_*.py", "fix_*.py"):
        for p in _SCRIPTS_DIR.glob(pattern):
            if p.name not in _EXCLUDED_SCRIPTS:
                paths.append(p)
    return sorted(paths)


_SCRIPT_PATHS = _gather_script_paths()


def _is_stdlib(top_level_name: str) -> bool:
    return top_level_name == "__future__" or top_level_name in sys.stdlib_module_names


def _iter_relevant_statements(tree: ast.Module):
    """Top-level statements, plus the direct children of the
    `if __name__ == "__main__":` block, where the guard invocation and CLI
    arg parsing live. Does not descend into function bodies -- an import
    deferred inside a function (like _database_url_from_dotenv_files\'
    `from dotenv import dotenv_values`) only executes when that function is
    called, not merely by importing/parsing this file, so it is not part of
    "what runs before the guard.\""""
    for node in tree.body:
        yield node
        if isinstance(node, ast.If):
            yield from node.body


@pytest.mark.parametrize("script_path", _SCRIPT_PATHS, ids=[p.name for p in _SCRIPT_PATHS])
def test_guard_invocation_precedes_first_non_stdlib_import(script_path: Path) -> None:
    """_enforce_environment_guard(...) must be called before any non-stdlib import."""
    tree = ast.parse(script_path.read_text(encoding="utf-8"))

    guard_call_lineno: int | None = None
    first_non_stdlib_import_lineno: int | None = None
    first_non_stdlib_import_name: str | None = None

    for node in _iter_relevant_statements(tree):
        if (
            guard_call_lineno is None
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_enforce_environment_guard"
        ):
            guard_call_lineno = node.lineno

        if isinstance(node, ast.Import):
            top_level_names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            top_level_names = [(node.module or "").split(".")[0]]
        else:
            top_level_names = []

        for name in top_level_names:
            if name and not _is_stdlib(name) and first_non_stdlib_import_lineno is None:
                first_non_stdlib_import_lineno = node.lineno
                first_non_stdlib_import_name = name

    assert guard_call_lineno is not None, (
        f"{script_path.name}: could not find the _enforce_environment_guard(...) call"
    )
    assert first_non_stdlib_import_lineno is not None, (
        f"{script_path.name}: could not find any non-stdlib import"
    )
    assert guard_call_lineno < first_non_stdlib_import_lineno, (
        f"{script_path.name}: guard call at line {guard_call_lineno} must precede the "
        f"first non-stdlib import ({first_non_stdlib_import_name!r}) at line "
        f"{first_non_stdlib_import_lineno}"
    )


@pytest.mark.parametrize("script_path", _SCRIPT_PATHS, ids=[p.name for p in _SCRIPT_PATHS])
def test_only_allowed_stdlib_imports_precede_the_guard(script_path: Path) -> None:
    """Tighter than the test above: even a *new stdlib* import above the
    guard is drift away from the Phase 8 fix (only argparse, os, sys,
    urllib may precede it) and should be caught explicitly rather than
    waiting for it to become a problem."""
    tree = ast.parse(script_path.read_text(encoding="utf-8"))
    allowed = {"argparse", "os", "sys", "urllib"}

    guard_call_lineno: int | None = None
    for node in _iter_relevant_statements(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_enforce_environment_guard"
        ):
            guard_call_lineno = node.lineno
            break

    assert guard_call_lineno is not None, (
        f"{script_path.name}: could not find the _enforce_environment_guard(...) call"
    )

    for node in _iter_relevant_statements(tree):
        if node.lineno >= guard_call_lineno:
            break

        if isinstance(node, ast.Import):
            top_level_names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            top_level_names = [(node.module or "").split(".")[0]]
        else:
            continue

        for name in top_level_names:
            assert name in allowed, (
                f"{script_path.name}: import of {name!r} at line {node.lineno} "
                f"precedes the guard call at line {guard_call_lineno}, but only "
                f"{sorted(allowed)} are allowed there"
            )
