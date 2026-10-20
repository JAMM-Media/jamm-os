# tests/test_no_script_password_literals.py

"""
Tripwire: no password literal in any script under scripts/.

Ruled Sep 24, 2026. A password assigned in tracked config is a credential
published to everyone who can read the repo, and rotating it means a commit.
Demo seeds read theirs from the environment at run time, after their
production guard has passed: DEMO_SEED_PASSWORD for the demo firm and
PORTAL_SEED_PASSWORD for the demo portal client.

This is an AST scan rather than a text search on purpose. A regex over source
would fire on the word password in a docstring and miss an assignment written
across two lines, and it could not tell a module-level constant from a local
variable inside a function that has already checked its environment.

Scope is module level only. A name containing PASSWORD bound to a string
literal at import time is the defect: it exists whether or not the script is
ever run, and it travels in every clone.
"""

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"


def _script_paths() -> list[Path]:
    return sorted(
        p for p in _SCRIPTS_DIR.glob("*.py") if "__pycache__" not in p.parts
    )


def _parse(path: Path) -> ast.Module:
    # utf-8-sig, not utf-8: three scripts in this directory carry a UTF-8 BOM
    # (add_tax_engagement_invoices.py, itemize_bookkeeping_invoices.py,
    # name_bookkeeping_line_items.py). Plain utf-8 leaves the BOM in the text
    # and ast.parse raises on it, which would turn this guard into a collection
    # error rather than a scan.
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def _module_level_password_literals(path: Path) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for node in _parse(path).body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue

        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue

        for name in names:
            if "PASSWORD" in name.upper():
                found.append((name, node.lineno))
    return found


def test_there_are_scripts_to_scan():
    """A scan over an empty file list passes for the wrong reason."""
    assert len(_script_paths()) > 10


def test_every_script_parses():
    """The scan is only as good as its ability to read the files.

    A script this cannot parse is silently unscanned, which is the shape of
    failure this repo keeps finding: a green signal measuring something
    adjacent.
    """
    for path in _script_paths():
        _parse(path)


def test_no_module_level_password_literal_under_scripts():
    offenders = {
        str(path.relative_to(_REPO_ROOT)): [name for name, _ in hits]
        for path in _script_paths()
        if (hits := _module_level_password_literals(path))
    }
    assert offenders == {}, (
        "these scripts assign a string literal to a password-shaped name at "
        f"module level: {offenders}. Read it from the environment at run time "
        "instead, after the production guard has passed, the way "
        "seed_demo_firm_config.get_demo_password does."
    )
