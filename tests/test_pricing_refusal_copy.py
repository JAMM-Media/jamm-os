# tests/test_pricing_refusal_copy.py

"""Guards on pricing refusal COPY, not on pricing logic.

Server refusal strings are rendered verbatim by the settings UI, so they are
load-bearing interface text rather than developer diagnostics. Two things are
pinned here:

  1. The dimension display rule ruled Aug 26, 2026 (_dimension_display).
  2. That no refusal detail string ever names change_dimension_direction as
     the way to clear a price or remove children.

Both have been watched to fail. The controls are recorded in the session
report: the display helper was broken so the question_text branch returned the
fallback form, and the phrase was re-inserted into a single refusal detail.
Each break was reverted, the test re-run green, and the working tree diffed
against git.
"""

import ast
import pathlib
import uuid

import pytest

from app.core.enums import DimensionKind
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_flag import ComplexityFlag
from app.services.pricing_config_service import _dimension_display
from tests.conftest import TestingSessionLocal


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _dimension(db, flag, key: str, question_text):
    row = ComplexityDimension(
        flag_id=flag.id,
        key=key,
        kind=DimensionKind.numeric_range,
        question_text=question_text,
        hierarchy_rank=1,
        linkable=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1. The display rule.
# ---------------------------------------------------------------------------

def test_dimension_display_rule(db):
    """Pins the Aug 26, 2026 ruling on how a dimension is named in refusals.

    complexity_dimensions has no label column, so the copy is composed from the
    flag name plus question_text when the content session has filled it, and
    from the flag name plus the catalog key in parentheses when it has not.

    The fallback keeping the key is the load-bearing half. question_text is
    nullable across the whole shipped catalog today, so the fallback is the
    form users actually see, and two dimensions under one flag have to stay
    distinguishable in a refusal that names both. Whitespace-only question_text
    counts as absent: a content session that saves an empty box must not
    produce "Crypto activity: " with nothing after the colon.
    """
    flag = ComplexityFlag(key=f"crypto-{uuid.uuid4().hex[:8]}", name="Crypto activity")
    db.add(flag)
    db.commit()
    db.refresh(flag)

    answered = _dimension(
        db, flag, "txn_volume", "How many crypto transactions last year?"
    )
    unanswered = _dimension(db, flag, "wallet_count", None)
    blank = _dimension(db, flag, "staking_hours", "   \n\t  ")

    assert _dimension_display(db, answered) == (
        "Crypto activity: How many crypto transactions last year?"
    )
    assert _dimension_display(db, unanswered) == "Crypto activity (wallet_count)"
    assert _dimension_display(db, blank) == "Crypto activity (staking_hours)"

    # The point of keeping the key: two dimensions under one flag, both still
    # awaiting content, do not collapse into the same string.
    assert _dimension_display(db, unanswered) != _dimension_display(db, blank)


# ---------------------------------------------------------------------------
# 2. The wrong instruction is gone and stays gone.
# ---------------------------------------------------------------------------

# Refusal copy told owners to clear a price "via change_dimension_direction"
# until Aug 26, 2026. That function deletes every tier and option price
# belonging to the moved config and everything below it, so the instruction
# pointed at data loss rather than at clearing one price.
_FORBIDDEN_IN_REFUSALS = "change_dimension_direction"

_SERVICE = pathlib.Path(__file__).resolve().parents[1] / "app" / "services" / (
    "pricing_config_service.py"
)


def _detail_strings(path: pathlib.Path):
    """Every string literal reachable from a detail= argument to HTTPException.

    Parsed rather than grepped on purpose. The module legitimately names the
    real change_dimension_direction function in its docstrings, in comments and
    in code, and a regex over the whole file would either trip on those or be
    loosened until it stopped guarding anything. Scoping to the detail keyword
    is the precise question: what does the user actually read?
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name != "HTTPException":
            continue
        detail = next(
            (kw.value for kw in node.keywords if kw.arg == "detail"),
            node.args[1] if len(node.args) > 1 else None,
        )
        if detail is None:
            continue
        for part in ast.walk(detail):
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                found.append((node.lineno, part.value))
    return found


def test_no_refusal_names_change_dimension_direction():
    """No refusal a user reads may name change_dimension_direction.

    Guards defect A from the Aug 26, 2026 copy pass. The three refusals that
    carried this instruction were rewritten to say what actually clears a
    price, and nothing new may reintroduce it. Docstring, comment and call-site
    references to the real function are deliberately allowed: this reads only
    the detail= argument of HTTPException, which is the text the settings UI
    renders verbatim.
    """
    details = _detail_strings(_SERVICE)

    # The parse has to have found something, or the assertion below is vacuous
    # and would stay green against a file with every refusal removed.
    assert len(details) > 20, f"only {len(details)} detail strings parsed; check the parser"

    offenders = [
        f"{_SERVICE.name}:{line} -> {text!r}"
        for line, text in details
        if _FORBIDDEN_IN_REFUSALS in text
    ]
    assert not offenders, (
        "refusal copy names change_dimension_direction, which deletes every "
        "tier and option price below the config rather than clearing one "
        "price:\n  " + "\n  ".join(offenders)
    )
