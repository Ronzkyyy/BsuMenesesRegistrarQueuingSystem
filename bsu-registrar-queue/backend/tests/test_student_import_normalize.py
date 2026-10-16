import pytest

from app.models.student import Course, Major, StudentType, YearLevel
from app.services.student_import import columns, normalize


@pytest.mark.parametrize("raw, expected", [
    ("BSIT", Course.BSIT), ("bsit", Course.BSIT), ("B.S.I.T.", Course.BSIT),
    ("Bachelor of Science in Information Technology", Course.BSIT),
    ("BSCpE", Course.BSCPE), ("BSCPE", Course.BSCPE), ("BSEd", Course.BSED),
    ("BSHM", Course.BSHM), ("BSBA", Course.BSBA), ("BIT", Course.BIT),
])
def test_course(raw, expected):
    assert normalize.course(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("1", YearLevel.FIRST), ("1st", YearLevel.FIRST), ("1st Year", YearLevel.FIRST),
    ("First Year", YearLevel.FIRST), ("1st_year", YearLevel.FIRST),
    ("3rd year", YearLevel.THIRD), ("5", YearLevel.FIFTH), ("Graduate", YearLevel.GRADUATE),
])
def test_year_level(raw, expected):
    assert normalize.year_level(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Undergraduate", StudentType.UNDERGRADUATE), ("undergrad", StudentType.UNDERGRADUATE),
    ("Graduate", StudentType.GRADUATE), ("grad", StudentType.GRADUATE),
    ("Alumni", StudentType.ALUMNI), ("alumnus", StudentType.ALUMNI),
])
def test_student_type(raw, expected):
    assert normalize.student_type(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("", None), ("  ", None), ("CT", Major.COMPUTER_TECHNOLOGY),
    ("Computer Technology", Major.COMPUTER_TECHNOLOGY),
    ("BIT Computer Technology", Major.COMPUTER_TECHNOLOGY),
    ("FPT", Major.FOOD_PROCESSING_TECHNOLOGY), ("food processing technology", Major.FOOD_PROCESSING_TECHNOLOGY),
])
def test_major(raw, expected):
    assert normalize.major(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Yes", True), ("y", True), ("TRUE", True), ("1", True), ("✓", True),
    ("No", False), ("n", False), ("false", False), ("0", False),
    ("", None), ("   ", None),
])
def test_flag(raw, expected):
    assert normalize.flag(raw) is expected


@pytest.mark.parametrize("fn, raw", [
    (normalize.course, "BS Nursing"), (normalize.course, ""),
    (normalize.year_level, "6th year"), (normalize.student_type, "freshman"),
    (normalize.major, "Welding"), (normalize.flag, "maybe"),
])
def test_rejects_unknown_values(fn, raw):
    with pytest.raises(normalize.NormalizeError):
        fn(raw)


def test_header_aliases_resolve_to_canonical_columns():
    assert columns.ALIASES[columns.key("Student No.")] == "student_number"
    assert columns.ALIASES[columns.key("Email Address")] == "email"
    assert columns.ALIASES[columns.key("Year Level*")] == "year_level"
    assert columns.ALIASES[columns.key("Surname")] == "last_name"
    assert set(columns.REQUIRED) <= set(columns.COLUMNS)
