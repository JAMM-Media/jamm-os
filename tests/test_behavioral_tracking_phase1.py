# tests/test_behavioral_tracking_phase1.py

import uuid
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.schemas.firm import FirmCreate
from app.services import firm_service


# ---------------------------------------------------------------------------
# Test 1 -- client.created with referral_source persists and logs the field
# ---------------------------------------------------------------------------
def test_client_created_with_referral_source_persists_and_logs(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    with patch("app.services.client_service.log_event") as mock_log:
        r = client.post(
            "/clients/",
            json={
                "name": "Referral Client",
                "email": "referral-client@example.com",
                "referral_source": "google_search",
            },
            headers=headers,
        )

    assert r.status_code == 201, r.text
    assert r.json()["referral_source"] == "google_search"

    created_calls = [
        c for c in mock_log.call_args_list if c.kwargs["event_type"] == "client.created"
    ]
    assert len(created_calls) == 1
    assert created_calls[0].kwargs["metadata"]["referral_source"] == "google_search"


# ---------------------------------------------------------------------------
# Test 2 -- updating a non-evented client field fires client.updated with delta
# ---------------------------------------------------------------------------
def test_client_update_non_evented_field_fires_client_updated(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    create_r = client.post(
        "/clients/",
        json={"name": "Contact Test", "email": "contact-test@example.com", "phone": "111-1111"},
        headers=headers,
    )
    assert create_r.status_code == 201, create_r.text
    client_id = create_r.json()["id"]

    # The client update path's log_event calls are all bound via a local
    # `from app.services.behavioral_log import log_event` import inside
    # app/api/clients.py::update_client, so the source module is the
    # correct patch target.
    with patch("app.services.behavioral_log.log_event") as mock_log:
        update_r = client.patch(
            f"/clients/{client_id}",
            json={"phone": "555-9999"},
            headers=headers,
        )

    assert update_r.status_code == 200, update_r.text
    assert update_r.json()["phone"] == "555-9999"

    updated_calls = [
        c for c in mock_log.call_args_list if c.kwargs["event_type"] == "client.updated"
    ]
    assert len(updated_calls) == 1
    changed_fields = updated_calls[0].kwargs["metadata"]["changed_fields"]
    assert changed_fields == {"phone": {"from": "111-1111", "to": "555-9999"}}


# ---------------------------------------------------------------------------
# Test 3 -- a sensitive-named field change is redacted in the delta
# ---------------------------------------------------------------------------
def test_client_update_sensitive_field_is_redacted(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    create_r = client.post(
        "/clients/",
        json={"name": "Sensitive Field Test", "email": "sensitive-test@example.com", "tax_id": "12-3456789"},
        headers=headers,
    )
    assert create_r.status_code == 201, create_r.text
    client_id = create_r.json()["id"]

    with patch("app.services.behavioral_log.log_event") as mock_log:
        update_r = client.patch(
            f"/clients/{client_id}",
            json={"tax_id": "98-7654321"},
            headers=headers,
        )

    assert update_r.status_code == 200, update_r.text

    updated_calls = [
        c for c in mock_log.call_args_list if c.kwargs["event_type"] == "client.updated"
    ]
    assert len(updated_calls) == 1
    changed_fields = updated_calls[0].kwargs["metadata"]["changed_fields"]
    assert changed_fields == {"tax_id": {"from": "redacted", "to": "redacted"}}


# ---------------------------------------------------------------------------
# Test 3b -- build_changed_fields redacts sensitive fields directly (unit-level)
# ---------------------------------------------------------------------------
def test_build_changed_fields_redacts_sensitive_field_names():
    from app.services.behavioral_log import build_changed_fields

    changed = build_changed_fields(
        {"tax_id": "12-3456789", "phone": "111-1111"},
        {"tax_id": "98-7654321", "phone": "222-2222"},
    )

    assert changed["tax_id"] == {"from": "redacted", "to": "redacted"}
    assert changed["phone"] == {"from": "111-1111", "to": "222-2222"}


# ---------------------------------------------------------------------------
# Test 4 -- firm creation fires firm.created
# ---------------------------------------------------------------------------
def test_firm_creation_fires_firm_created():
    db = TestingSessionLocal()
    actor_id = uuid.uuid4()
    unique = uuid.uuid4()
    payload = FirmCreate(
        name=f"New Firm {unique}",
        slug=f"new-firm-{unique}",
        signup_source="conference",
    )

    try:
        with patch("app.services.firm_service.log_event") as mock_log:
            firm = firm_service.create_firm(db, payload, current_user_id=actor_id)
    finally:
        db.close()

    assert firm.signup_source == "conference"
    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "firm.created"
    assert call_kwargs["entity_type"] == "firm"
    assert call_kwargs["entity_id"] == firm.id
    assert call_kwargs["actor_type"] == "staff"
    assert call_kwargs["actor_id"] == actor_id
    assert call_kwargs["metadata"]["signup_source"] == "conference"
    assert call_kwargs["metadata"]["plan_tier"] == "trial"
