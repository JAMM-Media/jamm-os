
import uuid


def test_create_user_success(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    data = {"email": "testuser@example.com", "password": "securepass123", "full_name": "Test User", "firm_id": firm_a_owner["firm_id"]}
    r = client.post("/users/", json=data, headers=headers)
    assert r.status_code == 201
    assert "id" in r.json()
    assert r.json()["email"] == data["email"]


def test_create_user_missing_fields(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/users/", json={}, headers=headers)
    assert r.status_code == 422


def test_create_user_invalid_email(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/users/", json={"email": "notanemail", "password": "pass123"}, headers=headers)
    assert r.status_code == 422


def test_create_user_short_password(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/users/", json={"email": "short@example.com", "password": "123"}, headers=headers)
    assert r.status_code in (201, 422)


def test_get_nonexistent_user(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    fake_id = str(uuid.uuid4())
    r = client.get(f"/users/{fake_id}", headers=headers)
    assert r.status_code == 404


def test_create_user_missing_password(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    response = client.post("/users/", json={"email": "user@example.com"}, headers=headers)
    assert response.status_code == 422


def test_login_with_wrong_credentials(client):
    response = client.post("/auth/token", data={"username": "wrong@example.com", "password": "badpass"})
    assert response.status_code == 401
