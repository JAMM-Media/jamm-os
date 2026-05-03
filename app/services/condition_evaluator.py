# app/services/condition_evaluator.py

import logging
from typing import Any, Dict, List

from app.core.enums import ConditionOperator

logger = logging.getLogger(__name__)


def evaluate(
    conditions: List[Dict[str, Any]],
    payload: Dict[str, Any],
) -> bool:
    if not conditions:
        return True

    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        expected = condition.get("value")
        actual = payload.get(field)
        if not _evaluate_single(actual, operator, expected):
            return False

    return True


def _evaluate_single(actual: Any, operator: str, expected: Any) -> bool:
    if operator == ConditionOperator.equals:
        return actual == expected

    if operator == ConditionOperator.not_equals:
        return actual != expected

    if operator == ConditionOperator.contains:
        if actual is None:
            return False
        if isinstance(actual, (str, list)):
            return expected in actual
        return False

    if operator == ConditionOperator.greater_than:
        try:
            return actual > expected
        except TypeError:
            return False

    if operator == ConditionOperator.less_than:
        try:
            return actual < expected
        except TypeError:
            return False

    if operator == ConditionOperator.is_empty:
        return actual is None or actual == "" or actual == [] or actual == {}

    if operator == ConditionOperator.is_not_empty:
        return not _evaluate_single(actual, ConditionOperator.is_empty, None)

    logger.warning(f"Unknown condition operator: {operator!r} — returning False")
    return False
