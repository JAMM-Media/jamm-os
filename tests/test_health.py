from tests.test_main import client


def test_health():
    r = client.get("/")  # change this from /api/health
    assert r.status_code == 200
    assert r.json() == {"message": "JAMM OS is running"}
