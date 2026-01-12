from tests.test_main import client


def test_create_and_get_task():
    # Create client
    r = client.post("/clients/", json={"name": "Task Client"})
    client_id = r.json()["id"]

    # Create project
    r = client.post("/projects/", json={"client_id": client_id, "name": "Task Project"})
    project_id = r.json()["id"]

    # Create task
    task_data = {
        "client_id": client_id,
        "project_id": project_id,
        "title": "Sample Task"
    }
    r = client.post("/tasks/", json=task_data)
    assert r.status_code == 200
    task = r.json()

    # Retrieve task
    r = client.get(f"/tasks/{task['id']}")
    assert r.status_code == 200
    assert r.json()["title"] == "Sample Task"

def test_create_task_invalid_data(client):
    response = client.post("/tasks/", json={"title": "", "project_id": "not-a-uuid"})
    assert response.status_code in (422, 400)

def test_get_nonexistent_task(client):
    response = client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
