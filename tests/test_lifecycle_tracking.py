# tests/test_lifecycle_tracking.py

import uuid
from unittest.mock import MagicMock, patch

from app.api.users import update_user, update_user_cost_rate, _CostRateBody
from app.api.clients import update_client
from app.core.enums import UserRole
from app.schemas.user import UserUpdate
from app.schemas.client import ClientUpdate


def _mock_user(role=UserRole.staff, is_active=True, totp_enabled=False, cost_rate=None):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.role = role
    user.is_active = is_active
    user.totp_enabled = totp_enabled
    user.cost_rate = cost_rate
    return user


def _mock_client(entity_type="individual", entity_subtype=None, is_active=True, portal_access_enabled=True):
    client = MagicMock()
    client.id = uuid.uuid4()
    client.entity_type = entity_type
    client.entity_subtype = entity_subtype
    client.is_active = is_active
    client.portal_access_enabled = portal_access_enabled
    return client


def _request():
    req = MagicMock()
    req.headers = {}
    req.client = None
    return req


# ---------------------------------------------------------------------------
# Test 1 -- role change fires user.role_changed with from_role/to_role
# ---------------------------------------------------------------------------
def test_user_role_change_fires_event():
    mock_db = MagicMock()
    old_user = _mock_user(role=UserRole.staff)
    mock_db.query.return_value.filter.return_value.first.return_value = old_user

    updated_user = _mock_user(role=UserRole.manager)
    user_in = UserUpdate(role=UserRole.manager)

    current_firm = MagicMock(id=uuid.uuid4())
    current_user = MagicMock(id=uuid.uuid4())

    with patch("app.api.users.crud_user.update_user", return_value=updated_user), \
         patch("app.api.users.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_user(
            user_id=old_user.id,
            user_in=user_in,
            request=_request(),
            db=mock_db,
            current_firm=current_firm,
            current_user=current_user,
            _=None,
        )

    role_calls = [c for c in mock_log.call_args_list if c.kwargs["event_type"] == "user.role_changed"]
    assert len(role_calls) == 1
    assert role_calls[0].kwargs["metadata"]["from_role"] == str(UserRole.staff)
    assert role_calls[0].kwargs["metadata"]["to_role"] == str(UserRole.manager)


# ---------------------------------------------------------------------------
# Test 2 -- deactivation fires user.active_changed with to_active False
# ---------------------------------------------------------------------------
def test_user_deactivation_fires_event():
    mock_db = MagicMock()
    old_user = _mock_user(is_active=True)
    mock_db.query.return_value.filter.return_value.first.return_value = old_user

    updated_user = _mock_user(is_active=False)
    user_in = UserUpdate(is_active=False)

    current_firm = MagicMock(id=uuid.uuid4())
    current_user = MagicMock(id=uuid.uuid4())

    with patch("app.api.users.crud_user.update_user", return_value=updated_user), \
         patch("app.api.users.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_user(
            user_id=old_user.id,
            user_in=user_in,
            request=_request(),
            db=mock_db,
            current_firm=current_firm,
            current_user=current_user,
            _=None,
        )

    active_calls = [c for c in mock_log.call_args_list if c.kwargs["event_type"] == "user.active_changed"]
    assert len(active_calls) == 1
    assert active_calls[0].kwargs["metadata"]["to_active"] is False


# ---------------------------------------------------------------------------
# Test 3 -- no change fires none of the three user events
# ---------------------------------------------------------------------------
def test_user_no_change_fires_nothing():
    mock_db = MagicMock()
    old_user = _mock_user(role=UserRole.staff, is_active=True, totp_enabled=False)
    mock_db.query.return_value.filter.return_value.first.return_value = old_user

    updated_user = _mock_user(role=UserRole.staff, is_active=True, totp_enabled=False)
    user_in = UserUpdate(full_name="Same Name")

    current_firm = MagicMock(id=uuid.uuid4())
    current_user = MagicMock(id=uuid.uuid4())

    with patch("app.api.users.crud_user.update_user", return_value=updated_user), \
         patch("app.api.users.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_user(
            user_id=old_user.id,
            user_in=user_in,
            request=_request(),
            db=mock_db,
            current_firm=current_firm,
            current_user=current_user,
            _=None,
        )

    fired_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "user.role_changed" not in fired_types
    assert "user.active_changed" not in fired_types
    assert "user.totp_changed" not in fired_types


# ---------------------------------------------------------------------------
# Test 4 -- cost rate event now captures from_cost_rate/to_cost_rate
# ---------------------------------------------------------------------------
def test_cost_rate_captures_old_value():
    mock_db = MagicMock()
    user = _mock_user(cost_rate=50.0)
    mock_db.query.return_value.filter.return_value.first.return_value = user

    current_firm = MagicMock(id=uuid.uuid4())
    body = _CostRateBody(cost_rate=75.0)

    with patch("app.services.behavioral_log.log_event") as mock_log:
        update_user_cost_rate(
            user_id=user.id,
            body=body,
            db=mock_db,
            current_firm=current_firm,
            _=None,
        )

    cost_calls = [c for c in mock_log.call_args_list if c.kwargs["event_type"] == "staff.cost_rate_set"]
    assert len(cost_calls) == 1
    metadata = cost_calls[0].kwargs["metadata"]
    assert metadata["from_cost_rate"] == 50.0
    assert metadata["to_cost_rate"] == 75.0
    assert metadata["cost_rate"] == 75.0
    assert metadata["user_id"] == str(user.id)


# ---------------------------------------------------------------------------
# Test 5 -- entity type change fires client.entity_changed
# ---------------------------------------------------------------------------
def test_client_entity_change_fires_event():
    mock_db = MagicMock()
    old_client = _mock_client(entity_type="individual", entity_subtype=None)

    updated_client = _mock_client(entity_type="business", entity_subtype="llc")
    payload = ClientUpdate(entity_type="business", entity_subtype="llc")

    current_firm = MagicMock(id=uuid.uuid4())
    current_user = MagicMock(id=uuid.uuid4())

    with patch("app.api.clients.crud_client.get_client_for_firm", return_value=old_client), \
         patch("app.api.clients.crud_client.update_client", return_value=updated_client), \
         patch("app.services.audit_service.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_client(
            client_id=old_client.id,
            payload=payload,
            db=mock_db,
            current_firm=current_firm,
            _=None,
            current_user=current_user,
        )

    entity_calls = [c for c in mock_log.call_args_list if c.kwargs["event_type"] == "client.entity_changed"]
    assert len(entity_calls) == 1
    assert entity_calls[0].kwargs["metadata"]["from_entity_type"] == "individual"
    assert entity_calls[0].kwargs["metadata"]["to_entity_type"] == "business"


# ---------------------------------------------------------------------------
# Test 6 -- portal access revoke fires client.portal_access_changed with to_enabled False
# ---------------------------------------------------------------------------
def test_client_portal_access_revoke_fires_event():
    mock_db = MagicMock()
    old_client = _mock_client(portal_access_enabled=True)

    updated_client = _mock_client(portal_access_enabled=False)
    payload = ClientUpdate(is_active=True)

    current_firm = MagicMock(id=uuid.uuid4())
    current_user = MagicMock(id=uuid.uuid4())

    with patch("app.api.clients.crud_client.get_client_for_firm", return_value=old_client), \
         patch("app.api.clients.crud_client.update_client", return_value=updated_client), \
         patch("app.services.audit_service.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_client(
            client_id=old_client.id,
            payload=payload,
            db=mock_db,
            current_firm=current_firm,
            _=None,
            current_user=current_user,
        )

    portal_calls = [c for c in mock_log.call_args_list if c.kwargs["event_type"] == "client.portal_access_changed"]
    assert len(portal_calls) == 1
    assert portal_calls[0].kwargs["metadata"]["to_enabled"] is False


# ---------------------------------------------------------------------------
# Test 7 -- no change fires no client lifecycle events
# ---------------------------------------------------------------------------
def test_client_no_change_fires_nothing():
    mock_db = MagicMock()
    old_client = _mock_client(entity_type="individual", entity_subtype=None, is_active=True, portal_access_enabled=True)

    updated_client = _mock_client(entity_type="individual", entity_subtype=None, is_active=True, portal_access_enabled=True)
    payload = ClientUpdate(name="Same Name")

    current_firm = MagicMock(id=uuid.uuid4())
    current_user = MagicMock(id=uuid.uuid4())

    with patch("app.api.clients.crud_client.get_client_for_firm", return_value=old_client), \
         patch("app.api.clients.crud_client.update_client", return_value=updated_client), \
         patch("app.services.audit_service.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_client(
            client_id=old_client.id,
            payload=payload,
            db=mock_db,
            current_firm=current_firm,
            _=None,
            current_user=current_user,
        )

    fired_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "client.entity_changed" not in fired_types
    assert "client.active_changed" not in fired_types
    assert "client.portal_access_changed" not in fired_types
