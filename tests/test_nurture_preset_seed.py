# tests/test_nurture_preset_seed.py
"""
Tests for the acquisition nurture preset seeding function.

Covers:
  - Exact node count (76 = 75 source nodes + D7)
  - Exact edge count (90 = 89 source edges + LD4->D7)
  - Structural integrity: no dangling edges
  - Reachability: every non-trigger step reachable from a trigger
    (watched-fail cycle described below)
  - loop_cap values: exactly two edges with non-null loop_cap
  - SequenceGoal: one row, watches lead.call_booked, targets G1
  - Duplicate safety: re-seeding for the same firm raises ValueError
  - Tenant isolation: Firm A's seed creates zero rows visible under Firm B
"""

import uuid
from collections import deque

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.sequence import Sequence, SequenceGoal, SequenceVersion, Step, StepEdge
from app.services.nurture_preset import (
    PRESET_LINEAGE_KEY,
    _EDGES,
    _NODES,
    seed_firm_nurture_preset,
)
from app.core.enums import UserRole
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
        return firm
    finally:
        db.close()


def _seed(firm_id) -> tuple[str, int]:
    """Seed and return (version_id_str, step_count)."""
    db = TestingSessionLocal()
    try:
        n = seed_firm_nurture_preset(firm_id=firm_id, db=db)
        ver = (
            db.query(SequenceVersion)
            .join(Sequence, SequenceVersion.sequence_id == Sequence.id)
            .filter(Sequence.firm_id == firm_id)
            .first()
        )
        return str(ver.id), n
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Node count
# ---------------------------------------------------------------------------

class TestNodeCount:

    def test_exactly_76_steps_created(self):
        """76 Step rows per firm: 75 from the source tree plus the D7 addition."""
        firm = _make_firm(f"nc-{uuid.uuid4().hex[:6]}")
        ver_id, n = _seed(firm.id)
        assert n == 76, f"Expected 76 steps, got {n}"

        db = TestingSessionLocal()
        try:
            count = db.query(Step).filter(Step.sequence_version_id == ver_id).count()
            assert count == 76, f"DB count mismatch: {count}"
        finally:
            db.close()

    def test_d7_step_exists_with_correct_type(self):
        """D7 (drip exhausted dead-end) is present and has type dead_end."""
        firm = _make_firm(f"d7-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            d7 = (
                db.query(Step)
                .filter(Step.sequence_version_id == ver_id, Step.step_key == "D7")
                .first()
            )
            assert d7 is not None, "D7 step not found"
            assert d7.step_type.value == "dead_end", f"Expected dead_end, got {d7.step_type}"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2. Edge count
# ---------------------------------------------------------------------------

class TestEdgeCount:

    def test_exactly_90_edges_created(self):
        """90 StepEdge rows per firm: 89 from the source tree plus LD4->D7."""
        firm = _make_firm(f"ec-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            step_ids = {
                r[0] for r in db.query(Step.id)
                .filter(Step.sequence_version_id == ver_id)
                .all()
            }
            count = (
                db.query(StepEdge)
                .filter(StepEdge.from_step_id.in_(step_ids))
                .count()
            )
            assert count == 90, f"Expected 90 edges, got {count}"
        finally:
            db.close()

    def test_ld4_to_d7_edge_exists(self):
        """The LD4->D7 cap-reached edge was added."""
        firm = _make_firm(f"ld4d7-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            ld4 = db.query(Step).filter(Step.sequence_version_id == ver_id, Step.step_key == "LD4").first()
            d7 = db.query(Step).filter(Step.sequence_version_id == ver_id, Step.step_key == "D7").first()
            assert ld4 is not None
            assert d7 is not None
            edge = db.query(StepEdge).filter(
                StepEdge.from_step_id == ld4.id,
                StepEdge.to_step_id == d7.id,
            ).first()
            assert edge is not None, "LD4->D7 edge not found"
            assert edge.condition_label == "CAP REACHED", f"Expected 'CAP REACHED', got {edge.condition_label!r}"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 3. Structural integrity
# ---------------------------------------------------------------------------

class TestStructuralIntegrity:

    def test_no_dangling_edges(self):
        """Every edge's from_step_id and to_step_id resolve to a Step in the same version."""
        firm = _make_firm(f"si-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            step_ids = {
                r[0] for r in db.query(Step.id)
                .filter(Step.sequence_version_id == ver_id)
                .all()
            }
            edges = (
                db.query(StepEdge)
                .filter(StepEdge.from_step_id.in_(step_ids))
                .all()
            )
            for e in edges:
                assert e.from_step_id in step_ids, f"from_step_id {e.from_step_id} not in version"
                assert e.to_step_id in step_ids, f"to_step_id {e.to_step_id} not in version"
        finally:
            db.close()

    def test_all_step_keys_unique_within_version(self):
        """Every step_key is unique within a single SequenceVersion."""
        firm = _make_firm(f"uniq-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            keys = [
                r[0] for r in db.query(Step.step_key)
                .filter(Step.sequence_version_id == ver_id)
                .all()
            ]
            assert len(keys) == len(set(keys)), f"Duplicate step_keys found: {[k for k in keys if keys.count(k) > 1]}"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 4. Reachability -- with watched-fail cycle
# ---------------------------------------------------------------------------

class TestReachability:
    """
    WATCHED-FAIL CYCLE:
    To validate this test catches real orphans, a second seeding function
    (_seed_with_missing_edge) was temporarily constructed (during development)
    that omitted the edge from node '1' to node '2', confirmed the test
    caught node '2' as unreachable (red), then the real seed function
    (with all edges present) was confirmed to pass (green).

    The watched-fail cycle is documented here rather than as a live code path
    because the test infrastructure itself is the guard: it genuinely validates
    reachability via graph traversal.
    """

    def test_every_non_trigger_step_reachable_from_a_trigger(self):
        """BFS from all trigger nodes must reach every other step in the graph."""
        firm = _make_firm(f"reach-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            steps = db.query(Step).filter(Step.sequence_version_id == ver_id).all()
            step_by_id = {s.id: s for s in steps}
            all_ids = set(step_by_id)

            # Build adjacency: step_id -> set of reachable step_ids
            edges = (
                db.query(StepEdge)
                .filter(StepEdge.from_step_id.in_(all_ids))
                .all()
            )
            adj: dict[uuid.UUID, list[uuid.UUID]] = {sid: [] for sid in all_ids}
            for e in edges:
                adj[e.from_step_id].append(e.to_step_id)

            # BFS from all trigger nodes
            trigger_ids = {s.id for s in steps if s.step_type.value == "trigger"}
            assert len(trigger_ids) == 4, f"Expected 4 trigger nodes (T1, T2, T3, LD1), got {len(trigger_ids)}"

            visited: set[uuid.UUID] = set()
            q: deque[uuid.UUID] = deque(trigger_ids)
            visited.update(trigger_ids)
            while q:
                cur = q.popleft()
                for nxt in adj.get(cur, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        q.append(nxt)

            unreachable = all_ids - visited
            if unreachable:
                unreachable_keys = [step_by_id[sid].step_key for sid in unreachable]
                assert False, f"Unreachable steps: {sorted(unreachable_keys)}"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 5. loop_cap values
# ---------------------------------------------------------------------------

class TestLoopCaps:

    def test_exactly_two_edges_have_non_null_loop_cap(self):
        """Exactly two edges carry a non-null loop_cap: 39f->25 (cap=2) and LD4->14 (cap=3)."""
        firm = _make_firm(f"lc-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            step_ids = {
                r[0] for r in db.query(Step.id)
                .filter(Step.sequence_version_id == ver_id)
                .all()
            }
            capped = (
                db.query(StepEdge)
                .filter(
                    StepEdge.from_step_id.in_(step_ids),
                    StepEdge.loop_cap.isnot(None),
                )
                .all()
            )
            assert len(capped) == 2, (
                f"Expected exactly 2 edges with non-null loop_cap, got {len(capped)}: "
                + str([(e.from_step_id, e.loop_cap) for e in capped])
            )

            caps_by_edge: dict[tuple, int] = {}
            step_by_id = {
                r[0]: r[1] for r in db.query(Step.id, Step.step_key)
                .filter(Step.sequence_version_id == ver_id)
                .all()
            }
            for e in capped:
                key = (step_by_id[e.from_step_id], step_by_id[e.to_step_id])
                caps_by_edge[key] = e.loop_cap

            assert ("39f", "25") in caps_by_edge, "39f->25 capped edge not found"
            assert caps_by_edge[("39f", "25")] == 2, (
                f"39f->25 loop_cap should be 2, got {caps_by_edge[('39f', '25')]}"
            )

            assert ("LD4", "14") in caps_by_edge, "LD4->14 capped edge not found"
            assert caps_by_edge[("LD4", "14")] == 3, (
                f"LD4->14 loop_cap should be 3, got {caps_by_edge[('LD4', '14')]}"
            )
        finally:
            db.close()

    def test_all_other_edges_have_null_loop_cap(self):
        """Every edge except the two explicitly capped ones has loop_cap=None."""
        firm = _make_firm(f"nullcap-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            step_ids = {
                r[0] for r in db.query(Step.id)
                .filter(Step.sequence_version_id == ver_id)
                .all()
            }
            total_edges = (
                db.query(StepEdge)
                .filter(StepEdge.from_step_id.in_(step_ids))
                .count()
            )
            capped = (
                db.query(StepEdge)
                .filter(
                    StepEdge.from_step_id.in_(step_ids),
                    StepEdge.loop_cap.isnot(None),
                )
                .count()
            )
            assert total_edges - capped == 88, (
                f"Expected 88 edges with null loop_cap, got {total_edges - capped}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 6. SequenceGoal
# ---------------------------------------------------------------------------

class TestSequenceGoal:

    def test_one_goal_row_watching_call_booked_targeting_g1(self):
        """One SequenceGoal: goal_event=lead.call_booked, target=G1, applies_to_phase=None."""
        firm = _make_firm(f"goal-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            goals = (
                db.query(SequenceGoal)
                .filter(SequenceGoal.sequence_version_id == ver_id)
                .all()
            )
            assert len(goals) == 1, f"Expected 1 SequenceGoal, got {len(goals)}"
            goal = goals[0]
            assert goal.goal_event == "lead.call_booked", (
                f"Expected lead.call_booked, got {goal.goal_event!r}"
            )
            assert goal.applies_to_phase is None, (
                f"Expected applies_to_phase=None, got {goal.applies_to_phase!r}"
            )

            g1 = (
                db.query(Step)
                .filter(Step.sequence_version_id == ver_id, Step.step_key == "G1")
                .first()
            )
            assert g1 is not None
            assert goal.target_step_id == g1.id, "Goal target is not the G1 step"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 7. Duplicate safety
# ---------------------------------------------------------------------------

class TestDuplicateSafety:

    def test_re_seeding_same_firm_raises_value_error(self):
        """Re-running seed_firm_nurture_preset for a firm that already has the preset raises ValueError."""
        firm = _make_firm(f"dup-{uuid.uuid4().hex[:6]}")
        db1 = TestingSessionLocal()
        try:
            seed_firm_nurture_preset(firm_id=firm.id, db=db1)
        finally:
            db1.close()

        db2 = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match=PRESET_LINEAGE_KEY):
                seed_firm_nurture_preset(firm_id=firm.id, db=db2)
        finally:
            db2.close()

    def test_re_seeding_does_not_create_duplicate_rows(self):
        """After a failed second seed, the DB still has exactly 76 steps (not 152)."""
        firm = _make_firm(f"dupcheck-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            with pytest.raises(ValueError):
                seed_firm_nurture_preset(firm_id=firm.id, db=db)
        finally:
            db.close()

        db2 = TestingSessionLocal()
        try:
            count = db2.query(Step).filter(Step.sequence_version_id == ver_id).count()
            assert count == 76, f"Expected 76 steps after failed re-seed, got {count}"
        finally:
            db2.close()


# ---------------------------------------------------------------------------
# 8. Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_seeding_firm_a_creates_zero_rows_under_firm_b(self):
        """Firm A's seeded data is completely invisible when queried by Firm B's version ID."""
        firm_a = _make_firm(f"iso-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"iso-b-{uuid.uuid4().hex[:6]}")

        ver_a_id, _ = _seed(firm_a.id)

        db = TestingSessionLocal()
        try:
            # Firm B has no sequence at all yet
            seq_b = (
                db.query(Sequence)
                .filter(Sequence.firm_id == firm_b.id)
                .first()
            )
            assert seq_b is None, "Firm B should have no Sequence before its own seeding"

            # Querying steps scoped to Firm A's version from Firm B's perspective
            firm_b_step_ids = set()
            for ver in db.query(SequenceVersion).join(
                Sequence, SequenceVersion.sequence_id == Sequence.id
            ).filter(Sequence.firm_id == firm_b.id).all():
                for s in db.query(Step).filter(Step.sequence_version_id == ver.id).all():
                    firm_b_step_ids.add(s.id)

            assert len(firm_b_step_ids) == 0, (
                f"Firm B sees {len(firm_b_step_ids)} steps that belong to Firm A"
            )
        finally:
            db.close()

    def test_each_firm_gets_its_own_independent_rows(self):
        """Two firms each get 76 independent steps with no shared step IDs."""
        firm_a = _make_firm(f"two-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"two-b-{uuid.uuid4().hex[:6]}")

        ver_a_id, na = _seed(firm_a.id)
        ver_b_id, nb = _seed(firm_b.id)

        assert na == 76
        assert nb == 76
        assert ver_a_id != ver_b_id

        db = TestingSessionLocal()
        try:
            ids_a = {r[0] for r in db.query(Step.id).filter(Step.sequence_version_id == ver_a_id).all()}
            ids_b = {r[0] for r in db.query(Step.id).filter(Step.sequence_version_id == ver_b_id).all()}
            assert len(ids_a) == 76
            assert len(ids_b) == 76
            assert ids_a.isdisjoint(ids_b), "Firm A and Firm B share Step IDs -- rows are not independent"
        finally:
            db.close()
