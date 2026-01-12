from tests.test_main import client


def test_login_fail():
    r = client.post("/auth/token", data={"username": "wrong@example.com", "password": "badpass"})
    assert r.status_code == 401

def test_user_create_and_login():
    email = "newuser@example.com"
    password = "secure123"

    # Register user
    r = client.post("/users/", json={"email": email, "password": password})
    assert r.status_code == 200
    user_id = r.json()["id"]

    # Login with user
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200
    assert "access_token" in r.json()
