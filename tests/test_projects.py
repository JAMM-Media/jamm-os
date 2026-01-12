from tests.test_main import client


def test_create_and_get_project():
    # Create client first
    client_payload = {"name": "Proj Client"}
    r = client.post("/clients/", json=client_payload)
    assert r.status_code == 201
    client_id = r.json()["id"]

    project_data = {
        "client_id": client_id,
        "name": "New Project"
    }

    r = client.post("/projects/", json=project_data)
    assert r.status_code == 201
    project = r.json()

    r = client.get(f"/projects/{project['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "New Project"

def test_create_project_missing_fields(client):
    response = client.post("/projects/", json={"name": "New Project"})
    assert response.status_code == 422  # Assuming 'client_id' is required

def test_get_nonexistent_project(client):
    response = client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
