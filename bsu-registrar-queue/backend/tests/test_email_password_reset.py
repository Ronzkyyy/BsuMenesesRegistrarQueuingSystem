"""Staff email addresses and self-service password reset: admins set an
account's email, its owner confirms it from an emailed link, and a confirmed
email can receive a one-time, 15-minute reset link. Accounts from before
emails existed must add one before any staff route serves them.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.core.config import settings
from app.core.security import EMAIL_REQUIRED_DETAIL, verify_password
from app.db_models import EmailTokenDB, UserRole
from app.services import account_email, email_sender
from app import gmail_auth


@pytest.fixture
def outbox(monkeypatch):
    """Capture outgoing mail instead of sending it, and skip the MX lookup
    (test addresses use a domain that doesn't exist)."""
    sent: list[dict] = []
    monkeypatch.setattr(email_sender, "send_email", lambda **m: sent.append(m) or True)
    monkeypatch.setattr(account_email, "validate_email_deliverable", lambda email: None)
    return sent


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


def _token(message: dict) -> str:
    match = re.search(r"#token=([A-Za-z0-9_-]+)", message["text"])
    assert match, message["text"]
    return match.group(1)


def _login(client, user, password=None):
    return client.post(
        "/api/auth/login",
        data={"username": user.username, "password": password or user._plain_password},
    )


def _as(client, user):
    client.post("/api/auth/logout")
    assert _login(client, user).status_code == 200


def _new_user_payload(**overrides):
    payload = dict(
        username="newstaff", full_name="New Staff", role="staff",
        password="new-staff-pass", email="New.Staff@Example.org",
    )
    payload.update(overrides)
    return payload


# ---- creating accounts ----

def test_register_requires_email(client, make_user, outbox):
    _as(client, make_user(role=UserRole.ADMIN))
    payload = _new_user_payload()
    del payload["email"]
    assert client.post("/api/auth/register", json=payload).status_code == 422
    assert client.post("/api/auth/register", json=_new_user_payload(email="not-an-email")).status_code == 422
    assert outbox == []


def test_register_stores_lowercase_email_and_sends_verification(client, make_user, outbox):
    _as(client, make_user(role=UserRole.ADMIN))
    resp = client.post("/api/auth/register", json=_new_user_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "new.staff@example.org"
    assert body["email_verified_at"] is None

    assert len(outbox) == 1
    assert outbox[0]["to"] == "new.staff@example.org"
    assert "/verify-email#token=" in outbox[0]["text"]
    assert "/verify-email#token=" in outbox[0]["html"]


def test_register_rejects_email_already_in_use(client, make_user, outbox):
    admin = make_user(role=UserRole.ADMIN)
    _as(client, admin)
    resp = client.post("/api/auth/register", json=_new_user_payload(email=admin.email.upper()))
    assert resp.status_code == 400
    assert "already used" in resp.json()["detail"]


def test_register_rejects_undeliverable_domain(client, make_user, outbox, monkeypatch):
    def _fail(email):
        raise ValueError("Email address looks fake or unreachable: no MX")

    monkeypatch.setattr(account_email, "validate_email_deliverable", _fail)
    _as(client, make_user(role=UserRole.ADMIN))
    resp = client.post("/api/auth/register", json=_new_user_payload())
    assert resp.status_code == 400
    assert outbox == []


# ---- verifying an email ----

def test_verification_link_confirms_email_once(client, make_user, outbox, db_session):
    _as(client, make_user(role=UserRole.ADMIN))
    client.post("/api/auth/register", json=_new_user_payload())
    token = _token(outbox[0])
    client.post("/api/auth/logout")

    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    from app.db_models import UserDB
    user = db_session.query(UserDB).filter(UserDB.username == "newstaff").one()
    assert user.email_verified_at is not None

    again = client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["detail"] == account_email.INVALID_LINK_DETAIL


def test_verification_link_dies_when_email_changes(client, make_user, outbox):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user(email_verified_at=None)
    _as(client, admin)
    client.patch(f"/api/auth/users/{staff.id}/email", json={"email": "first@example.org"})
    first_token = _token(outbox[-1])
    client.patch(f"/api/auth/users/{staff.id}/email", json={"email": "second@example.org"})
    second_token = _token(outbox[-1])

    assert client.post("/api/auth/verify-email", json={"token": first_token}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": second_token}).status_code == 200
    assert staff.email == "second@example.org"
    assert staff.email_verified_at is not None


def test_tokens_are_stored_hashed(client, make_user, outbox, db_session):
    _as(client, make_user(role=UserRole.ADMIN))
    client.post("/api/auth/register", json=_new_user_payload())
    token = _token(outbox[0])
    rows = db_session.query(EmailTokenDB).all()
    assert rows and all(token not in (r.token_hash, r.email) for r in rows)


# ---- admin email management ----

def test_admin_changing_email_unverifies_it(client, make_user, outbox, audit):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user()
    assert staff.email_verified_at is not None
    _as(client, admin)
    resp = client.patch(f"/api/auth/users/{staff.id}/email", json={"email": "Changed@Example.org"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "changed@example.org"
    assert staff.email_verified_at is None
    assert outbox[-1]["to"] == "changed@example.org"
    events = [e for e in audit() if e["event"] == "auth.email_changed"]
    assert events[-1]["actor"] == admin.username and events[-1]["target"] == staff.username


def test_setting_the_same_email_sends_nothing(client, make_user, outbox):
    admin = make_user(role=UserRole.ADMIN)
    staff = make_user()
    _as(client, admin)
    resp = client.patch(f"/api/auth/users/{staff.id}/email", json={"email": staff.email})
    assert resp.status_code == 200
    assert staff.email_verified_at is not None
    assert outbox == []


@pytest.mark.parametrize("role", [UserRole.REGISTRAR, UserRole.STAFF])
def test_only_admin_manages_emails(client, make_user, outbox, role):
    staff = make_user(email_verified_at=None)
    _as(client, make_user(role=role))
    assert client.patch(f"/api/auth/users/{staff.id}/email", json={"email": "x@example.org"}).status_code == 403
    assert client.post(f"/api/auth/users/{staff.id}/resend-verification").status_code == 403
    assert outbox == []


def test_admin_resend_verification(client, make_user, outbox):
    admin = make_user(role=UserRole.ADMIN)
    unverified = make_user(email_verified_at=None)
    verified = make_user()
    _as(client, admin)
    assert client.post(f"/api/auth/users/{unverified.id}/resend-verification").status_code == 200
    assert outbox[-1]["to"] == unverified.email
    assert client.post(f"/api/auth/users/{verified.id}/resend-verification").status_code == 400
    assert client.post("/api/auth/users/999999/resend-verification").status_code == 404


# ---- accounts from before emails ----

def test_account_without_email_must_add_one(client, make_user, outbox):
    legacy = make_user(email=None, email_verified_at=None)
    login = _login(client, legacy)
    assert login.status_code == 200
    assert login.json()["email"] is None

    assert client.get("/api/auth/me").status_code == 200
    blocked = client.get("/api/queues")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == EMAIL_REQUIRED_DETAIL

    resp = client.put("/api/auth/me/email", json={"email": "legacy@example.org"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "legacy@example.org"
    # Adding it is enough to work; confirming it only unlocks email resets.
    assert client.get("/api/queues").status_code == 200
    assert outbox[-1]["to"] == "legacy@example.org"


def test_user_can_fix_unconfirmed_email_but_not_confirmed_one(client, make_user, outbox):
    unverified = make_user(email_verified_at=None)
    _as(client, unverified)
    assert client.put("/api/auth/me/email", json={"email": "fixed@example.org"}).status_code == 200
    assert client.post("/api/auth/me/email/resend-verification").status_code == 200

    verified = make_user()
    _as(client, verified)
    resp = client.put("/api/auth/me/email", json={"email": "elsewhere@example.org"})
    assert resp.status_code == 400
    assert verified.email != "elsewhere@example.org"


def test_set_my_email_requires_login(client, outbox):
    assert client.put("/api/auth/me/email", json={"email": "x@example.org"}).status_code == 401


# ---- forgot password ----

def _forgot(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


def test_forgot_password_reply_never_reveals_the_account(client, make_user, outbox):
    verified = make_user()
    unverified = make_user(email_verified_at=None)
    inactive = make_user(is_active=False)

    replies = [_forgot(client, e) for e in
               ("nobody@example.org", unverified.email, inactive.email, verified.email)]
    assert {r.status_code for r in replies} == {202}
    assert len({r.text for r in replies}) == 1
    # Only the active, confirmed account actually gets mail.
    assert [m["to"] for m in outbox] == [verified.email]


def test_forgot_password_matches_case_insensitively(client, make_user, outbox):
    staff = make_user()
    _forgot(client, staff.email.upper())
    assert [m["to"] for m in outbox] == [staff.email]


def test_forgot_password_rejects_malformed_email(client, outbox):
    assert _forgot(client, "not-an-email").status_code == 422
    resp = client.post("/api/auth/forgot-password", json={"email": "a@example.org", "username": "x"})
    assert resp.status_code == 422


def test_per_account_reset_email_cap(client, make_user, outbox, audit):
    staff = make_user()
    for _ in range(settings.MAX_PASSWORD_RESET_EMAILS + 2):
        assert _forgot(client, staff.email).status_code == 202
    assert len(outbox) == settings.MAX_PASSWORD_RESET_EMAILS
    assert any(e["event"] == "auth.password_reset_requested" and e["outcome"] == "blocked" for e in audit())


# ---- resetting with the link ----

def _reset(client, token, password="fresh-pass-456"):
    return client.post("/api/auth/reset-password", json={"token": token, "new_password": password})


def test_reset_link_sets_password_unlocks_and_works_once(client, make_user, outbox, db_session):
    staff = make_user()
    staff.failed_login_attempts = 4
    staff.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    staff.must_change_password = True
    db_session.commit()

    _forgot(client, staff.email)
    token = _token(outbox[-1])
    assert "/reset-password#token=" in outbox[-1]["text"]

    assert _reset(client, token).status_code == 200
    assert verify_password("fresh-pass-456", staff.hashed_password)
    assert staff.locked_until is None and staff.failed_login_attempts == 0
    assert staff.must_change_password is False
    assert _login(client, staff, "fresh-pass-456").status_code == 200

    again = _reset(client, token, "another-pass-789")
    assert again.status_code == 400
    assert again.json()["detail"] == account_email.INVALID_LINK_DETAIL


def test_newer_reset_link_retires_older_one(client, make_user, outbox):
    staff = make_user()
    _forgot(client, staff.email)
    first = _token(outbox[-1])
    _forgot(client, staff.email)
    second = _token(outbox[-1])
    assert _reset(client, first).status_code == 400
    assert _reset(client, second).status_code == 200


def test_expired_reset_link_is_refused(client, make_user, outbox, db_session):
    staff = make_user()
    _forgot(client, staff.email)
    token = _token(outbox[-1])
    row = db_session.query(EmailTokenDB).filter(EmailTokenDB.user_id == staff.id).one()
    assert row.expires_at - datetime.now(timezone.utc) <= timedelta(minutes=15)
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert _reset(client, token).status_code == 400
    assert verify_password(staff._plain_password, staff.hashed_password)


def test_verification_token_cannot_reset_password(client, make_user, outbox):
    _as(client, make_user(role=UserRole.ADMIN))
    client.post("/api/auth/register", json=_new_user_payload())
    assert _reset(client, _token(outbox[0])).status_code == 400


def test_reset_link_refused_after_deactivation_or_email_change(client, make_user, outbox, db_session):
    staff = make_user()
    _forgot(client, staff.email)
    token = _token(outbox[-1])
    staff.is_active = False
    db_session.commit()
    assert _reset(client, token).status_code == 400

    other = make_user()
    _forgot(client, other.email)
    token = _token(outbox[-1])
    other.email = "moved@example.org"
    db_session.commit()
    assert _reset(client, token).status_code == 400


@pytest.mark.parametrize("body", [
    {"token": "x" * 43, "new_password": "short"},
    {"token": "short", "new_password": "long-enough-pass"},
    {"token": "x" * 43, "new_password": "y" * 73},
    {"token": "x" * 43},
])
def test_reset_input_validation(client, body):
    assert client.post("/api/auth/reset-password", json=body).status_code == 422


def test_audit_never_contains_tokens_or_passwords(client, make_user, outbox, audit):
    staff = make_user()
    _forgot(client, staff.email)
    token = _token(outbox[-1])
    _reset(client, token)
    events = audit()
    assert {"auth.password_reset_requested", "auth.password_reset_completed"} <= {e["event"] for e in events}
    dumped = json.dumps(events)
    assert token not in dumped and "fresh-pass-456" not in dumped


# ---- email sender ----

def test_console_backend_logs_link_only_in_debug(monkeypatch, caplog):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "console")
    caplog.set_level(logging.INFO, logger="bsu.email")

    monkeypatch.setattr(settings, "DEBUG", True)
    assert email_sender.send_email("a@example.org", "Subj", "link #token=SECRET") is False
    assert "SECRET" in caplog.text

    caplog.clear()
    monkeypatch.setattr(settings, "DEBUG", False)
    assert email_sender.send_email("a@example.org", "Subj", "link #token=SECRET") is False
    assert "SECRET" not in caplog.text and "NOT sent" in caplog.text


def _gmail_settings(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "gmail")
    monkeypatch.setattr(settings, "EMAIL_FROM", "Registrar <registrar@example.org>")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(settings, "GMAIL_REFRESH_TOKEN", "rtoken")


def _mock_httpx(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(
        email_sender.httpx, "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )


def test_gmail_backend_refreshes_token_and_sends(monkeypatch):
    _gmail_settings(monkeypatch)
    calls = []

    def handler(request):
        calls.append(request)
        if request.url == email_sender.GOOGLE_TOKEN_URL:
            assert b"refresh_token=rtoken" in request.content
            return httpx.Response(200, json={"access_token": "atoken"})
        assert request.headers["authorization"] == "Bearer atoken"
        raw = json.loads(request.content)["raw"]
        import base64
        mime = base64.urlsafe_b64decode(raw).decode()
        assert "To: staff@example.org" in mime and "Subject: Hello" in mime
        return httpx.Response(200, json={"id": "m1"})

    _mock_httpx(monkeypatch, handler)
    assert email_sender.send_email("staff@example.org", "Hello", "body", "<p>body</p>") is True
    assert [str(c.url) for c in calls] == [email_sender.GOOGLE_TOKEN_URL, email_sender.GMAIL_SEND_URL]


def test_gmail_failure_is_logged_not_raised(monkeypatch, caplog):
    _gmail_settings(monkeypatch)
    _mock_httpx(monkeypatch, lambda request: httpx.Response(400, json={"error": "invalid_grant"}))
    caplog.set_level(logging.ERROR, logger="bsu.email")
    assert email_sender.send_email("staff@example.org", "Hello", "body") is False
    assert "invalid_grant" in caplog.text


def test_gmail_without_credentials_is_not_sent(monkeypatch):
    _gmail_settings(monkeypatch)
    monkeypatch.setattr(settings, "GMAIL_REFRESH_TOKEN", "")
    assert email_sender.send_email("staff@example.org", "Hello", "body") is False


def test_gmail_auth_url_requests_send_only_with_pkce():
    url = gmail_auth.build_auth_url("cid", "http://127.0.0.1:5555", "st", "verifier" * 8)
    assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.send" in url
    assert "code_challenge_method=S256" in url and "access_type=offline" in url
    assert "verifier" not in url


def test_gmail_auth_reads_downloaded_client_file(tmp_path):
    path = tmp_path / "client_secret_x.json"
    path.write_text(json.dumps({"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "GOCSPX-abc"}}))
    assert gmail_auth.read_client_file(str(path)) == ("cid.apps.googleusercontent.com", "GOCSPX-abc")


def test_gmail_auth_reports_unreadable_client_file(tmp_path, capsys):
    assert gmail_auth.run(["--client-file", str(tmp_path / "missing.json")]) == 1
    assert "Could not read" in capsys.readouterr().err
