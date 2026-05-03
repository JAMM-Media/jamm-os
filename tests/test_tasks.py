# tests/test_tasks.py


def test_admin_can_create_task(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    client_resp = client.post("/clients/", json={"name": "Task Client"}, headers=headers)
    assert client_resp.status_code == 201

    engagement_resp = client.post("/engagements/", json={
        "name": "Tax Return 2024",
        "client_id": client_resp.json()["id"]
    }, headers=headers)
    assert engagement_resp.status_code == 201

    task_payload = {
        "title": "Admin-Created Task",
        "client_id": client_resp.json()["id"],
        "engagement_id": engagement_resp.json()["id"]
    }
    task_resp = client.post("/tasks/", json=task_payload, headers=headers)
    assert task_resp.status_code == 201
    assert task_resp.json()["title"] == "Admin-Created Task"


def test_client_cannot_list_tasks(client, firm_a_owner):
    owner_headers = firm_a_owner["headers"]

    # firm_owner creates a client_portal_user in their firm
    portal_user = {
        "email": "portaluser@example.com",
        "password": "clientpass123",
        "full_name": "Portal User",
        "role": "client_portal_user",
        "firm_id": firm_a_owner["firm_id"]
    }
    r = client.post("/users/", json=portal_user, headers=owner_headers)
    assert r.status_code == 201

    # Login as that portal user
    login = client.post("/auth/token", json={
        "username": portal_user["email"],
        "password": portal_user["password"]
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    portal_headers = {"Authorization": f"Bearer {token}"}

    # client_portal_user should be blocked from listing tasks
    resp = client.get("/tasks/", headers=portal_headers)
    assert resp.status_code == 403
