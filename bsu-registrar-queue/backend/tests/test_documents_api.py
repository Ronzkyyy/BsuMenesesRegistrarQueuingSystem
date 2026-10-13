"""Document catalog: Admin-only management, public active list, and the
documents a ticket request may carry."""
import json
import logging
from decimal import Decimal

import pytest

from app.db_models import DocumentDB, UserRole


def _login(client, user):
    return client.post("/api/auth/login",
                       data={"username": user.username,
                             "password": user._plain_password})


def _audit_capture():
    logger = logging.getLogger("bsu.security")
    messages: list[str] = []

    class _Cap(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    handler = _Cap()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler, lambda: [json.loads(m) for m in messages]


# ---- public list -----------------------------------------------------------

def test_public_active_list_hides_inactive_and_admin_fields(client, make_document):
    shown = make_document(short_name="SHOWN", fee=Decimal("25.50"), requirements="Bring ID",
                          processing_time="3 days", display_order=2)
    first = make_document(short_name="FIRST", display_order=1)
    make_document(short_name="HIDDEN", is_active=False, display_order=0)

    r = client.get("/api/documents/active")

    assert r.status_code == 200
    body = r.json()
    assert [d["short_name"] for d in body] == ["FIRST", "SHOWN"]
    assert body[1] == {
        "id": shown.id, "name": shown.name, "short_name": "SHOWN",
        "requirements": "Bring ID", "processing_time": "3 days", "fee": "25.50",
    }
    assert first.id == body[0]["id"]


# ---- authorization ---------------------------------------------------------

@pytest.mark.parametrize("role", [UserRole.REGISTRAR, UserRole.STAFF])
def test_catalog_management_is_admin_only(client, make_user, make_document, role):
    doc = make_document()
    _login(client, make_user(role=role))

    assert client.get("/api/documents").status_code == 403
    assert client.post("/api/documents", json={"name": "X", "short_name": "X"}).status_code == 403
    assert client.patch(f"/api/documents/{doc.id}", json={"fee": "10"}).status_code == 403
    assert client.put("/api/documents/order", json={"document_ids": [doc.id]}).status_code == 403


def test_catalog_management_requires_login(client):
    assert client.get("/api/documents").status_code == 401


# ---- create / update / validation -----------------------------------------

def test_admin_creates_document_at_the_end_and_it_is_audited(client, db_session, make_user, make_document):
    make_document(display_order=40)
    admin = make_user(role=UserRole.ADMIN)
    _login(client, admin)

    handler, events = _audit_capture()
    try:
        r = client.post("/api/documents", json={
            "name": "  Certificate of Enrollment ", "short_name": "COE",
            "fee": "75.00", "processing_time": "", "requirements": "Valid ID",
        })
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Certificate of Enrollment"
    assert body["processing_time"] is None
    assert body["fee"] == "75.00"
    assert body["is_active"] is True
    assert body["display_order"] == 41
    created = [e for e in events() if e["event"] == "document.created"]
    assert created and created[0]["actor"] == admin.username


def test_duplicate_names_rejected_case_insensitively(client, make_user, make_document):
    make_document(name="Diploma Copy", short_name="DIP")
    _login(client, make_user(role=UserRole.ADMIN))

    r = client.post("/api/documents", json={"name": "diploma copy", "short_name": "NEW"})
    assert r.status_code == 400
    assert "name" in r.json()["detail"]

    r = client.post("/api/documents", json={"name": "Something", "short_name": "dip"})
    assert r.status_code == 400
    assert "short name" in r.json()["detail"]


@pytest.mark.parametrize("payload", [
    {"name": "X", "short_name": "X", "fee": "-1"},
    {"name": "X", "short_name": "X", "fee": "100000.01"},
    {"name": "X", "short_name": "X", "fee": "1.234"},
    {"name": "", "short_name": "X"},
    {"name": "X", "short_name": "X" * 31},
    {"name": "X", "short_name": "X", "requirements": "r" * 501},
    {"name": "X", "short_name": "X", "is_active": False},  # extra="forbid" on create
])
def test_create_rejects_invalid_input(client, make_user, payload):
    _login(client, make_user(role=UserRole.ADMIN))
    assert client.post("/api/documents", json=payload).status_code == 422


def test_update_logs_changed_fields_and_deactivation(client, make_user, make_document):
    keep = make_document()
    doc = make_document(fee=Decimal("10.00"))
    _login(client, make_user(role=UserRole.ADMIN))

    handler, events = _audit_capture()
    try:
        r = client.patch(f"/api/documents/{doc.id}", json={"fee": "20", "is_active": False})
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 200
    assert r.json()["fee"] == "20.00"
    assert r.json()["is_active"] is False
    by_event = {e["event"]: e for e in events()}
    assert by_event["document.updated"]["detail"] == "fee"
    assert by_event["document.deactivated"]["target"] == f"document#{doc.id}"
    assert keep.is_active


def test_last_active_document_cannot_be_deactivated(client, db_session, make_user, make_document):
    # Only the documents this test made exist (the suite truncates the seed).
    for other in db_session.query(DocumentDB).all():
        other.is_active = False
    only = make_document()
    db_session.commit()
    _login(client, make_user(role=UserRole.ADMIN))

    r = client.patch(f"/api/documents/{only.id}", json={"is_active": False})

    assert r.status_code == 400
    assert "At least one document must stay active" in r.json()["detail"]


def test_update_missing_document_is_404(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    assert client.patch("/api/documents/999999", json={"fee": "1"}).status_code == 404
    assert client.patch("/api/documents/0", json={"fee": "1"}).status_code == 422


# ---- reorder ---------------------------------------------------------------

def test_reorder_sets_display_order_and_requires_every_id(client, db_session, make_user, make_document):
    a, b, c = make_document(), make_document(), make_document()
    all_ids = [d.id for d in db_session.query(DocumentDB).all()]
    _login(client, make_user(role=UserRole.ADMIN))

    new_order = [c.id] + [i for i in all_ids if i not in (c.id, a.id)] + [a.id]
    r = client.put("/api/documents/order", json={"document_ids": new_order})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(DocumentDB, c.id).display_order == 1
    assert db_session.get(DocumentDB, a.id).display_order == len(all_ids)

    partial = client.put("/api/documents/order", json={"document_ids": [a.id, b.id]})
    assert partial.status_code == 400
    dupes = client.put("/api/documents/order", json={"document_ids": new_order + [a.id]})
    assert dupes.status_code == 400


# ---- the public ticket endpoint -------------------------------------------

def test_public_ticket_request_carries_documents(client, make_queue, make_student, make_document):
    from app.models.queue import QueueType

    queue = make_queue(queue_type=QueueType.DOCUMENT_REQUEST)
    doc = make_document(fee=Decimal("40.00"))

    r = client.post("/api/tickets", json={
        "student_id": make_student().id, "queue_id": queue.id, "document_ids": [doc.id],
    })

    assert r.status_code == 200
    body = r.json()
    assert body["documents"] == [{
        "document_id": doc.id, "name": doc.name, "short_name": doc.short_name, "fee": "40.00",
    }]
    assert body["documents_fee_total"] == "40.00"


def test_public_ticket_request_rejects_the_old_single_document_field(client, make_queue, make_student):
    from app.models.queue import QueueType

    queue = make_queue(queue_type=QueueType.DOCUMENT_REQUEST)
    r = client.post("/api/tickets", json={
        "student_id": make_student().id, "queue_id": queue.id, "document_type": "TOR",
    })
    assert r.status_code == 422


@pytest.mark.parametrize("ids", [[0], [-3], list(range(1, 52))])
def test_public_ticket_request_bounds_document_ids(client, make_queue, make_student, ids):
    r = client.post("/api/tickets", json={
        "student_id": make_student().id, "queue_id": make_queue().id, "document_ids": ids,
    })
    assert r.status_code == 422
