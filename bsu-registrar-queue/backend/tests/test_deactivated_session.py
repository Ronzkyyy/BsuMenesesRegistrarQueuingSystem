"""Deactivating an account ends its sessions that are already open: the
next staff request gets a 401 (which the frontend treats as "log out"),
not a 400 the page could ignore and carry on showing stale data.
"""
from app.core.security import ACCOUNT_DEACTIVATED_DETAIL
from app.db_models import UserRole


def _login(client, user):
    return client.post(
        "/api/auth/login",
        data={"username": user.username, "password": user._plain_password},
    )


def test_deactivation_ends_an_open_session(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user()

    assert _login(client, admin).status_code == 200
    admin_cookie = client.cookies.get("registrar_token")
    client.cookies.clear()
    assert _login(client, staff).status_code == 200
    staff_cookie = client.cookies.get("registrar_token")
    assert client.get("/api/queues").status_code == 200

    # admin deactivates staff while staff's session is still open
    client.cookies.set("registrar_token", admin_cookie)
    assert client.patch(f"/api/auth/users/{staff.id}/deactivate").status_code == 200

    client.cookies.set("registrar_token", staff_cookie)
    for path in ("/api/queues", "/api/auth/me"):
        resp = client.get(path)
        assert resp.status_code == 401, path
        assert resp.json()["detail"] == ACCOUNT_DEACTIVATED_DETAIL


def test_deactivated_account_cannot_log_in_again(client, make_user, db_session):
    staff = make_user()
    staff.is_active = False
    db_session.commit()

    resp = _login(client, staff)
    assert resp.status_code == 400
    assert "set-cookie" not in resp.headers


def test_reactivated_account_works_again(client, make_user, db_session):
    staff = make_user()
    staff.is_active = False
    db_session.commit()
    staff.is_active = True
    db_session.commit()

    assert _login(client, staff).status_code == 200
    assert client.get("/api/queues").status_code == 200
