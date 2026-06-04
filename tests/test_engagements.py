# tests/test_engagements.py


def test_create_and_get_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Engagement Client"}, headers=headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    engagement_data = {
        "client_id": client_id,
        "name": "2024 Tax Return"
    }

    r = client.post("/engagements/", json=engagement_data, headers=headers)
    assert r.status_code == 201
    engagement = r.json()
    assert engagement["name"] == "2024 Tax Return"

    r = client.get(f"/engagements/{engagement['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "2024 Tax Return"


def test_create_engagement_missing_client_id(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/engagements/", json={"name": "Orphan Engagement"}, headers=headers)
    assert r.status_code == 422


def test_get_nonexistent_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.get("/engagements/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404


def test_update_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Update Client"}, headers=headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    r = client.post("/engagements/", json={"client_id": client_id, "name": "Original Name"}, headers=headers)
    assert r.status_code == 201
    engagement_id = r.json()["id"]

    r = client.patch(f"/engagements/{engagement_id}", json={"name": "Updated Name"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


def test_delete_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Delete Client"}, headers=headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    r = client.post("/engagements/", json={"client_id": client_id, "name": "To Be Deleted"}, headers=headers)
    assert r.status_code == 201
    engagement_id = r.json()["id"]

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 204

    r = client.get(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 404
