# app/core/technique_floors.py

"""
Every entry in this file is Andrew-owned and changed only by his decision.

Ratchet rule: tightening any floor is allowed without sign-off. Loosening any
floor requires an explicit manual decision by Andrew after reviewing the
shadow-mode would-have-surfaced queue. Posture: undeniable over probable.

Each technique authors its own floors in the build session that creates the
technique, against measured data_sufficiency values, never before.

A technique ABSENT from this registry fails sufficiency closed in
judge_finding. A technique PRESENT with an empty dict is a deliberate,
distinct choice meaning "no sufficiency requirement" and must be justified in
a comment beside the entry.

Known future move: when automatic tightening from dismissal feedback lands
(RL phase, last in the build order), floors must move to a database table so
the system can adjust them at runtime. This module is the correct home until
then.
"""

import copy

# Andrew-owned. Keyed by Finding.technique. Ships empty: no technique has
# authored its floors yet, and authoring one before there is measured data to
# author it against is exactly what the ratchet rule forbids.
FLOORS_BY_TECHNIQUE: dict[str, dict[str, float]] = {}


def get_floors_by_technique() -> dict[str, dict[str, float]]:
    """
    Returns a deep copy of the registry.

    A copy rather than the live dict so no caller can mutate Andrew-owned
    numbers at runtime, by accident or otherwise. The inner dicts are copied
    too: a shallow copy would hand out the same mutable floor dicts.
    """
    return copy.deepcopy(FLOORS_BY_TECHNIQUE)
