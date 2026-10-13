"""The b9c0d1e2f3a4 backfill: legacy single `document_type` values become
association rows. Runs the migration's own SQL against legacy-shaped rows
(the suite's schema is already at head, and its seed rows are truncated)."""
import importlib.util
from datetime import datetime, time, timezone
from pathlib import Path

from app.db_models import AppointmentDB, AppointmentDBStatus, TicketDB, TicketDBStatus

_MIGRATION = (Path(__file__).resolve().parent.parent
              / "migrations" / "versions" / "b9c0d1e2f3a4_add_document_catalog.py")


def _migration():
    spec = importlib.util.spec_from_file_location("doc_catalog_migration", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_maps_legacy_document_type_to_snapshot_rows(
        db_session, make_queue, make_student, make_document):
    migration = _migration()
    doc = make_document(short_name="LEGACY-TOR", name="Legacy Transcript", display_order=3)
    queue = make_queue()
    when = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)
    ticket = TicketDB(ticket_number=1, student_id=make_student().id, queue_id=queue.id,
                      status=TicketDBStatus.COMPLETED, position=0, created_at=when,
                      document_type="LEGACY-TOR")
    untouched = TicketDB(ticket_number=2, student_id=make_student().id, queue_id=queue.id,
                         status=TicketDBStatus.COMPLETED, position=0, created_at=when)
    appointment = AppointmentDB(
        reference_code="APT-LEGACY", student_id=make_student().id, queue_id=queue.id,
        appointment_date=when.date(), slot_start_time=time(9, 0), slot_end_time=time(9, 30),
        qr_token="tok-legacy", status=AppointmentDBStatus.BOOKED, document_type="LEGACY-TOR",
    )
    db_session.add_all([ticket, untouched, appointment])
    db_session.commit()

    db_session.execute(migration.BACKFILL_TICKETS)
    db_session.execute(migration.BACKFILL_TICKETS)  # idempotent: no duplicate rows
    db_session.execute(migration.BACKFILL_APPOINTMENTS)
    db_session.commit()
    db_session.expire_all()

    assert [(d.document_id, d.name, d.short_name, d.fee, d.position) for d in ticket.documents] == [
        (doc.id, "Legacy Transcript", "LEGACY-TOR", None, 3)
    ]
    assert untouched.documents == []
    assert [d.short_name for d in appointment.documents] == ["LEGACY-TOR"]


def test_migration_seeds_the_seven_legacy_documents_in_order():
    seeded = _migration().SEED_DOCUMENTS
    assert [short for short, _ in seeded] == [
        "TOR", "COR", "COG", "Diploma", "Good Moral", "Graduation Form", "Form 137",
    ]
