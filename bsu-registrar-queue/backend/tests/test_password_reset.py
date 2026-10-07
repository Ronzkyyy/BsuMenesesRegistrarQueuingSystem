"""Forgotten-password recovery: an admin resets another account to a
system-generated temporary password, the account must replace it before any
staff route will serve it, and the server CLI can reset + unlock when no
admin can log in at all.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from app import cli
from app.core.security import PASSWORD_CHANGE_REQUIRED_DETAIL, verify_password
from app.db_models import UserRole


@pytest.fixture
def audit():
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


def _login(client, user, password=None):
    return client.post(
        "/api/auth/login",
        data={"username": user.username, "password": password or user._plain_password},
    )


def _reset(client, admin, target):
    assert _login(client, admin).status_code == 200
    resp = client.post(f"/api/auth/users/{target.id}/reset-password")
    client.post("/api/auth/logout")
    return resp


# ---- admin reset route ----

def test_admin_reset_issues_temp_password_and_unlocks(client, make_user, db_session):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user()
    staff.failed_login_attempts = 3
    staff.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    db_session.commit()

    resp = _reset(client, admin, staff)

    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
    body = resp.json()
    assert body["username"] == staff.username
    temp = body["temporary_password"]
    assert len(temp) == 14 and temp.count("-") == 2
    assert staff.must_change_password is True
    assert staff.failed_login_attempts == 0
    assert staff.locked_until is None
    # old password no longer works, temporary one does
    assert _login(client, staff).status_code == 401
    assert _login(client, staff, temp).status_code == 200


def test_temp_passwords_are_not_repeated(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user()
    first = _reset(client, admin, staff).json()["temporary_password"]
    second = _reset(client, admin, staff).json()["temporary_password"]
    assert first != second


def test_registrar_cannot_reset(client, make_user):
    registrar = make_user(role=UserRole.REGISTRAR)
    staff = make_user()
    assert _login(client, registrar).status_code == 200
    resp = client.post(f"/api/auth/users/{staff.id}/reset-password")
    assert resp.status_code == 403
    assert verify_password(staff._plain_password, staff.hashed_password)


def test_unauthenticated_cannot_reset(client, make_user):
    staff = make_user()
    assert client.post(f"/api/auth/users/{staff.id}/reset-password").status_code == 401


def test_admin_cannot_reset_self(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    resp = _reset(client, admin, admin)
    assert resp.status_code == 400
    assert admin.must_change_password is False


def test_reset_unknown_and_invalid_ids(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    assert _login(client, admin).status_code == 200
    assert client.post("/api/auth/users/999999/reset-password").status_code == 404
    assert client.post("/api/auth/users/0/reset-password").status_code == 422


def test_reset_is_audited_without_the_password(client, make_user, audit):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user()
    temp = _reset(client, admin, staff).json()["temporary_password"]

    events = [e for e in audit() if e["event"] == "auth.password_reset"]
    assert len(events) == 1
    assert events[0]["actor"] == admin.username
    assert events[0]["target"] == staff.username
    assert all(temp not in json.dumps(e) for e in audit())


# ---- forced change at next login ----

def test_pending_change_blocks_staff_routes_until_changed(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    other_admin = make_user(role=UserRole.ADMIN)
    temp = _reset(client, admin, other_admin).json()["temporary_password"]

    login = _login(client, other_admin, temp)
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True

    # /me still answers so the frontend can route to the change screen...
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    # ...but staff routes refuse, even ones the role would normally allow
    blocked = client.get("/api/auth/users")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == PASSWORD_CHANGE_REQUIRED_DETAIL
    assert client.get("/api/queues").status_code == 403

    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": temp, "new_password": "my-own-pass-1"},
    )
    assert changed.status_code == 200
    assert other_admin.must_change_password is False
    assert client.get("/api/auth/users").status_code == 200
    assert client.get("/api/auth/me").json()["must_change_password"] is False


def test_reset_cuts_off_an_already_open_session(client, make_user, db_session):
    staff = make_user()
    assert _login(client, staff).status_code == 200
    assert client.get("/api/queues").status_code == 200

    staff.must_change_password = True  # what a concurrent admin reset does
    db_session.commit()
    assert client.get("/api/queues").status_code == 403


def test_new_password_must_differ_from_temp(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user()
    temp = _reset(client, admin, staff).json()["temporary_password"]
    assert _login(client, staff, temp).status_code == 200

    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": temp, "new_password": temp},
    )
    assert resp.status_code == 400
    assert staff.must_change_password is True


def test_any_role_can_change_own_password(client, make_user):
    staff = make_user()
    assert _login(client, staff).status_code == 200
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": staff._plain_password, "new_password": "brand-new-pass"},
    )
    assert resp.status_code == 200
    client.post("/api/auth/logout")
    assert _login(client, staff, "brand-new-pass").status_code == 200


def test_change_password_still_requires_current(client, make_user):
    staff = make_user()
    assert _login(client, staff).status_code == 200
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "not-it-at-all", "new_password": "brand-new-pass"},
    )
    assert resp.status_code == 400


# ---- server CLI ----

def _prompter(*answers):
    it = iter(answers)
    return lambda _msg: next(it)


def test_cli_resets_and_unlocks(db_session, make_user, audit):
    admin = make_user(role=UserRole.ADMIN)
    admin.failed_login_attempts = 0
    admin.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    db_session.commit()

    code = cli.run(
        ["reset-password", admin.username], db_session,
        prompt=_prompter("recovered-pass", "recovered-pass"),
    )

    assert code == 0
    assert verify_password("recovered-pass", admin.hashed_password)
    assert admin.locked_until is None
    assert admin.must_change_password is False
    events = [e for e in audit() if e["event"] == "auth.password_reset"]
    assert events and events[-1]["actor"] == "server-cli"
    assert all("recovered-pass" not in json.dumps(e) for e in audit())


def test_cli_temporary_flag_forces_change(db_session, make_user):
    staff = make_user()
    code = cli.run(
        ["reset-password", staff.username, "--temporary"], db_session,
        prompt=_prompter("temp-pass-123", "temp-pass-123"),
    )
    assert code == 0
    assert staff.must_change_password is True


@pytest.mark.parametrize("answers", [
    ("short", "short"),                       # under 8 chars
    ("x" * 73, "x" * 73),                     # over bcrypt's 72 bytes
    ("first-choice", "second-choice"),        # confirmation mismatch
])
def test_cli_rejects_bad_input_and_changes_nothing(db_session, make_user, answers):
    staff = make_user()
    old_hash = staff.hashed_password
    code = cli.run(["reset-password", staff.username], db_session, prompt=_prompter(*answers))
    assert code == 1
    assert staff.hashed_password == old_hash


def test_cli_unknown_user(db_session):
    code = cli.run(["reset-password", "nobody-here"], db_session, prompt=_prompter())
    assert code == 1
