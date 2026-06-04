
import uuid


def test_create_and_get_client(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_data = {
        "name": "Test Client",
        "email": "client@example.com",
        "phone": "123-456-7890"
    }

    r = client.post("/clients/", json=client_data, headers=headers)
    assert r.status_code == 201
    created = r.json()
    assert created["name"] == client_data["name"]

    r = client.get(f"/clients/{created['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == client_data["email"]


def test_create_client_invalid_email(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/clients/", json={"name": "Invalid Email Client", "email": "not-an-email"}, headers=headers)
    assert r.status_code == 422


def test_create_client_missing_fields(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/clients/", json={}, headers=headers)
    assert r.status_code == 422


def test_get_client_invalid_uuid(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.get("/clients/invalid-uuid", headers=headers)
    assert r.status_code == 422


def test_get_nonexistent_client(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    fake_id = str(uuid.uuid4())
    r = client.get(f"/clients/{fake_id}", headers=headers)
    assert r.status_code == 404


def test_duplicate_client_email(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    email = "duplicate@example.com"
    data = {"name": "Client A", "email": email}

    r1 = client.post("/clients/", json=data, headers=headers)
    assert r1.status_code == 201

    r2 = client.post("/clients/", json=data, headers=headers)
    assert r2.status_code in (400, 409)
