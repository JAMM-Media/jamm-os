# tests/test_filesystem_phase8_folder_move.py
"""
Guard tests for Filesystem Phase 8: folder move (re-parenting).

Tests:
  a. Moving a folder into one of its own direct children is refused 422 with a
     cycle-related message. Watched red by temporarily removing the
     descendant-set check from move_folder, confirming the cycle incorrectly
     succeeds and parent_folder_id is set to a descendant, then restoring.
  b. Moving into a deeper (grandchild) descendant is also refused, proving the
     check walks the full descendant set, not just one level.
  c. A move that would push the folder's existing deepest descendant to or past
     MAX_FOLDER_DEPTH is refused, even though the folder itself would not
     exceed the limit if it had no children. Watched red by using only
     get_depth (no subtree_height) in the check, confirming the wrongly-
     permissive version allows the move that pushes a descendant over the
     limit, then restoring.
  d. A legitimate move succeeds and a subsequent GET confirms parent_folder_id
     actually changed.
  e. Auth-before-tree ordering: an unauthorized caller gets 404 before learning
     any tree detail (depth, descendants, cycle status).
"""

import uuid
from unittest.mock import patch

from app.models.document_folder import DocumentFolder
from app.models.engagement_member import EngagementMember
from app.core.enums import UserRole
from app.core.security import get_password_hash
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(test_client, email, password):
    r = test_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_user(firm_id, role=UserRole.staff):
    email = f"user-{uuid.uuid4()}@test.com"
    password = "testpass123"
    db = TestingSessionLocal()
    try:
        from app.models.user import User
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Test User",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()
    return email, password, user_id


def _add_member(firm_id, engagement_id, user_id, *, is_administrator=False):
    db = TestingSessionLocal()
    try:
        member = EngagementMember(
            firm_id=firm_id,
            engagement_id=engagement_id,
            user_id=user_id,
            is_administrator=is_administrator,
        )
        db.add(member)
        db.commit()
    finally:
        db.close()


def _setup_client(test_client, headers, name=None):
    r = test_client.post(
        "/clients/", json={"name": name or f"Client-{uuid.uuid4()}"}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _setup_engagement(test_client, headers, client_id, name=None):
    r = test_client.post(
        "/engagements/",
        json={"name": name or f"Eng-{uuid.uuid4()}", "client_id": client_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_folder_direct(firm_id, engagement_id, client_id, name, parent_folder_id=None):
    """Insert a folder directly into DB, bypassing HTTP and depth checks."""
    from app.crud.document_folder import create_document_folder
    db = TestingSessionLocal()
    try:
        folder = create_document_folder(
            db=db,
            firm_id=uuid.UUID(firm_id),
            scope="engagement",
            name=name,
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(engagement_id),
            parent_folder_id=uuid.UUID(parent_folder_id) if parent_folder_id else None,
        )
        return str(folder.id)
    finally:
        db.close()


def _get_parent_folder_id(folder_id):
    """Read parent_folder_id directly from DB."""
    db = TestingSessionLocal()
    try:
        f = db.query(DocumentFolder).filter(
            DocumentFolder.id == uuid.UUID(folder_id)
        ).first()
        if f is None:
            return "NOT_FOUND"
        return str(f.parent_folder_id) if f.parent_folder_id else None
    finally:
        db.close()


def _move(test_client, headers, folder_id, new_parent_folder_id):
    """PATCH /document-folders/{folder_id}/move."""
    return test_client.patch(
        f"/document-folders/{folder_id}/move",
        json={"new_parent_folder_id": new_parent_folder_id},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# a. Move into direct child is refused 422 with cycle message
# ---------------------------------------------------------------------------

class TestCycleDirectChild:

    def test_move_into_direct_child_returns_422_with_cycle_message(self, client, firm_a_owner):
        """Moving folder F into its own direct child must return 422 with a
        message naming a cycle.

        Watched-fail procedure: temporarily comment out the
        `if new_parent_folder_id in descendant_ids` check in move_folder, run
        this test -- it returns 200 and _get_parent_folder_id(f_id) == child_id,
        proving the cycle was set. Restore the check, test returns 422.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)

        f_id = _create_folder_direct(firm_id, eng_id, client_id, "Parent")
        child_id = _create_folder_direct(firm_id, eng_id, client_id, "Child", parent_folder_id=f_id)

        r = _move(client, headers, f_id, child_id)
        assert r.status_code == 422, (
            f"Move into direct child must return 422; got {r.status_code}: {r.text}"
        )
        assert "cycle" in r.json()["detail"].lower(), (
            f"Detail must mention 'cycle'; got: {r.json()['detail']}"
        )

        # Confirm parent_folder_id was not changed.
        parent_in_db = _get_parent_folder_id(f_id)
        assert parent_in_db is None, (
            f"parent_folder_id must still be None after refused move; got {parent_in_db}"
        )

    def test_move_into_self_returns_422(self, client, firm_a_owner):
        """Moving a folder into itself must also return 422."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)
        f_id = _create_folder_direct(firm_id, eng_id, client_id, "Self")

        r = _move(client, headers, f_id, f_id)
        assert r.status_code == 422, (
            f"Move into self must return 422; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# b. Move into a deeper descendant is also refused
# ---------------------------------------------------------------------------

class TestCycleDeeperDescendant:

    def test_move_into_grandchild_returns_422(self, client, firm_a_owner):
        """Moving folder F into its grandchild (child's child) must return 422,
        proving the check walks the full descendant set, not just one level.

        Watched-fail procedure: replace `if new_parent_folder_id in descendant_ids`
        with `if new_parent_folder_id == folder.id` (only self-check), run this
        test -- it returns 200. Restore the full check, test returns 422.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)

        # Build: F -> Child -> Grandchild
        f_id = _create_folder_direct(firm_id, eng_id, client_id, "F")
        child_id = _create_folder_direct(firm_id, eng_id, client_id, "Child", parent_folder_id=f_id)
        grandchild_id = _create_folder_direct(firm_id, eng_id, client_id, "Grandchild", parent_folder_id=child_id)

        r = _move(client, headers, f_id, grandchild_id)
        assert r.status_code == 422, (
            f"Move into grandchild must return 422; got {r.status_code}: {r.text}"
        )
        assert "cycle" in r.json()["detail"].lower(), (
            f"Detail must mention 'cycle'; got: {r.json()['detail']}"
        )

        # Confirm no change.
        parent_in_db = _get_parent_folder_id(f_id)
        assert parent_in_db is None, (
            f"parent_folder_id must still be None; got {parent_in_db}"
        )


# ---------------------------------------------------------------------------
# c. Subtree depth check: refused when deepest descendant would exceed limit
# ---------------------------------------------------------------------------

class TestSubtreeDepthExceeded:

    def test_move_refused_when_subtree_pushes_past_max_depth(self, client, firm_a_owner):
        """Moving F (which has a 2-level subtree) to a destination 2 levels deep
        is refused when MAX_FOLDER_DEPTH is patched to 5, because
        get_depth(dest) + subtree_height + 1 = 3 + 2 + 1 = 6 >= 5.

        With only get_depth in the check (no subtree_height), the same move
        returns 200 (3 + 1 = 4 < 5), proving the subtree_height term is the
        load-bearing guard that catches descendants-over-limit scenarios.

        Setup uses _create_folder_direct to bypass the real depth check during
        construction, then patches MAX_FOLDER_DEPTH=5 only for the move attempt.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)

        # Build destination chain: dest_root -> dest_lvl1 -> Dest (level 2)
        dest_root_id = _create_folder_direct(firm_id, eng_id, client_id, "DestRoot")
        dest_lvl1_id = _create_folder_direct(firm_id, eng_id, client_id, "DestLvl1", parent_folder_id=dest_root_id)
        dest_id = _create_folder_direct(firm_id, eng_id, client_id, "Dest", parent_folder_id=dest_lvl1_id)

        # Build F with a 2-level subtree: F -> FChild -> FGrandchild
        f_id = _create_folder_direct(firm_id, eng_id, client_id, "F")
        f_child_id = _create_folder_direct(firm_id, eng_id, client_id, "FChild", parent_folder_id=f_id)
        _create_folder_direct(firm_id, eng_id, client_id, "FGrandchild", parent_folder_id=f_child_id)

        # With MAX_FOLDER_DEPTH=5: dest_depth=3, subtree_height=2, check: 3+2+1=6 >= 5 -> refused
        with patch("app.services.document_folder_service.MAX_FOLDER_DEPTH", 5):
            r = _move(client, headers, f_id, dest_id)
        assert r.status_code == 422, (
            f"Move must be refused when subtree pushes past MAX_FOLDER_DEPTH; "
            f"got {r.status_code}: {r.text}"
        )
        assert "depth" in r.json()["detail"].lower() or "limit" in r.json()["detail"].lower(), (
            f"Detail must mention depth limit; got: {r.json()['detail']}"
        )

        # Confirm parent_folder_id unchanged.
        assert _get_parent_folder_id(f_id) is None, "parent_folder_id must still be None"

    def test_move_refused_because_of_subtree_not_folder_itself(self, client, firm_a_owner):
        """The refusal is caused by the subtree, not F itself.

        Verify: moving a LEAF version of F to the same destination succeeds
        with MAX_FOLDER_DEPTH=5, confirming F itself is not the problem.
        Then verify that adding the subtree makes it fail, proving the
        subtree_height term is the deciding factor.

        Watched-fail version: replace check with `dest_depth + 1 >= MAX_FOLDER_DEPTH`
        (omit subtree_height). F-with-subtree move then returns 200 (3+1=4 < 5)
        instead of 422. Restoring the full check makes it fail correctly.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)

        # Destination at level 2: get_depth(dest.id) = 3
        dest_root_id = _create_folder_direct(firm_id, eng_id, client_id, "DestRoot2")
        dest_lvl1_id = _create_folder_direct(firm_id, eng_id, client_id, "DestLvl1b", parent_folder_id=dest_root_id)
        dest_id = _create_folder_direct(firm_id, eng_id, client_id, "Dest2", parent_folder_id=dest_lvl1_id)

        # Leaf F (no children): get_subtree_height = 0. Check: 3+0+1=4 < 5 -> allowed.
        leaf_id = _create_folder_direct(firm_id, eng_id, client_id, "Leaf")

        with patch("app.services.document_folder_service.MAX_FOLDER_DEPTH", 5):
            r_leaf = _move(client, headers, leaf_id, dest_id)
        assert r_leaf.status_code == 200, (
            f"Leaf move must succeed (no subtree); got {r_leaf.status_code}: {r_leaf.text}"
        )

        # Now F2 with subtree_height=2: check 3+2+1=6 >= 5 -> refused.
        f2_id = _create_folder_direct(firm_id, eng_id, client_id, "F2")
        f2_child_id = _create_folder_direct(firm_id, eng_id, client_id, "F2Child", parent_folder_id=f2_id)
        _create_folder_direct(firm_id, eng_id, client_id, "F2Grand", parent_folder_id=f2_child_id)

        # Dest is already occupied by leaf; use a fresh dest.
        dest_root_b = _create_folder_direct(firm_id, eng_id, client_id, "DestRootB")
        dest_lvl1_b = _create_folder_direct(firm_id, eng_id, client_id, "DestLvl1B", parent_folder_id=dest_root_b)
        dest_b = _create_folder_direct(firm_id, eng_id, client_id, "DestB", parent_folder_id=dest_lvl1_b)

        with patch("app.services.document_folder_service.MAX_FOLDER_DEPTH", 5):
            r_subtree = _move(client, headers, f2_id, dest_b)
        assert r_subtree.status_code == 422, (
            f"Move with subtree must be refused; got {r_subtree.status_code}: {r_subtree.text}"
        )


# ---------------------------------------------------------------------------
# d. Legitimate move succeeds and GET confirms parent_folder_id changed
# ---------------------------------------------------------------------------

class TestLegitimateMove:

    def test_legitimate_move_succeeds_and_parent_updated(self, client, firm_a_owner):
        """Moving folder A to be a child of folder B succeeds (200) and a
        subsequent DB read confirms A.parent_folder_id == B.id."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)

        a_id = _create_folder_direct(firm_id, eng_id, client_id, "A")
        b_id = _create_folder_direct(firm_id, eng_id, client_id, "B")

        r = _move(client, headers, a_id, b_id)
        assert r.status_code == 200, (
            f"Legitimate move must return 200; got {r.status_code}: {r.text}"
        )

        parent_in_db = _get_parent_folder_id(a_id)
        assert parent_in_db == b_id, (
            f"After move, A.parent_folder_id must be {b_id}; got {parent_in_db}"
        )
        assert r.json()["parent_folder_id"] == b_id, (
            f"Response parent_folder_id must be {b_id}; got {r.json()['parent_folder_id']}"
        )

    def test_move_to_root_succeeds(self, client, firm_a_owner):
        """Moving a non-root folder to root (new_parent_folder_id=null) succeeds
        and parent_folder_id becomes None."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)

        parent_id = _create_folder_direct(firm_id, eng_id, client_id, "Parent")
        child_id = _create_folder_direct(firm_id, eng_id, client_id, "Child", parent_folder_id=parent_id)

        r = _move(client, headers, child_id, None)
        assert r.status_code == 200, (
            f"Move to root must return 200; got {r.status_code}: {r.text}"
        )

        parent_in_db = _get_parent_folder_id(child_id)
        assert parent_in_db is None, (
            f"After move to root, parent_folder_id must be None; got {parent_in_db}"
        )
        assert r.json()["parent_folder_id"] is None, (
            f"Response parent_folder_id must be None; got {r.json()['parent_folder_id']}"
        )


# ---------------------------------------------------------------------------
# e. Auth-before-tree ordering: unauthorized caller gets 404 before tree details
# ---------------------------------------------------------------------------

class TestAuthBeforeTreeDetails:

    def test_non_trio_member_gets_404_before_cycle_check(self, client, firm_a_owner):
        """A plain (non-administrator) engagement member gets 404 when trying to
        move a folder. This confirms auth is checked before the cycle or depth
        logic runs, so the caller never learns tree details.

        The test uses a cycle scenario (child into parent) that WOULD return
        422 for an authorized caller. The non-trio caller must get 404 instead,
        proving the check order is auth -> tree.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id = _setup_client(client, owner_headers)
        eng_id = _setup_engagement(client, owner_headers, client_id)

        f_id = _create_folder_direct(firm_id, eng_id, client_id, "F")
        child_id = _create_folder_direct(firm_id, eng_id, client_id, "Child", parent_folder_id=f_id)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = _move(client, staff_headers, f_id, child_id)
        assert r.status_code == 404, (
            f"Non-trio member must get 404 (not 422 cycle error); "
            f"got {r.status_code}: {r.text}"
        )

    def test_wrong_firm_gets_404_not_tree_detail(self, client, firm_a_owner, firm_b_owner):
        """A user from a different firm gets 404 when attempting a move,
        not a cycle or depth error that would reveal tree structure."""
        firm_id_a = firm_a_owner["firm_id"]
        owner_a_headers = firm_a_owner["headers"]
        owner_b_headers = firm_b_owner["headers"]

        client_id = _setup_client(client, owner_a_headers)
        eng_id = _setup_engagement(client, owner_a_headers, client_id)

        f_id = _create_folder_direct(firm_id_a, eng_id, client_id, "F")
        child_id = _create_folder_direct(firm_id_a, eng_id, client_id, "Child", parent_folder_id=f_id)

        r = _move(client, owner_b_headers, f_id, child_id)
        assert r.status_code == 404, (
            f"Wrong-firm caller must get 404; got {r.status_code}: {r.text}"
        )

    def test_engagement_administrator_staff_can_move(self, client, firm_a_owner):
        """A staff-role user with is_administrator=True on the engagement is in
        the trio and must succeed -- 200 with parent_folder_id changed in the DB.

        This is the positive direction of the trio gate. The two denial tests
        above only confirm that non-members and wrong-firm callers are refused;
        this test confirms the gate grants access correctly to a legitimate
        non-elevated-role administrator, matching the pattern proven for every
        other trio check built in this session.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id = _setup_client(client, owner_headers)
        eng_id = _setup_engagement(client, owner_headers, client_id)

        a_id = _create_folder_direct(firm_id, eng_id, client_id, "AdminA")
        b_id = _create_folder_direct(firm_id, eng_id, client_id, "AdminB")

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=True)
        admin_headers = _login(client, email, password)

        r = _move(client, admin_headers, a_id, b_id)
        assert r.status_code == 200, (
            f"Engagement administrator must succeed on move; got {r.status_code}: {r.text}"
        )

        parent_in_db = _get_parent_folder_id(a_id)
        assert parent_in_db == b_id, (
            f"After admin move, parent_folder_id must be {b_id}; got {parent_in_db}"
        )
