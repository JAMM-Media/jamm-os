

def test_health(client):
    r = client.get("/")  # change this from /api/health
    assert r.status_code == 200
    assert r.json() == {"message": "JAMM PX is running"}
