"""Column definitions shared by the reader, importer and template."""
import re

# Canonical column keys, in template order.
COLUMNS = [
    "student_number", "first_name", "last_name", "email", "student_type",
    "course", "major", "year_level", "is_scholar", "is_varsity", "is_graduating",
]
REQUIRED = ["student_number", "first_name", "last_name", "email", "student_type", "course", "year_level"]
FLAG_COLUMNS = ["is_scholar", "is_varsity", "is_graduating"]

LABELS = {
    "student_number": "Student Number", "first_name": "First Name", "last_name": "Last Name",
    "email": "Email", "student_type": "Student Type", "course": "Course", "major": "Major",
    "year_level": "Year Level", "is_scholar": "Scholar", "is_varsity": "Varsity",
    "is_graduating": "Graduating",
}


def key(value) -> str:
    """Comparison key: lowercase letters and digits only ("Student No.*" -> "studentno")."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


ALIASES = {key(label): column for column, label in LABELS.items()}
ALIASES.update({
    key("Student No"): "student_number", key("Student ID"): "student_number",
    key("ID Number"): "student_number", key("Given Name"): "first_name",
    key("Surname"): "last_name", key("Family Name"): "last_name",
    key("Email Address"): "email", key("Type"): "student_type",
    key("Program"): "course", key("Year"): "year_level",
})

# The template's example row. The reader skips a data row equal to this.
EXAMPLE_ROW = {
    "student_number": "2026000001", "first_name": "Juan", "last_name": "Dela Cruz",
    "email": "juan.delacruz@example.com", "student_type": "Undergraduate", "course": "BSIT",
    "major": "", "year_level": "1st Year", "is_scholar": "No", "is_varsity": "No",
    "is_graduating": "No",
}
