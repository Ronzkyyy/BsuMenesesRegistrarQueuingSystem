import pytest

from app.db_models import Course, StudentDB, StudentDBType, YearLevel
from app.services import student_service
from app.services.student_import.importer import StudentImporter
from app.services.student_import.reader import RawRow, ReadResult

BASE = {
    "student_number": "2031000001", "first_name": "Ana", "last_name": "Reyes",
    "email": "ana.reyes@example.com", "student_type": "Undergraduate", "course": "BSIT",
    "year_level": "1st Year",
}


def read(*rows) -> ReadResult:
    raw = [RawRow(row=i + 2, values=dict(r), original={k: v for k, v in r.items()})
           for i, r in enumerate(rows)]
    return ReadResult(file_type="csv", headers=list(BASE), ignored_columns=[], rows=raw)


@pytest.fixture(autouse=True)
def no_mx_check(monkeypatch):
    def fail(email):
        raise AssertionError("imports must not run the live MX check")
    monkeypatch.setattr(student_service, "validate_email_deliverable", fail)


def count(db):
    return db.query(StudentDB).filter(StudentDB.student_id.like("2031%")).count()


def existing(db, number, first="Ana", last="Reyes", email="ana.reyes@example.com", **extra):
    """An existing student, inserted directly - make_student would run the
    live MX check, which the no_mx_check fixture deliberately breaks."""
    row = StudentDB(student_id=number, first_name=first, last_name=last, email=email,
                    student_type=StudentDBType.UNDERGRADUATE, course=Course.BSIT,
                    year_level=YearLevel.FIRST, **extra)
    db.add(row)
    db.commit()
    return row


def test_preview_classifies_and_writes_nothing(db_session):
    existing(db_session, "2031000002", first="Ben", last="Cruz", email="ben@gmail.com")
    existing(db_session, "2031000003", first="Cy", last="Lim", email="cy@gmail.com")
    report = StudentImporter(db_session).run(read(
        BASE,                                                         # new
        {**BASE, "student_number": "2031000002", "first_name": "Ben", "last_name": "Cruz",
         "email": "ben@gmail.com", "year_level": "2nd Year"},          # update
        {**BASE, "student_number": "2031000003", "first_name": "Cy", "last_name": "Lim",
         "email": "cy@gmail.com"},                                     # unchanged
        {**BASE, "student_number": "123"},                             # invalid
    ), commit=False)

    assert (report.new, report.updated, report.unchanged, report.invalid) == (1, 1, 1, 1)
    assert report.committed is False
    assert report.total_rows == 4
    update = next(c for c in report.changes if c.action == "update")
    assert update.fields == {"year_level": ["1st Year", "2nd Year"]}
    problem = report.problems[0]
    assert (problem.row, problem.column) == (5, "Student Number")
    assert problem.values["student_number"] == "123"
    assert count(db_session) == 2


def test_commit_saves_new_and_updated_rows(db_session):
    existing(db_session, "2031000002", email="ben@gmail.com")
    report = StudentImporter(db_session).run(read(
        BASE, {**BASE, "student_number": "2031000002", "email": "ben@gmail.com", "course": "BSHM"},
    ), commit=True)

    assert report.committed is True and (report.new, report.updated) == (1, 1)
    db_session.expire_all()
    updated = db_session.query(StudentDB).filter_by(student_id="2031000002").one()
    assert updated.course.value == "Bachelor of Science in Hospitality Management"
    assert db_session.query(StudentDB).filter_by(student_id="2031000001").one().first_name == "Ana"


def test_duplicate_student_number_points_to_first_row(db_session):
    report = StudentImporter(db_session).run(read(BASE, BASE), commit=False)
    assert report.new == 1 and report.invalid == 1
    assert report.problems[0].message == "Student number also appears in row 2."


@pytest.mark.parametrize("row, column, fragment", [
    ({**BASE, "course": "BS Nursing"}, "Course", "not a course"),
    ({**BASE, "email": "not-an-email"}, "Email", "valid email"),
    ({**BASE, "first_name": ""}, "First Name", "Required"),
    ({**BASE, "course": "BIT"}, "Major", "major is required"),
    ({**BASE, "major": "CT"}, "Major", "only applicable"),
    ({**BASE, "student_number": "2.031E+09"}, "Student Number", "changed by Excel"),
    ({**BASE, "is_scholar": "maybe"}, "Scholar", "Yes or No"),
])
def test_row_errors_name_the_column(db_session, row, column, fragment):
    report = StudentImporter(db_session).run(read(row), commit=False)
    assert report.invalid == 1
    assert report.problems[0].column == column
    assert fragment in report.problems[0].message


def test_flag_rules(db_session):
    existing(db_session, "2031000002", email="ben@gmail.com", is_scholar=True)
    base = {**BASE, "student_number": "2031000002", "email": "ben@gmail.com"}

    # Column absent / blank cell: keep the current value -> unchanged.
    assert StudentImporter(db_session).run(read(base), commit=False).unchanged == 1
    assert StudentImporter(db_session).run(read({**base, "is_scholar": ""}), commit=False).unchanged == 1
    # Explicit No clears it.
    report = StudentImporter(db_session).run(read({**base, "is_scholar": "No"}), commit=True)
    assert report.changes[0].fields == {"is_scholar": ["Yes", "No"]}
    # New students default to No; Yes sets it.
    report = StudentImporter(db_session).run(read({**BASE, "is_graduating": "Yes"}), commit=True)
    db_session.expire_all()
    new = db_session.query(StudentDB).filter_by(student_id="2031000001").one()
    assert (new.is_graduating, new.is_scholar) == (True, False)


def test_commit_is_all_or_nothing(db_session, monkeypatch):
    def boom():
        raise RuntimeError("connection lost")
    monkeypatch.setattr(db_session, "commit", boom)
    with pytest.raises(RuntimeError):
        StudentImporter(db_session).run(read(BASE, {**BASE, "student_number": "2031000009"}), commit=True)
    monkeypatch.undo()
    assert count(db_session) == 0
