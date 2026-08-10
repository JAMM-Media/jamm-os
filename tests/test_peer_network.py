# tests/test_peer_network.py

import uuid
from datetime import datetime, timezone

from tests.conftest import TestingSessionLocal


def _create_active_member(db, firm_id, email, handle):
    from app.models.user import User
    from app.models.peer_network import PeerNetworkMember
    from app.core.security import get_password_hash
    from app.core.enums import UserRole

    user = User(
        firm_id=firm_id,
        email=email,
        hashed_password=get_password_hash("testpass"),
        full_name=handle,
        role=UserRole.manager,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    member = PeerNetworkMember(
        user_id=user.id,
        firm_id=firm_id,
        handle=handle,
        is_active=True,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return user.email, member.id


def test_peer_network_non_member_cannot_access_dm(client):
    """An active Peer Network member not part of a DM gets 403 on read and post."""
    from app.models.firm import Firm
    from app.models.peer_network import PeerNetworkRoom, PeerNetworkRoomMember

    db = TestingSessionLocal()
    try:
        firm = Firm(
            name="PN Test Firm",
            slug=f"pn-test-{uuid.uuid4().hex[:8]}",
            peer_network_enabled=True,
        )
        db.add(firm)
        db.commit()
        db.refresh(firm)
        firm_id = firm.id

        suffix = uuid.uuid4().hex[:8]
        email1, mid1 = _create_active_member(db, firm_id, f"pn-u1-{suffix}@test.com", f"@pnu1{suffix}")
        email2, mid2 = _create_active_member(db, firm_id, f"pn-u2-{suffix}@test.com", f"@pnu2{suffix}")
        email3, mid3 = _create_active_member(db, firm_id, f"pn-u3-{suffix}@test.com", f"@pnu3{suffix}")

        room = PeerNetworkRoom(room_type="dm", name=None)
        db.add(room)
        db.flush()
        db.add(PeerNetworkRoomMember(room_id=room.id, member_id=mid1))
        db.add(PeerNetworkRoomMember(room_id=room.id, member_id=mid2))
        db.commit()
        room_id = str(room.id)
    finally:
        db.close()

    login3 = client.post("/auth/token", json={"username": email3, "password": "testpass"})
    assert login3.status_code == 200, f"Member 3 login failed: {login3.json()}"
    headers3 = {"Authorization": f"Bearer {login3.json()['access_token']}"}

    r_read = client.get(f"/peer-network/rooms/{room_id}/messages", headers=headers3)
    assert r_read.status_code == 403, (
        f"Non-member should get 403 on read, got {r_read.status_code}: {r_read.json()}"
    )

    r_post = client.post(
        f"/peer-network/rooms/{room_id}/messages",
        json={"body": "should not get through"},
        headers=headers3,
    )
    assert r_post.status_code == 403, (
        f"Non-member should get 403 on post, got {r_post.status_code}: {r_post.json()}"
    )
