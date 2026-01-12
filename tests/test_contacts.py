from tests.test_main import client


def test_create_and_get_contact():
    r = client.post("/clients/", json={"name": "Contact Client"})
    client_id = r.json()["id"]

    contact_data = {
        "first_name": "Joey",
        "last_name": "Tester",
        "email": "joey@test.com",
        "phone": "1231231234",
        "client_id": client_id
    }

    r = client.post("/contacts/", json=contact_data)
    assert r.status_code == 201
    contact_id = r.json()["id"]

    r = client.get(f"/contacts/{contact_id}")
    assert r.status_code == 200
    assert r.json()["email"] == "joey@test.com"

def test_create_contact_missing_required_fields(client):
    response = client.post("/contacts/", json={"first_name": "John"})
    assert response.status_code == 422

def test_get_nonexistent_contact(client):
    response = client.get("/contacts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
