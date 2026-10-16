"""Friendly spreadsheet values -> the system's enum values. Pure functions."""
from typing import Optional

from ...models.student import Course, Major, StudentType, YearLevel
from .columns import key


class NormalizeError(ValueError):
    pass


_COURSES = {key(c.value): c for c in Course}
_COURSES.update({key(code): course for code, course in {
    "BSIT": Course.BSIT, "BSHM": Course.BSHM, "BSBA": Course.BSBA,
    "BSCpE": Course.BSCPE, "BSEd": Course.BSED, "BIT": Course.BIT,
}.items()})

_MAJORS = {key(m.value): m for m in Major}
_MAJORS.update({
    key("CT"): Major.COMPUTER_TECHNOLOGY, key("Computer Technology"): Major.COMPUTER_TECHNOLOGY,
    key("FPT"): Major.FOOD_PROCESSING_TECHNOLOGY,
})

_TYPES = {
    "undergraduate": StudentType.UNDERGRADUATE, "undergrad": StudentType.UNDERGRADUATE,
    "graduate": StudentType.GRADUATE, "grad": StudentType.GRADUATE,
    "alumni": StudentType.ALUMNI, "alumnus": StudentType.ALUMNI, "alumna": StudentType.ALUMNI,
}

_YEARS = {"graduate": YearLevel.GRADUATE}
for _n, (_ord, _word, _level) in enumerate([
    ("1st", "first", YearLevel.FIRST), ("2nd", "second", YearLevel.SECOND),
    ("3rd", "third", YearLevel.THIRD), ("4th", "fourth", YearLevel.FOURTH),
    ("5th", "fifth", YearLevel.FIFTH),
], start=1):
    for _alias in (str(_n), _ord, f"{_ord}year", _word, f"{_word}year", f"year{_n}"):
        _YEARS[_alias] = _level

_YES = {"yes", "y", "true", "1"}
_NO = {"no", "n", "false", "0"}
_CHECKMARKS = {"✓", "✔"}


def _lookup(table, raw, message):
    found = table.get(key(raw))
    if found is None:
        raise NormalizeError(message.format(raw=str(raw).strip()))
    return found


def course(raw) -> Course:
    return _lookup(_COURSES, raw, "'{raw}' is not a course offered here.")


def major(raw) -> Optional[Major]:
    if not str(raw or "").strip():
        return None
    return _lookup(_MAJORS, raw, "'{raw}' is not a BIT major.")


def student_type(raw) -> StudentType:
    return _lookup(_TYPES, raw, "'{raw}' is not a student type (Undergraduate, Graduate or Alumni).")


def year_level(raw) -> YearLevel:
    return _lookup(_YEARS, raw, "'{raw}' is not a year level (1st–5th Year or Graduate).")


def flag(raw) -> Optional[bool]:
    """True / False, or None for a blank cell (meaning: keep the current value)."""
    text = str(raw or "").strip()
    if not text:
        return None
    if text in _CHECKMARKS or key(text) in _YES:
        return True
    if key(text) in _NO:
        return False
    raise NormalizeError(f"'{text}' should be Yes or No.")
