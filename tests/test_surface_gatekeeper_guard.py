# tests/test_surface_gatekeeper_guard.py

"""Guard: the surface engine never reads the behavioral event log.

WHAT IS BEING GUARDED

The behavioral log is a recorder, never a gatekeeper. Operational control flow
(branching, gating, enforcement) reads durable operational tables, and anything
the product acts on comes from those tables. The surface engine is the newest
place that rule could quietly be broken: an overdue invoice item is supposed to
clear because the invoices table says the balance is zero, and it would be very
easy, and completely wrong, to clear it by looking for an invoice.paid event.

A generator or job that queries behavioral_events is a build failure, so this
test reads the real committed source of the generator module and the daily job
and fails if either one mentions the event log in a way that could be a read.

WHY THIS IS AN AST SCAN AND NOT A GREP

Two reasons, both learned the hard way in this repo.

First, portability. tests/test_sequence_version_pinning.py shells out to grep,
which does not exist on Windows PowerShell, so it fails there for a reason that
has nothing to do with the rule it guards. It is the suite's one known failing
test. Nothing new should join it.

Second, precision. Both modules under scan DISCUSS behavioral_events at length
in their docstrings and comments, because explaining why they must not read it
is part of the code. A text search would match that prose and be permanently
red, and the natural fix (loosen the pattern until it goes green) would leave a
guard that no longer catches anything. Parsing the source and walking the tree
ignores comments and docstrings for free, so the guard can be strict about code
while the code stays free to explain itself.

WRITING TO THE LOG IS ALLOWED, AND DELIBERATELY NOT FLAGGED

log_event is how the row-governs-log-echoes rule is honoured: the row is
written first, then the event fires as an echo. So this guard looks for the
MODEL and the TABLE (BehavioralEvent, behavioral_events), which are what a read
would have to go through, and not for log_event, which is the write path.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The modules the rule binds. Both are on the operational control-flow path:
# the generators decide what exists, the job decides what resolves.
GUARDED_MODULES = [
    Path("app/services/surface_generators.py"),
    Path("app/services/surface_daily_job.py"),
]

# The model class and the table name. Either one appearing in executable code
# means something is reaching for the event log.
FORBIDDEN_NAMES = {"BehavioralEvent"}
FORBIDDEN_STRINGS = {"behavioral_events"}
FORBIDDEN_IMPORT_FRAGMENT = "behavioral_event"

# log_event and the module that provides it are the write path and are fine.
ALLOWED_IMPORT_MODULES = {"app.services.behavioral_log"}


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Every string node that is a docstring, by identity, so prose is skipped."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                found.add(id(body[0].value))
    return found


def _violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    docstrings = _docstring_nodes(tree)
    problems: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in ALLOWED_IMPORT_MODULES:
                continue
            if FORBIDDEN_IMPORT_FRAGMENT in module:
                problems.append(
                    f"line {node.lineno}: imports from {module}, which is the event log"
                )
            for alias in node.names:
                if alias.name in FORBIDDEN_NAMES:
                    problems.append(
                        f"line {node.lineno}: imports {alias.name}, the event log model"
                    )

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if FORBIDDEN_IMPORT_FRAGMENT in alias.name:
                    problems.append(
                        f"line {node.lineno}: imports {alias.name}, the event log"
                    )

        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                problems.append(f"line {node.lineno}: uses {node.id}")

        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_NAMES:
                problems.append(f"line {node.lineno}: uses .{node.attr}")

        elif isinstance(node, ast.Constant):
            if (
                isinstance(node.value, str)
                and id(node) not in docstrings
                and any(bad in node.value for bad in FORBIDDEN_STRINGS)
            ):
                problems.append(
                    f"line {node.lineno}: string literal mentions the event log table"
                )

    return problems


@pytest.mark.parametrize("relative_path", GUARDED_MODULES, ids=lambda p: p.name)
def test_surface_engine_never_reads_behavioral_events(relative_path: Path):
    """No executable reference to the behavioral event log in either module."""
    path = REPO_ROOT / relative_path
    assert path.exists(), f"{relative_path} is missing, so this guard is measuring nothing"

    problems = _violations(path)
    assert problems == [], (
        f"{relative_path} reaches for the behavioral event log:\n  "
        + "\n  ".join(problems)
        + "\n\nOperational control flow reads operational tables. The log is a "
          "recorder, never a gatekeeper."
    )


def test_the_guard_can_actually_see_a_violation():
    """The control for the control.

    A scan that cannot fail is worse than no scan, and this one has real ways
    to be blind: if _violations silently returned [] on a parse error, or the
    docstring filter swallowed every string, the test above would be green
    forever. So parse a module that does exactly what is forbidden and confirm
    each shape is caught.
    """
    offending = (
        "from app.models.behavioral_event import BehavioralEvent\\n"
        "def clear(db):\\n"
        "    return db.query(BehavioralEvent).filter_by(table='behavioral_events').all()\\n"
    ).replace("\\n", "\n")

    path = REPO_ROOT / "tests" / "_gatekeeper_control_sample.py"
    path.write_text(offending, encoding="utf-8")
    try:
        problems = _violations(path)
    finally:
        path.unlink()

    assert len(problems) >= 3, f"guard missed a violation shape: {problems}"
    joined = " ".join(problems)
    assert "behavioral_event" in joined
    assert "BehavioralEvent" in joined
    assert "event log table" in joined


def test_guard_ignores_prose_about_the_rule():
    """Docstrings and comments explaining the rule must not trip the guard.

    This is the assertion that keeps the guard honest rather than merely
    strict. Both guarded modules explain at length why they must not read
    behavioral_events, and a guard that punished them for saying so would be
    deleted within a week.
    """
    sample = (
        '"""This module never reads behavioral_events, ever."""\\n'
        "# BehavioralEvent must not be imported here\\n"
        "VALUE = 1\\n"
    ).replace("\\n", "\n")

    path = REPO_ROOT / "tests" / "_gatekeeper_prose_sample.py"
    path.write_text(sample, encoding="utf-8")
    try:
        problems = _violations(path)
    finally:
        path.unlink()

    assert problems == [], f"guard tripped on prose: {problems}"
