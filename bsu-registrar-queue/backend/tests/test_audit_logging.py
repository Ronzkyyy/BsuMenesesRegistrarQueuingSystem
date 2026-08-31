"""Security-audit logging: the sensitive actions emit a `bsu.security`
record, and no record ever carries a password or token.
"""
import json
import logging

import pytest


@pytest.fixture
def audit():
    """Capture `bsu.security` JSON records via a handler on that logger
    (it runs with propagate=False, so caplog's root handler misses it)."""
    logger = logging.getLogger("bsu.security")
    messages: list[str] = []

    class _Cap(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    handler = _Cap()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield lambda: [json.loads(m) for m in messages]
    finally:
        logger.removeHandler(handler)


def _login(client, username, password, portal=None):
    data = {"username": username, "password": password}
    if portal:
        data["portal"] = portal
    return client.post("/api/auth/login", data=data)


def test_failed_login_is_logged(client, make_user, audit):
    user = make_user()
    _login(client, user.username, "wrong")

    events = audit()
    fail = [e for e in events if e["event"] == "auth.login" and e["outcome"] == "failure"]
    assert len(fail) == 1
    assert fail[0]["actor"] == user.username
    assert fail[0]["detail"] == "bad password"


def test_unknown_user_login_is_logged(client, audit):
    _login(client, "ghost-user", "x")
    events = audit()
    assert any(e["event"] == "auth.login" and e["detail"] == "unknown username"
               for e in events)


def test_successful_login_is_logged(client, make_user, audit):
    user = make_user()
    _login(client, user.username, user._plain_password)

    ok = [e for e in audit() if e["event"] == "auth.login" and e["outcome"] == "success"]
    assert len(ok) == 1
    assert ok[0]["actor"] == user.username


def test_role_denial_is_logged(client, make_user, audit):
    from app.db_models import UserRole
    staff = make_user(role=UserRole.STAFF)
    _login(client, staff.username, staff._plain_password)

    # STAFF hitting an ADMIN-only route - the session cookie set by _login
    # above rides along automatically via the TestClient's cookie jar.
    r = client.get("/api/auth/users")
    assert r.status_code == 403

    denied = [e for e in audit() if e["event"] == "authz.denied"]
    assert len(denied) == 1
    assert denied[0]["actor"] == staff.username
    assert denied[0]["path"] == "/api/auth/users"


def test_records_never_contain_secrets(client, make_user, audit):
    user = make_user(password="SuperSecret-9999")
    _login(client, user.username, "SuperSecret-9999")
    _login(client, user.username, "WrongGuess-0000")

    blob = json.dumps(audit())
    assert "SuperSecret-9999" not in blob
    assert "WrongGuess-0000" not in blob
    assert "access_token" not in blob
