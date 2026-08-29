"""Secure HTTP headers on API responses (the SPA's headers come from nginx).

The `client` fixture leaves DEBUG at its default (True), so these assert the
dev behaviour; the prod-only additions (HSTS, upgrade-insecure-requests) are
toggled explicitly below.
"""
from app.core.config import settings


def test_baseline_headers_present(client):
    h = client.get("/").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert h["cross-origin-opener-policy"] == "same-origin"
    assert h["cross-origin-resource-policy"] == "same-site"
    assert h["server"] == "api"


def test_api_csp_is_locked_down(client):
    csp = client.get("/api/queues/active").headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_hsts_only_in_production(client):
    assert "strict-transport-security" not in {k.lower() for k in client.get("/").headers}

    settings.DEBUG = False
    try:
        h = client.get("/").headers
        assert h["strict-transport-security"] == "max-age=31536000; includeSubDomains"
        assert "upgrade-insecure-requests" in h["content-security-policy"]
    finally:
        settings.DEBUG = True


def test_docs_route_is_exempt_from_strict_csp(client):
    # DEBUG defaults True, so /openapi.json is served; it must NOT carry the
    # default-src 'none' policy or the Swagger UI CDN assets would be blocked.
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "content-security-policy" not in {k.lower() for k in resp.headers}
