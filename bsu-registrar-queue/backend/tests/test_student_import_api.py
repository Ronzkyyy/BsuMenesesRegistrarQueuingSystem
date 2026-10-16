import json
import logging

import pytest

from app.db_models import StudentDB, UserRole
from app.services import student_service

CSV = ("Student Number,First Name,Last Name,Email,Student Type,Course,Year Level\r\n"
       "2032000001,Ana,Reyes,ana@example.com,Undergraduate,BSIT,1st Year\r\n"
       "123,Bad,Row,bad@example.com,Undergraduate,BSIT,1st Year\r\n").encode()


def _login(client, user):
    return client.post("/api/auth/login", data={"username": user.username, "password": user._plain_password})


def _upload(client, commit, data=CSV, name="students.csv"):
    return client.post("/api/students/import", params={"commit": str(commit).lower()},
                       files={"file": (name, data, "text/csv")})


@pytest.fixture(autouse=True)
def no_mx(monkeypatch):
    monkeypatch.setattr(student_service, "validate_email_deliverable",
                        lambda e: (_ for _ in ()).throw(AssertionError("no MX on import")))


def test_admin_previews_then_commits(client, db_session, make_user):
    _login(client, make_user(role=UserRole.ADMIN))

    preview = _upload(client, False)
    assert preview.status_code == 200
    assert (preview.json()["new"], preview.json()["invalid"]) == (1, 1)
    assert db_session.query(StudentDB).filter_by(student_id="2032000001").count() == 0

    logger = logging.getLogger("bsu.security")
    messages = []
    handler = logging.Handler()
    handler.emit = lambda record: messages.append(record.getMessage())
    logger.addHandler(handler)
    try:
        committed = _upload(client, True)
    finally:
        logger.removeHandler(handler)
    assert committed.status_code == 200 and committed.json()["committed"] is True
    assert db_session.query(StudentDB).filter_by(student_id="2032000001").count() == 1
    events = [json.loads(m) for m in messages]
    imported = [e for e in events if e["event"] == "student.bulk_imported"]
    assert imported and imported[0]["detail"] == "new=1, updated=0, unchanged=0, invalid=1, file=csv"
    assert "Reyes" not in json.dumps(imported) and "students.csv" not in json.dumps(imported)


@pytest.mark.parametrize("role", [UserRole.REGISTRAR, UserRole.STAFF])
def test_non_admins_are_refused(client, make_user, role):
    _login(client, make_user(role=role))
    assert _upload(client, False).status_code == 403
    assert client.get("/api/students/import-template.xlsx").status_code == 403


def test_anonymous_is_refused(client):
    assert _upload(client, False).status_code == 401


def test_file_errors_use_detail(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    too_big = _upload(client, False, data=b"a" * (2 * 1024 * 1024 + 1))
    assert too_big.status_code == 413 and too_big.json()["detail"] == "The file is larger than 2 MB."
    missing = _upload(client, False, data=b"Name\r\nAna\r\n")
    assert missing.status_code == 400 and "Missing required column" in missing.json()["detail"]


def test_template_download(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    r = client.get("/api/students/import-template.xlsx")
    assert r.status_code == 200
    assert r.content[:4] == b"PK\x03\x04"
    assert 'filename="students_import_template.xlsx"' in r.headers["content-disposition"]


def test_old_json_bulk_import_is_gone(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    assert client.post("/api/students/bulk-import", json=[]).status_code in (404, 405)
