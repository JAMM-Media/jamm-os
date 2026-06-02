

def test_create_and_get_contact(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Contact Client"}, headers=headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    contact_data = {
        "name": "Joey Tester",
        "email": "joey@test.com",
        "phone": "1231231234",
        "client_id": client_id
    }

    r = client.post("/contacts/", json=contact_data, headers=headers)
    assert r.status_code == 201
    contact_id = r.json()["id"]

    r = client.get(f"/contacts/{contact_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "joey@test.com"


def test_create_contact_missing_required_fields(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    response = client.post("/contacts/", json={"email": "x@test.com"}, headers=headers)
    assert response.status_code == 422


def test_get_nonexistent_contact(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    response = client.get("/contacts/00000000-0000-0000-0000-000000000000", headers=headers)
    assert response.status_code == 404
