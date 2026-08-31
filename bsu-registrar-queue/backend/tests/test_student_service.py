import pytest

from app.services.student_service import StudentService
from app.services.ticket_service import TicketService
from app.models.student import StudentCreate, StudentType, Course, Major, YearLevel
from app.models.ticket import TicketCreate


def test_create_and_fetch_student(db_session, make_student):
    student = make_student(first_name="Ana", last_name="Reyes")

    service = StudentService(db_session)
    fetched = service.get_student_by_student_id(student.student_id)

    assert fetched is not None
    assert fetched.first_name == "Ana"
    assert fetched.last_name == "Reyes"


def test_create_student_rejects_duplicate_student_id(db_session, make_student):
    student = make_student()

    service = StudentService(db_session)
    with pytest.raises(ValueError, match="already exists"):
        service.create_student(StudentCreate(
            student_id=student.student_id,
            first_name="Someone",
            last_name="Else",
            email="someone@example.com",
            student_type=StudentType.UNDERGRADUATE,
            course=Course.BSIT,
            year_level=YearLevel.FIRST,
        ))


def test_bit_course_requires_major(db_session):
    with pytest.raises(ValueError, match="major is required"):
        StudentCreate(
            student_id="3010000001",
            first_name="Test",
            last_name="Student",
            email="t@example.com",
            student_type=StudentType.UNDERGRADUATE,
            course=Course.BIT,
            year_level=YearLevel.FIRST,
        )


def test_non_bit_course_rejects_major(db_session):
    with pytest.raises(ValueError, match="only applicable"):
        StudentCreate(
            student_id="3010000002",
            first_name="Test",
            last_name="Student",
            email="t2@example.com",
            student_type=StudentType.UNDERGRADUATE,
            course=Course.BSIT,
            major=Major.COMPUTER_TECHNOLOGY,
            year_level=YearLevel.FIRST,
        )


def test_computer_engineering_course_is_accepted(db_session, make_student):
    student = make_student(student_id="3010000010", course=Course.BSCPE)

    assert student.course == Course.BSCPE

    service = StudentService(db_session)
    fetched = service.get_student_by_student_id("3010000010")
    assert fetched.course == Course.BSCPE


def test_computer_engineering_course_rejects_major(db_session):
    with pytest.raises(ValueError, match="only applicable"):
        StudentCreate(
            student_id="3010000011",
            first_name="Test",
            last_name="Student",
            email="cpe@example.com",
            student_type=StudentType.UNDERGRADUATE,
            course=Course.BSCPE,
            major=Major.COMPUTER_TECHNOLOGY,
            year_level=YearLevel.FIRST,
        )


def test_search_students_by_query(db_session, make_student):
    make_student(first_name="Bea", last_name="Santos")
    make_student(first_name="Carlo", last_name="Cruz")

    service = StudentService(db_session)
    results, total = service.search_students(query="Santos")

    assert total == 1
    assert results[0].first_name == "Bea"


def test_delete_student_without_tickets_succeeds(db_session, make_student):
    student = make_student()

    service = StudentService(db_session)
    deleted = service.delete_student(student.id)

    assert deleted is True
    assert service.get_student_by_id(student.id) is None


def test_delete_student_with_tickets_is_blocked(db_session, make_student, make_queue):
    student = make_student()
    queue = make_queue()
    TicketService(db_session).create_ticket(TicketCreate(student_id=student.id, queue_id=queue.id))

    service = StudentService(db_session)
    with pytest.raises(ValueError, match="Cannot delete student"):
        service.delete_student(student.id)
