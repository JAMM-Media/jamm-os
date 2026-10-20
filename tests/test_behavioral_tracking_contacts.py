# tests/test_behavioral_tracking_contacts.py

"""
Phase 7 behavioral event wiring: contacts.

Pinning tests were written against the router-to-crud code BEFORE the writes
moved into contact_service, watched green there, and left unchanged across the
move. They read the contacts table directly.
"""

import uuid
from unittest.mock import patch

from sqlalchemy import text

from tests.conftest import TestingSessionLocal


def _new_client(client, headers, name="Contact Client"):
    r = client.post("/clients/", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _new_contact(client, headers, client_id, **fields):
    body = {"name": "Joey Tester", "email": "joey@test.com", "phone": "1231231234", "client_id": client_id}
    body.update(fields)
    r = client.post("/contacts/", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _read_contact(contact_id):
    db = TestingSessionLocal()
    try:
        row = db.execute(
            text("SELECT name, email, phone, is_active FROM contacts WHERE id = CAST(:cid AS uuid)"),
            {"cid": str(contact_id)},
        ).one_or_none()
    finally:
        db.close()
    return None if row is None else {"name": row[0], "email": row[1], "phone": row[2], "is_active": row[3]}


# ---------------------------------------------------------------------------
# Pinning tests: behavior before the service move
# ---------------------------------------------------------------------------

def test_pin_patch_contact_updates_only_sent_fields(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    contact_id = _new_contact(client, headers, _new_client(client, headers))

    r = client.patch(f"/contacts/{contact_id}", json={"phone": "999", "is_active": False}, headers=headers)

    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "999"
    assert _read_contact(contact_id) == {
        "name": "Joey Tester", "email": "joey@test.com", "phone": "999", "is_active": False,
    }


def test_pin_patch_missing_contact_is_404(client, firm_a_owner):
    r = client.patch(f"/contacts/{uuid.uuid4()}", json={"phone": "1"}, headers=firm_a_owner["headers"])
    assert r.status_code == 404
    assert r.json()["detail"] == "Contact not found"


def test_pin_patch_other_firms_contact_is_404_and_untouched(client, firm_a_owner, firm_b_owner):
    headers_a = firm_a_owner["headers"]
    contact_id = _new_contact(client, headers_a, _new_client(client, headers_a))

    r = client.patch(f"/contacts/{contact_id}", json={"phone": "1"}, headers=firm_b_owner["headers"])

    assert r.status_code == 404
    assert _read_contact(contact_id)["phone"] == "1231231234"


def test_pin_delete_contact_is_204_and_row_is_gone(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    contact_id = _new_contact(client, headers, _new_client(client, headers))

    r = client.delete(f"/contacts/{contact_id}", headers=headers)

    assert r.status_code == 204
    assert _read_contact(contact_id) is None


def test_pin_delete_other_firms_contact_is_404_and_row_survives(client, firm_a_owner, firm_b_owner):
    headers_a = firm_a_owner["headers"]
    contact_id = _new_contact(client, headers_a, _new_client(client, headers_a))

    r = client.delete(f"/contacts/{contact_id}", headers=firm_b_owner["headers"])

    assert r.status_code == 404
    assert r.json()["detail"] == "Contact not found"
    assert _read_contact(contact_id) is not None


# ---------------------------------------------------------------------------
# Event tests: contact.created / contact.updated / contact.deleted
# ---------------------------------------------------------------------------

def _user_id(email):
    db = TestingSessionLocal()
    try:
        return db.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
    finally:
        db.close()


def _events(mock_log, event_type):
    return [c.kwargs for c in mock_log.call_args_list if c.kwargs.get("event_type") == event_type]


def test_contact_created_fires_event(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _new_client(client, headers)

    with patch("app.services.contact_service.log_event") as mock_log:
        contact_id = _new_contact(client, headers, client_id)

    events = _events(mock_log, "contact.created")
    assert len(events) == 1
    e = events[0]
    assert str(e["firm_id"]) == firm_a_owner["firm_id"]
    assert e["entity_type"] == "contact"
    assert str(e["entity_id"]) == contact_id
    assert e["actor_type"] == "staff"
    assert e["actor_id"] == _user_id("owner@firma.com")
    assert e["metadata"] == {"client_id": client_id, "is_active": True}


def test_contact_updated_fires_event_with_changed_fields(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    contact_id = _new_contact(client, headers, _new_client(client, headers))

    with patch("app.services.contact_service.log_event") as mock_log:
        r = client.patch(
            f"/contacts/{contact_id}",
            json={"phone": "999", "name": "Joey Tester"},
            headers=headers,
        )

    assert r.status_code == 200, r.text
    events = _events(mock_log, "contact.updated")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == contact_id
    assert e["actor_id"] == _user_id("owner@firma.com")
    assert e["metadata"] == {
        "changed_fields": {"phone": {"from": "1231231234", "to": "999"}},
    }


def test_contact_deleted_fires_event(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _new_client(client, headers)
    contact_id = _new_contact(client, headers, client_id)

    with patch("app.services.contact_service.log_event") as mock_log:
        r = client.delete(f"/contacts/{contact_id}", headers=headers)

    assert r.status_code == 204
    events = _events(mock_log, "contact.deleted")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == contact_id
    assert e["actor_id"] == _user_id("owner@firma.com")
    assert e["metadata"] == {"client_id": client_id}


# ---------------------------------------------------------------------------
# Scope addition (ruled Oct 12, 2026): create refuses another firm's client
# ---------------------------------------------------------------------------

def test_create_contact_with_another_firms_client_is_404_and_writes_nothing(
    client, firm_a_owner, firm_b_owner,
):
    firm_b_client_id = _new_client(client, firm_b_owner["headers"], name="Firm B Client")

    with patch("app.services.contact_service.log_event") as mock_log:
        r = client.post(
            "/contacts/",
            json={"name": "Leak Attempt", "client_id": firm_b_client_id},
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 404
    assert r.json()["detail"] == "Client not found"
    db = TestingSessionLocal()
    try:
        count = db.execute(
            text("SELECT count(*) FROM contacts WHERE client_id = CAST(:cid AS uuid)"),
            {"cid": firm_b_client_id},
        ).scalar_one()
    finally:
        db.close()
    assert count == 0
    assert _events(mock_log, "contact.created") == []
