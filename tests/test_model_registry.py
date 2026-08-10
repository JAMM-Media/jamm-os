# tests/test_model_registry.py

"""Guards on the model registry in app/models/__init__.py.

A model file that never gets imported is invisible to Base.metadata, and
Base.metadata is exactly what Alembic autogenerate compares the database
against. An unimported model therefore does not read as "no change" -- it
reads as "this table is not supposed to exist", and autogenerate proposes to
DROP it. That has happened twice in this repo. These tests are the tripwire.

Only direction one is testable here. See test_direction_two_is_not_testable
at the bottom for why, in full.
"""

import importlib
import inspect
import pkgutil
import subprocess
import sys
from pathlib import Path

import app.models
from app.db.base_class import Base

MODELS_DIR = Path(app.models.__file__).parent


def _model_module_names() -> list[str]:
    """Every .py file in app/models/ except __init__.py, by module name."""
    return sorted(
        info.name
        for info in pkgutil.iter_modules([str(MODELS_DIR)])
        if info.name != "__init__"
    )


def test_model_directory_is_not_empty():
    """Cheap canary. If the enumeration below ever silently returns nothing,
    every other test in this file would pass while checking zero models."""
    assert len(_model_module_names()) > 40


def test_every_model_module_is_imported():
    """Direction one, part one: a model file exists but nobody imports it."""
    missing = [
        name
        for name in _model_module_names()
        if f"app.models.{name}" not in sys.modules
    ]
    assert not missing, (
        "These model modules exist in app/models/ but were not imported by "
        f"`import app.models`: {missing}. Their tables are absent from "
        "Base.metadata, so Alembic autogenerate will propose dropping them."
    )


def test_every_model_class_is_registered_in_metadata():
    """Direction one, part two: a model class exists but its table is not in
    Base.metadata."""
    unregistered = []

    for module_name in _model_module_names():
        module = importlib.import_module(f"app.models.{module_name}")
        for class_name, obj in vars(module).items():
            # __module__ keeps this to the classes the module actually defines,
            # so a model imported for a foreign key is not checked twice.
            if (
                inspect.isclass(obj)
                and issubclass(obj, Base)
                and obj is not Base
                and obj.__module__ == module.__name__
            ):
                if obj.__tablename__ not in Base.metadata.tables:
                    unregistered.append(f"{module_name}.{class_name}")

    assert not unregistered, (
        "These model classes are not registered in Base.metadata: "
        f"{unregistered}"
    )


def test_every_model_class_is_exported_from_the_package():
    """`from app.models import Firm` and `app.models.Firm` are used across the
    codebase. Auto-discovery has to keep binding those names, not just import
    the modules for their side effects."""
    not_exported = []

    for module_name in _model_module_names():
        module = importlib.import_module(f"app.models.{module_name}")
        for class_name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, Base)
                and obj is not Base
                and obj.__module__ == module.__name__
            ):
                if getattr(app.models, class_name, None) is not obj:
                    not_exported.append(f"{module_name}.{class_name}")

    assert not not_exported, (
        "These model classes are not bound into the app.models namespace: "
        f"{not_exported}"
    )


def test_import_of_app_models_alone_registers_every_table():
    """Direction one, the version that actually reproduces the Alembic bug.

    The three tests above run inside the pytest process, where conftest has
    already imported app.main and pulled most model modules in transitively
    through routers and services. That masks the real failure: those tests
    keep passing even with a stale hand-written registry, because something
    else in the app happened to import the missing module.

    migrations/env.py has no such luck. It imports app.models and nothing
    else, and whatever is absent from Base.metadata at that moment is what
    autogenerate proposes to DROP. So this runs in a clean subprocess that
    imports exactly what env.py imports, and compares the table count there
    against the fully loaded count in this process.
    """
    source = (
        "import app.models; "
        "from app.db.base_class import Base; "
        "print(len(Base.metadata.tables))"
    )
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert result.returncode == 0, (
        f"`import app.models` failed in a clean interpreter:\n{result.stderr}"
    )

    isolated_count = int(result.stdout.strip().splitlines()[-1])
    assert isolated_count == len(Base.metadata.tables), (
        f"`import app.models` on its own registers {isolated_count} tables, "
        f"but {len(Base.metadata.tables)} are registered once the whole app "
        "is loaded. Alembic only does the former, so the difference is the "
        "set of tables autogenerate would propose to DROP."
    )


def test_direction_two_is_not_testable_under_this_harness():
    """Direction two -- a table exists in the database that no model describes
    -- is deliberately NOT tested, and this test exists to record why so the
    gap is visible rather than merely absent.

    tests/conftest.py builds the test database with
    Base.metadata.create_all(). The database is therefore constructed from the
    exact metadata a direction two test would compare it against, so such a
    test passes unconditionally, forever, while measuring nothing. A green
    check that cannot fail is worse than no check, because it is read as
    coverage.

    That test becomes real the day the harness runs Alembic migrations against
    the test database instead. At that point the database is built by the
    migration history and the comparison has two independent sides. Exempt
    alembic_version when writing it; it is Alembic's own bookkeeping table and
    correctly has no model.

    This test asserts the precondition rather than the behavior, so it fails
    and prompts a rewrite if the harness ever switches to migrations.
    """
    conftest = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    assert "Base.metadata.create_all" in conftest, (
        "tests/conftest.py no longer builds the test database with "
        "create_all(). If it now runs Alembic migrations, the direction two "
        "guard test has become meaningful and should be written. Read this "
        "test's docstring, then replace it."
    )
