from tests.test_main import client
import uuid

def test_create_and_get_client():
    client_data = {
        "name": "Test Client",
        "email": "client@example.com",
        "phone": "123-456-7890"
    }

    r = client.post("/clients/", json=client_data)
    assert r.status_code == 201
    created = r.json()
    assert created["name"] == client_data["name"]

    # Get client by ID
    r = client.get(f"/clients/{created['id']}")
    assert r.status_code == 200
    assert r.json()["email"] == client_data["email"]

def test_create_client_invalid_email(client):
    r = client.post("/clients/", json={"name": "Invalid Email Client", "email": "not-an-email"})
    assert r.status_code == 422

def test_create_client_missing_fields(client):
    r = client.post("/clients/", json={})
    assert r.status_code == 422

def test_get_client_invalid_uuid(client):
    r = client.get("/clients/invalid-uuid")
    assert r.status_code == 422  # UUID validation should fail

def test_get_nonexistent_client(client):
    fake_id = str(uuid.uuid4())
    r = client.get(f"/clients/{fake_id}")
    assert r.status_code == 404

def test_duplicate_client_email(client):
    email = "duplicate@example.com"
    data = {"name": "Client A", "email": email}
    
    # First creation should work
    r1 = client.post("/clients/", json=data)
    assert r1.status_code == 201

    # Second creation should fail
    r2 = client.post("/clients/", json=data)
    assert r2.status_code == 400 or r2.status_code == 409  # Depending on how you handle conflict
