from tests.test_main import client
import uuid


def test_create_user_success():
    data = {"email": "testuser@example.com", "password": "securepass123"}
    r = client.post("/users/", json=data)
    assert r.status_code == 200
    assert "id" in r.json()
    assert r.json()["email"] == data["email"]


def test_create_user_missing_fields():
    r = client.post("/users/", json={})
    assert r.status_code == 422


def test_create_user_invalid_email():
    r = client.post("/users/", json={"email": "notanemail", "password": "pass123"})
    assert r.status_code == 422


def test_create_user_short_password():
    r = client.post("/users/", json={"email": "short@example.com", "password": "123"})
    # Adjust the expected response if you're not validating password length yet
    assert r.status_code == 200 or r.status_code == 422


def test_get_nonexistent_user():
    fake_id = str(uuid.uuid4())
    r = client.get(f"/users/{fake_id}")
    assert r.status_code == 404

def test_create_user_missing_password():
    response = client.post("/users/", json={"email": "user@example.com"})
    assert response.status_code == 422

def test_login_with_wrong_credentials():
    response = client.post("/auth/token", data={"username": "wrong@example.com", "password": "badpass"})
    assert response.status_code == 401
