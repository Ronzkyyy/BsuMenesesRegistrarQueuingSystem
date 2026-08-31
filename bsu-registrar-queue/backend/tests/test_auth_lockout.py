"""Failed-login lockout: an account is locked after
MAX_FAILED_LOGIN_ATTEMPTS consecutive bad passwords and stays locked (even
for the correct password) until ACCOUNT_LOCKOUT_MINUTES pass. Any success
resets the counter.
"""
from datetime import datetime, timedelta, timezone

from app.core.config import settings


def _login(client, username, password):
    return client.post("/api/auth/login", data={"username": username, "password": password})


def test_wrong_password_increments_counter(client, make_user):
    user = make_user()

    resp = _login(client, user.username, "wrong")
    assert resp.status_code == 401
    assert user.failed_login_attempts == 1


def test_account_locks_after_threshold_failures(client, make_user):
    user = make_user()

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        assert _login(client, user.username, "wrong").status_code == 401

    # threshold reached: counter reset, locked_until set in the future
    assert user.failed_login_attempts == 0
    assert user.locked_until is not None

    # even the CORRECT password is refused while locked
    locked = _login(client, user.username, user._plain_password)
    assert locked.status_code == 429
    assert "failed attempts" in locked.json()["detail"].lower()


def test_successful_login_resets_counter(client, make_user):
    user = make_user()

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS - 1):
        assert _login(client, user.username, "wrong").status_code == 401
    assert user.failed_login_attempts == settings.MAX_FAILED_LOGIN_ATTEMPTS - 1

    ok = _login(client, user.username, user._plain_password)
    assert ok.status_code == 200
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


def test_expired_lock_allows_login_again(client, make_user, db_session):
    user = make_user()
    user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    user.failed_login_attempts = 0
    db_session.commit()

    ok = _login(client, user.username, user._plain_password)
    assert ok.status_code == 200
    assert user.locked_until is None


def test_unknown_username_does_not_500(client):
    resp = _login(client, "nobody-here", "whatever")
    assert resp.status_code == 401
