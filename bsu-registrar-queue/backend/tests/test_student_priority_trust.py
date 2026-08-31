"""Priority flags (is_scholar/is_varsity/is_graduating) drive queue priority
(see TicketService.calculate_priority) and must never be settable by the
public, unauthenticated kiosk self-registration endpoint - only by
staff (PATCH, registrar-gated) or an admin bulk-import.
"""
from app.db_models import UserRole


def _login(client, user):
    return client.post("/api/auth/login", data={"username": user.username, "password": user._plain_password})


_BASE_PAYLOAD = {
    "first_name": "Test",
    "last_name": "Student",
    "student_type": "undergraduate",
    "course": "Bachelor of Science in Information Technology",
    "year_level": "1st_year",
}


def test_public_register_rejects_priority_flags(client):
    payload = {
        **_BASE_PAYLOAD,
        "student_id": "3020000001",
        "email": "flag.attempt@example.com",
        "is_graduating": True,
    }
    resp = client.post("/api/students", json=payload)
    assert resp.status_code == 422, resp.text
    assert any(e.get("loc", [None, None])[-1] == "is_graduating" for e in resp.json()["detail"])


def test_public_register_without_flags_defaults_to_false(client):
    payload = {
        **_BASE_PAYLOAD,
        "student_id": "3020000002",
        "email": "no.flags@example.com",
    }
    resp = client.post("/api/students", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_scholar"] is False
    assert body["is_varsity"] is False
    assert body["is_graduating"] is False


def test_registrar_can_set_priority_flags_via_patch(client, make_user, make_student):
    student = make_student(student_id="3020000003")
    registrar = make_user(role=UserRole.REGISTRAR)
    _login(client, registrar)

    payload = {
        **_BASE_PAYLOAD,
        "student_id": student.student_id,
        "email": student.email,
        "is_graduating": True,
    }
    resp = client.patch(f"/api/students/{student.id}", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_graduating"] is True


def test_staff_role_cannot_set_priority_flags_endpoint(client, make_user):
    """PATCH /students is registrar+, not staff - staff shouldn't reach it at all."""
    staff = make_user(role=UserRole.STAFF)
    _login(client, staff)
    resp = client.patch("/api/students/1", json={**_BASE_PAYLOAD, "student_id": "3020000004", "email": "x@example.com"})
    assert resp.status_code == 403
