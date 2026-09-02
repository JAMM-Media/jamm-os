# tests/test_surface_job_registration.py

"""Guard: the surface tick is actually registered with the scheduler.

Instance one on the list in How_We_Work_Process_Rules.md is an expiry sweep
that was written, tested, and correct, and that never ran, because nobody
registered it. Nothing errored, because nothing happened. Every test in
test_surface_items.py calls the generation pass directly, so all of them would
stay green if the job were never wired into the scheduler at all.

This test reads app/main.py and asserts the wiring exists: the tick is
imported, and it is handed to scheduler.add_job. It parses the source rather
than starting the real scheduler, because starting it inside the suite would
launch background threads against the test database.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN = REPO_ROOT / "app" / "main.py"

JOB_FUNCTION = "run_surface_hourly_tick"
JOB_ID = "surface_items_hourly_tick"


def _tree() -> ast.AST:
    return ast.parse(MAIN.read_text(encoding="utf-8"), filename=str(MAIN))


def test_the_tick_is_imported_into_main():
    imported = {
        alias.name
        for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert JOB_FUNCTION in imported, (
        f"{JOB_FUNCTION} is not imported by app/main.py, so it cannot be "
        "registered and the surfaces would never be generated."
    )


def test_the_tick_is_registered_with_the_scheduler():
    """A job that exists but is never added to the scheduler never runs."""
    registered = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "add_job"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Name):
            registered.append(first.id)

    assert JOB_FUNCTION in registered, (
        f"{JOB_FUNCTION} is never passed to scheduler.add_job. The generators, "
        "the job and every test of them would still pass while no briefing was "
        "ever built. This is instance one on the list, exactly."
    )


def test_the_registration_pins_its_timezone_and_id():
    """An unpinned cron hour resolves through tzlocal from the host.

    Only the IRS expiry job pins its timezone today; nothing in this repo pins
    the droplet's TZ, so an unpinned trigger fires at an hour nobody chose.
    """
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "add_job"):
            continue
        if not (node.args and isinstance(node.args[0], ast.Name)):
            continue
        if node.args[0].id != JOB_FUNCTION:
            continue

        keywords = {
            kw.arg: kw.value.value
            for kw in node.keywords
            if isinstance(kw.value, ast.Constant)
        }
        assert keywords.get("timezone") == "UTC", (
            "the surface tick does not pin its trigger timezone"
        )
        assert keywords.get("id") == JOB_ID
        assert keywords.get("replace_existing") is True
        return

    raise AssertionError(f"no add_job call found for {JOB_FUNCTION}")
