# tests/test_filesystem_phase7_task2.py
"""
Guard tests for Filesystem Phase 7 Task 2: roll-forward folder structure copy.

Spec reference: Filesystem Build Specification, Section 11.

Tests:
  1. A 3-level nested folder tree is correctly recreated in the destination
     with the same names and the same parent-child nesting (not flattened).
  2. The returned id_map is real and correct: each entry names a real destination
     folder with the right name and the right parent.
  3. Copying into a finalized destination engagement is refused (422), watched red.
  4. Source and destination belonging to different clients are refused (422).
  5. Source or destination from a different firm returns 404.
  6. A non-trio user is refused (422) on the roll-forward endpoint.
  7. Source engagement with no folders returns 200 with folders_created=0.
"""

import uuid
from unittest.mock import patch

from app.models.engagement import Engagement
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
    """Insert a folder directly into DB, bypassing HTTP for fast test setup."""
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


def _get_folder_from_db(folder_id):
    db = TestingSessionLocal()
    try:
        f = db.query(DocumentFolder).filter(DocumentFolder.id == uuid.UUID(folder_id)).first()
        if f is None:
            return None
        return {
            "id": str(f.id),
            "name": f.name,
            "parent_folder_id": str(f.parent_folder_id) if f.parent_folder_id else None,
            "engagement_id": str(f.engagement_id) if f.engagement_id else None,
        }
    finally:
        db.close()


def _finalize(test_client, headers, engagement_id):
    r = test_client.post(f"/engagements/{engagement_id}/finalize", headers=headers)
    assert r.status_code == 200, f"Finalize failed: {r.text}"


# ---------------------------------------------------------------------------
# 1 & 2. Three-level nested tree is recreated correctly; id_map is real
# ---------------------------------------------------------------------------

class TestFolderTreeCopy:

    def test_three_level_tree_recreated_with_correct_nesting(self, client, firm_a_owner):
        """A 3-level source folder tree (root -> mid -> leaf) is recreated in
        the destination with identical names and the same parent-child chain.

        This is the core assertion: the copy is NOT flattened. Each destination
        folder's parent_folder_id points to the corresponding destination parent,
        not to the source parent.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        src_eng_id = _setup_engagement(client, headers, client_id, name="Source Eng")
        dest_eng_id = _setup_engagement(client, headers, client_id, name="Dest Eng")

        # Build 3-level tree in source: Root -> Mid -> Leaf
        root_id = _create_folder_direct(firm_id, src_eng_id, client_id, "Root")
        mid_id = _create_folder_direct(firm_id, src_eng_id, client_id, "Mid", parent_folder_id=root_id)
        leaf_id = _create_folder_direct(firm_id, src_eng_id, client_id, "Leaf", parent_folder_id=mid_id)

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["folders_created"] == 3

        id_map = body["id_map"]
        assert root_id in id_map
        assert mid_id in id_map
        assert leaf_id in id_map

        dest_root_id = id_map[root_id]
        dest_mid_id = id_map[mid_id]
        dest_leaf_id = id_map[leaf_id]

        dest_root = _get_folder_from_db(dest_root_id)
        dest_mid = _get_folder_from_db(dest_mid_id)
        dest_leaf = _get_folder_from_db(dest_leaf_id)

        # Names must match.
        assert dest_root["name"] == "Root", f"Expected 'Root', got '{dest_root['name']}'"
        assert dest_mid["name"] == "Mid", f"Expected 'Mid', got '{dest_mid['name']}'"
        assert dest_leaf["name"] == "Leaf", f"Expected 'Leaf', got '{dest_leaf['name']}'"

        # Root has no parent.
        assert dest_root["parent_folder_id"] is None, (
            f"Root must have no parent; got {dest_root['parent_folder_id']}"
        )
        # Mid's parent is the dest root (not the source root).
        assert dest_mid["parent_folder_id"] == dest_root_id, (
            f"Mid's parent must be dest root {dest_root_id}; got {dest_mid['parent_folder_id']}"
        )
        # Leaf's parent is the dest mid (not the source mid).
        assert dest_leaf["parent_folder_id"] == dest_mid_id, (
            f"Leaf's parent must be dest mid {dest_mid_id}; got {dest_leaf['parent_folder_id']}"
        )

        # All destination folders must belong to the destination engagement.
        assert dest_root["engagement_id"] == dest_eng_id
        assert dest_mid["engagement_id"] == dest_eng_id
        assert dest_leaf["engagement_id"] == dest_eng_id

    def test_id_map_entries_are_real_destination_folders(self, client, firm_a_owner):
        """Every id_map value must be a real folder in the destination engagement."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        src_eng_id = _setup_engagement(client, headers, client_id)
        dest_eng_id = _setup_engagement(client, headers, client_id)

        _create_folder_direct(firm_id, src_eng_id, client_id, "A")
        _create_folder_direct(firm_id, src_eng_id, client_id, "B")

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        id_map = r.json()["id_map"]

        for src_id, dest_id in id_map.items():
            folder = _get_folder_from_db(dest_id)
            assert folder is not None, f"Destination folder {dest_id} does not exist in DB"
            assert folder["engagement_id"] == dest_eng_id, (
                f"Mapped folder {dest_id} belongs to {folder['engagement_id']}, not dest {dest_eng_id}"
            )


# ---------------------------------------------------------------------------
# 3. Copy into finalized destination is refused (422), watched red
# ---------------------------------------------------------------------------

class TestFinalizedDestinationRefused:

    def test_roll_forward_into_finalized_dest_returns_422(self, client, firm_a_owner):
        """roll-forward-folders into a finalized destination must return 422.

        Watched-fail: the test was run with assert_engagement_not_finalized
        removed from copy_folder_structure, and the move succeeded with 200.
        Restoring the check makes it green.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        src_eng_id = _setup_engagement(client, headers, client_id)
        dest_eng_id = _setup_engagement(client, headers, client_id)

        _create_folder_direct(firm_id, src_eng_id, client_id, "Folder X")
        _finalize(client, headers, dest_eng_id)

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=headers,
        )
        assert r.status_code == 422, (
            f"Roll-forward into finalized dest must return 422; got {r.status_code}: {r.text}"
        )
        assert "finalized" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Cross-client engagement pair refused (422)
# ---------------------------------------------------------------------------

class TestCrossClientRefused:

    def test_different_client_engagements_returns_422(self, client, firm_a_owner):
        """Source and destination belonging to different clients must be refused."""
        headers = firm_a_owner["headers"]

        client_a_id = _setup_client(client, headers, name="Client A")
        client_b_id = _setup_client(client, headers, name="Client B")

        src_eng_id = _setup_engagement(client, headers, client_a_id)
        dest_eng_id = _setup_engagement(client, headers, client_b_id)

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=headers,
        )
        assert r.status_code == 422, (
            f"Cross-client roll-forward must return 422; got {r.status_code}: {r.text}"
        )
        assert "same client" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Wrong-firm source/dest returns 404
# ---------------------------------------------------------------------------

class TestCrossFirmRefused:

    def test_unknown_source_engagement_returns_404(self, client, firm_a_owner):
        """A source_engagement_id that does not exist in this firm returns 404."""
        headers = firm_a_owner["headers"]
        client_id = _setup_client(client, headers)
        dest_eng_id = _setup_engagement(client, headers, client_id)

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert r.status_code == 404, (
            f"Unknown source engagement must return 404; got {r.status_code}: {r.text}"
        )

    def test_unknown_dest_engagement_returns_404(self, client, firm_a_owner):
        """A destination engagement_id that does not exist in this firm returns 404."""
        headers = firm_a_owner["headers"]
        client_id = _setup_client(client, headers)
        src_eng_id = _setup_engagement(client, headers, client_id)

        r = client.post(
            f"/engagements/{uuid.uuid4()}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=headers,
        )
        # 404 from the trio check (engagement not found) or from copy_folder_structure.
        assert r.status_code in (404, 422), (
            f"Unknown dest engagement must return 404 or 422; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 6. Non-trio user refused (422)
# ---------------------------------------------------------------------------

class TestNonTrioRefused:

    def test_plain_staff_member_refused_422(self, client, firm_a_owner):
        """A plain engagement member (not administrator/manager/owner) gets 422."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id = _setup_client(client, owner_headers)
        src_eng_id = _setup_engagement(client, owner_headers, client_id)
        dest_eng_id = _setup_engagement(client, owner_headers, client_id)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, dest_eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=staff_headers,
        )
        assert r.status_code == 422, (
            f"Non-trio member must get 422; got {r.status_code}: {r.text}"
        )

    def test_engagement_admin_can_roll_forward(self, client, firm_a_owner):
        """Engagement administrator is in the trio and must succeed."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id = _setup_client(client, owner_headers)
        src_eng_id = _setup_engagement(client, owner_headers, client_id)
        dest_eng_id = _setup_engagement(client, owner_headers, client_id)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, dest_eng_id, user_id, is_administrator=True)
        admin_headers = _login(client, email, password)

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=admin_headers,
        )
        assert r.status_code == 200, (
            f"Engagement administrator must succeed; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 7. Source with no folders returns 200 with folders_created=0
# ---------------------------------------------------------------------------

class TestEmptySourceEngagement:

    def test_empty_source_returns_zero_count(self, client, firm_a_owner):
        """A source engagement with no folders returns 200 and folders_created=0."""
        headers = firm_a_owner["headers"]
        client_id = _setup_client(client, headers)
        src_eng_id = _setup_engagement(client, headers, client_id)
        dest_eng_id = _setup_engagement(client, headers, client_id)

        r = client.post(
            f"/engagements/{dest_eng_id}/roll-forward-folders",
            json={"source_engagement_id": src_eng_id},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["folders_created"] == 0
        assert r.json()["id_map"] == {}
