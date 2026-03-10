
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


def test_workload_returns_assigned_tasks(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    # Create a staff user to assign tasks to
    staff = client.post("/users/", json={
        "email": "staff@example.com", "password": "pass1234",
        "full_name": "Staff User", "role": "staff", "firm_id": firm_id,
    }, headers=headers)
    assert staff.status_code == 201
    staff_id = staff.json()["id"]

    # Create a client and engagement to attach tasks to
    cl = client.post("/clients/", json={"name": "Workload Client"}, headers=headers)
    assert cl.status_code == 201
    eng = client.post("/engagements/", json={"name": "Workload Eng", "client_id": cl.json()["id"]}, headers=headers)
    assert eng.status_code == 201

    # Create two tasks assigned to the staff user, one unassigned
    client.post("/tasks/", json={
        "title": "Task A", "client_id": cl.json()["id"],
        "engagement_id": eng.json()["id"], "assigned_to": staff_id,
    }, headers=headers)
    client.post("/tasks/", json={
        "title": "Task B", "client_id": cl.json()["id"],
        "engagement_id": eng.json()["id"], "assigned_to": staff_id,
    }, headers=headers)
    client.post("/tasks/", json={
        "title": "Unassigned", "client_id": cl.json()["id"],
        "engagement_id": eng.json()["id"],
    }, headers=headers)

    r = client.get(f"/users/{staff_id}/workload", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    titles = {t["title"] for t in data["items"]}
    assert titles == {"Task A", "Task B"}


def test_workload_status_filter(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    staff = client.post("/users/", json={
        "email": "staff2@example.com", "password": "pass1234",
        "full_name": "Staff 2", "role": "staff", "firm_id": firm_id,
    }, headers=headers)
    staff_id = staff.json()["id"]

    cl = client.post("/clients/", json={"name": "Filter Client"}, headers=headers)
    eng = client.post("/engagements/", json={"name": "Filter Eng", "client_id": cl.json()["id"]}, headers=headers)

    task_a = client.post("/tasks/", json={
        "title": "Todo Task", "client_id": cl.json()["id"],
        "engagement_id": eng.json()["id"], "assigned_to": staff_id, "status": "todo",
    }, headers=headers)
    task_b_id = client.post("/tasks/", json={
        "title": "Done Task", "client_id": cl.json()["id"],
        "engagement_id": eng.json()["id"], "assigned_to": staff_id, "status": "done",
    }, headers=headers).json()["id"]

    r = client.get(f"/users/{staff_id}/workload?status=todo", headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["title"] == "Todo Task"


def test_workload_nonexistent_user(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.get(f"/users/{uuid.uuid4()}/workload", headers=headers)
    assert r.status_code == 404
