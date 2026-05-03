# tests/test_phase11_security_headers.py


# ---------------------------------------------------------------------------
# Test 1: Strict-Transport-Security contains max-age=31536000
# ---------------------------------------------------------------------------
def test_hsts_header(client):
    r = client.get("/api/health")
    assert "strict-transport-security" in r.headers
    assert "max-age=31536000" in r.headers["strict-transport-security"]


# ---------------------------------------------------------------------------
# Test 2: X-Content-Type-Options: nosniff
# ---------------------------------------------------------------------------
def test_x_content_type_options(client):
    r = client.get("/api/health")
    assert r.headers.get("x-content-type-options") == "nosniff"


# ---------------------------------------------------------------------------
# Test 3: X-Frame-Options: DENY
# ---------------------------------------------------------------------------
def test_x_frame_options(client):
    r = client.get("/api/health")
    assert r.headers.get("x-frame-options") == "DENY"


# ---------------------------------------------------------------------------
# Test 4: Referrer-Policy header is present
# ---------------------------------------------------------------------------
def test_referrer_policy(client):
    r = client.get("/api/health")
    assert "referrer-policy" in r.headers
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"


# ---------------------------------------------------------------------------
# Test 5: Permissions-Policy header is present
# ---------------------------------------------------------------------------
def test_permissions_policy(client):
    r = client.get("/api/health")
    assert "permissions-policy" in r.headers
    assert "camera=()" in r.headers["permissions-policy"]


# ---------------------------------------------------------------------------
# Test 6: Content-Security-Policy contains default-src 'self'
# ---------------------------------------------------------------------------
def test_csp_default_src(client):
    r = client.get("/api/health")
    assert "content-security-policy" in r.headers
    assert "default-src 'self'" in r.headers["content-security-policy"]


# ---------------------------------------------------------------------------
# Test 7: Content-Security-Policy contains frame-ancestors 'none'
# ---------------------------------------------------------------------------
def test_csp_frame_ancestors(client):
    r = client.get("/api/health")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


# ---------------------------------------------------------------------------
# Test 8: Security headers present on POST /auth/token regardless of status
# ---------------------------------------------------------------------------
def test_security_headers_on_post_endpoint(client):
    # Send a POST to /auth/token (will return 422 for missing body — that's fine)
    r = client.post("/auth/token", json={})
    required_headers = [
        "strict-transport-security",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "permissions-policy",
        "content-security-policy",
    ]
    for header in required_headers:
        assert header in r.headers, f"Missing header: {header}"
