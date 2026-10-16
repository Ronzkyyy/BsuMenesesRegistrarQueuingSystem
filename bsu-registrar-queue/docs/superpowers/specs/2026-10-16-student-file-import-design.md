# Student File Import — Design

**Date:** 2026-10-16
**Status:** Draft — awaiting review
**Path type:** Architectural (new upload + parsing subsystem, replaces an
existing endpoint, new dependencies)

## Problem

Students get into the system one at a time, either by self-registering at
the kiosk or through Student Management → Add Student. At the start of a
semester the registrar already holds the whole student list in a
spreadsheet, and has no way to load it.

There is a backend route, `POST /api/students/bulk-import` (Admin), but it
only takes a JSON array, nothing in the UI calls it, and it runs the live
mail-server check on every email (about 1 s per student). It can't read a
file, show a preview, or update existing students.

## Goals

1. An **Admin** uploads an **Excel (.xlsx) or CSV** file of students from
   Student Management.
2. The system checks every row and shows a **preview** of how many students
   are new, updated, unchanged and invalid (with the reason for each invalid
   one) **before anything is saved**.
3. On **Import**, valid rows are saved. A new student number creates a
   student. An existing student number **updates** that student. Invalid
   rows are skipped and reported, and the Admin can download them as a file
   to fix and re-upload.
4. A **downloadable template** with the right headers, an example row and
   dropdowns. The importer also accepts the short forms people actually type
   ("BSIT", "1st Year").
5. Optional **Scholar / Varsity / Graduating** columns.

## Non-goals

- **No Registrar or Staff access.** Imports are Admin only, as decided.
- **No deleting students.** A student missing from the file is left alone.
  The file adds and updates only.
- **No old `.xls` (Excel 97–2003) files** and no Google Sheets link. The
  Admin saves as .xlsx or .csv.
- **No background job or progress bar.** 2,000 rows are checked and saved
  inside one request in a few seconds.
- **No live mail-server (MX) check during import.** Only the email format
  is checked; see Decisions.
- **No undo.** The preview is the safeguard, and the audit log records who
  imported what.

## Decisions (confirmed with user)

| Question | Decision |
|---|---|
| Formats | **.xlsx and .csv** |
| Existing student number | **Update** that student (the file is the latest record) |
| Flow | **Preview, then confirm.** Nothing is saved until the Admin clicks Import |
| Invalid rows | **Import the valid rows** and report the invalid ones, downloadable as a file |
| Who | **Admin only** |
| Columns and values | **Downloadable template + friendly values** ("BSIT", "1st Year", "Yes") |
| Priority flags | **Optional columns**; see the column rules below |
| Email check | **Format only on import**; the kiosk keeps the full mail-server check |
| Preview mechanism | **Approach A**: the same file is uploaded twice (preview, then commit), with no state stored in between |
| Limits | **2 MB per file, 2,000 student rows** |

## Approach — upload twice, nothing stored in between

```
StudentManagementView ── Import Students (Admin)
  1. choose file ──► POST /api/students/import?commit=false ──► parse → validate → diff
                     ◄── ImportReport (counts + per-row problems + planned changes)
  2. Import ───────► POST /api/students/import?commit=true  (same file)
                     parse → validate → diff → save valid rows in ONE transaction
                     ◄── ImportReport (what was actually saved)
  3. Download template: GET /api/students/import-template.xlsx
```

The commit request re-parses and re-validates the file, so a student who
changed between preview and Import is handled correctly. Nothing waits on
the server between the two steps.

## Backend units

| unit | purpose |
|---|---|
| `app/services/student_import/reader.py` | Bytes → a list of raw rows (`{header: cell text}` plus the sheet row number). Handles .xlsx and .csv, the size, row and zip limits, and header detection. Knows nothing about students. |
| `app/services/student_import/normalize.py` | Friendly values → system values (course codes, year levels, Yes/No). Pure functions with a table-driven test. |
| `app/services/student_import/importer.py` | `StudentImporter(db).run(rows, commit)`: validates each row with the **same Pydantic models the rest of the app uses** (`StudentCreate`), compares it with the existing student, and on commit saves in one transaction. |
| `app/services/student_import/template.py` | Builds the template .xlsx (XlsxWriter, already a dependency). |
| `app/models/student_import.py` | The `ImportReport` / `ImportRowProblem` / `ImportChange` response models. |
| `app/api/students.py` | The two new routes. **The old JSON `POST /students/bulk-import` is removed.** Nothing calls it, and it's superseded. |

### Reading the file (`reader.py`)

- **Size:** the upload is read in chunks, at most 2 MB + 1 byte. Anything
  over 2 MB is rejected with `413` "The file is larger than 2 MB." before it
  is parsed.
- **Type:** decided by **content, not file name**. A file starting with the
  ZIP signature `PK\x03\x04` is treated as .xlsx. Anything else must decode
  as text and is treated as CSV. An old `.xls` (OLE signature
  `D0 CF 11 E0`) gets "This is an old Excel 97–2003 file. Open it in Excel
  and Save As .xlsx or .csv."
- **.xlsx safety:** before openpyxl opens the file, its ZIP entries are
  listed. A total uncompressed size over 25 MB is rejected (zip-bomb
  guard). **`defusedxml`** is installed; openpyxl uses it automatically to
  block XML entity attacks. The workbook is opened with
  `read_only=True, data_only=True`: formulas are never evaluated, and a
  formula cell reads as its last saved value. Only the **first worksheet**
  is read.
- **CSV:** decoded as `utf-8-sig` (strips Excel's BOM), falling back to
  `cp1252` (Excel's "CSV" on Windows). The delimiter (`,` or `;`) is
  detected with `csv.Sniffer`.
- **Header row:** the first non-empty row. Headers are matched
  case-insensitively, ignoring spaces, punctuation and a trailing `*`. A
  few aliases are accepted ("Student No.", "Student Number", "ID Number";
  "Email Address"; "Year"). Unknown columns are ignored and listed in the
  report as "ignored columns". A missing **required** column rejects the
  whole file with `400` naming the missing columns.
- **Rows:** fully blank rows are skipped. More than **2,000** data rows
  rejects the whole file with `400` "The file has N students; the limit is
  2,000 per import. Split it into smaller files."
- **Cell values:** Excel numbers are converted carefully. A student number
  stored as a number (`2021000001` or `2021000001.0`) becomes
  `"2021000001"`. A value in scientific notation (`2.021E+09`, which happens
  when a CSV was edited in Excel) is reported on that row as "Student
  number was changed by Excel (2.021E+09). Format the column as Text and
  re-enter it."

### Columns and accepted values (`normalize.py`)

| column (header) | required | accepts |
|---|---|---|
| Student Number | yes | exactly 10 digits |
| First Name, Last Name | yes | 1–50 characters (trimmed) |
| Email | yes | a valid email format, ≤ 100 characters |
| Student Type | yes | Undergraduate / Undergrad, Graduate / Grad, Alumni / Alumnus |
| Course | yes | code or full name, any case: BSIT, BSHM, BSBA, BSCpE/BSCPE, BSEd/BSED, BIT |
| Major | only for BIT | Computer Technology (or "BIT Computer Technology", "CT"), Food Processing Technology ("FPT"); must be blank for other courses |
| Year Level | yes | 1–5, "1st", "1st Year", "First Year", "1st_year" … "5th Year"; "Graduate" |
| Scholar, Varsity, Graduating | no | Yes/No, Y/N, True/False, 1/0, ✓ |

**Priority flag columns.** If a column is **absent from the file**,
existing students keep their current value and new students get No. If the
column is present but a cell is **blank**, the same rule applies: blank
never clears a flag. Only an explicit "No" clears one. An empty cell is
never read as a decision to remove a student's priority.

After normalising, each row is validated with **`StudentCreate`**, the same
model and rules as Student Management (10-digit ID, name lengths,
`EmailStr`, the Major/BIT rule). A Pydantic error becomes a readable
message naming the column ("Course: 'BS Nursing' is not a course offered
here").

### Validating against the database (`importer.py`)

- **Same student number twice in the file:** the first occurrence is used,
  and each later one is an error: "Student number also appears in row 12".
- The existing students for all valid student numbers are loaded in **one
  query** (`WHERE student_id IN (...)`), not one per row.
- Each valid row is classified as:
  - **new**: no student with that number;
  - **update**: the student exists and at least one field differs (the
    report lists which fields, e.g. `year_level: 2nd Year → 3rd Year`);
  - **unchanged**: the student exists and nothing differs. It is not
    written.
- **Email:** format only (`EmailStr`). The live MX check
  (`validate_email_deliverable`) is skipped for imports. The file is the
  registrar's own record, and 2,000 DNS lookups would take about 30
  minutes. The kiosk and Add Student keep the full check.
- **Commit:** every new and update row is saved in **one transaction**, so
  a database error (e.g. a lost connection) saves nothing and the Admin can
  simply retry. Invalid rows are never written.

### The report (`ImportReport`)

```json
{
  "committed": false,
  "file_type": "xlsx",
  "total_rows": 412,
  "new": 380, "updated": 20, "unchanged": 7, "invalid": 5,
  "ignored_columns": ["Section"],
  "problems": [
    {"row": 14, "student_number": "20210001", "column": "Student Number",
     "message": "Must be exactly 10 digits.",
     "values": {"Student Number": "20210001", "First Name": "Ana", "...": "..."}}
  ],
  "changes": [
    {"row": 3, "student_number": "2021000001", "action": "update",
     "fields": {"year_level": ["2nd Year", "3rd Year"]}}
  ]
}
```

- `problems[].values` carries the row's original cell text, so the browser
  can build the "rows with errors" download without re-reading the file.
- `changes` lists **new and updated rows only**, capped at 2,000 items like
  the file, so the preview can show exactly what will change.
- The report contains **no data that wasn't in the uploaded file**, apart
  from the "before" side of updated fields, which Admins can already see in
  Student Management.

### API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/students/import?commit=false\|true` | Admin | Multipart `file`. `commit=false` (the default) returns the preview; `commit=true` saves the valid rows. |
| GET | `/api/students/import-template.xlsx` | Admin | The template. |

- `require_role(UserRole.ADMIN)` on both, and
  `@limiter.limit("20/minute")` on the import route.
- `commit` is a `bool` query param. The file field is `UploadFile`, and its
  size and content are checked as described above. Errors use the usual
  `{"detail": ...}` shape (`400` / `413`).
- **Audit:** a commit logs the existing event `student.bulk_imported` with
  `detail="new=…, updated=…, unchanged=…, invalid=…, file=xlsx"` and the
  actor. It never includes names, numbers or the file name, because the
  file name could hold personal data. A preview is not logged, since it
  changes nothing.
- **Logs:** no student data is written to the app logs. A parse failure
  logs the exception type only.

### Template (`template.py`)

`students_import_template.xlsx`, built with XlsxWriter:
- Sheet **Students**: the header row (required headers marked `*`) and one
  example row in grey italics, labelled to delete. The Student Number
  column is **formatted as Text**, so Excel can't turn numbers into
  scientific notation. Dropdowns (data validation) for Student Type,
  Course, Major, Year Level and the Yes/No flag columns.
- Sheet **Instructions**: what each column accepts (the table above), the
  update and flag rules, and the 2,000-row / 2 MB limit.
- The reader skips the example row only if it is still exactly the example.

## Frontend

**Student Management (`StudentManagementView.vue`)**: an **Import
Students** button next to Add Student, shown only to Admins. It opens a
modal with three steps:

1. **Choose file.** A file picker (`.xlsx,.csv`) and a **Download
   template** link, plus the limits in one line. Picking a file runs the
   preview straight away.
2. **Preview.** Four counts: **New**, **Updated**, **Unchanged** and
   **Invalid**. Then:
   - a **Problems** table (row, student number, column, message), when
     there are invalid rows;
   - an expandable **Changes** list, where updates show `field: old → new`;
   - "Ignored columns: Section", when some columns weren't used.

   **Import N students** stays disabled when nothing is new or updated.
   **Choose another file** goes back to step 1.
3. **Done.** The saved counts, a **Download rows with errors (.csv)** button
   when there were invalid rows, and **Close**, which reloads the student
   list.

**The error file is built in the browser** from `problems[].values`, with
the original columns plus an **Error** column. Every cell starting with
`=`, `+`, `-`, `@`, a tab or a carriage return is prefixed with `'`
(**CSV formula-injection guard**), because the file is meant to be opened
in Excel. This logic lives in `services/studentImportCsv.js` so it can be
unit-tested.

**Store:** `previewStudentImport(file)`, `commitStudentImport(file)` and
`downloadStudentImportTemplate()`, all `multipart/form-data` or blob calls
through the existing axios instance (relative `/api`, cookies). They use
the existing `err.response?.data?.detail` error pattern.

The modal is usable on a phone (stacked counts, a scrollable problems
table), though imports will mostly happen on a desktop.

## Dependencies

Added to `requirements.txt`, pinned with `==` per the supply-chain rule:
`openpyxl==3.1.5`, its dependency `et_xmlfile` (the exact version pip
resolves), and `defusedxml==0.7.1`. CI's `pip-audit` covers them. No
frontend dependency is added.

## Testing

**Backend (pytest)**, using real .xlsx/.csv bytes built in the tests with
XlsxWriter or plain strings:

- **reader:** .xlsx and .csv (comma, semicolon, BOM, cp1252) read the same
  rows; header aliases, case and the `*` are accepted; a missing required
  column gives `400` naming it; >2 MB gives `413`; 2,001 rows gives `400`;
  an `.xls` signature, random bytes and an empty file each give clear
  messages; a ZIP with a huge uncompressed member is rejected; a numeric
  student number becomes the 10-digit string; scientific notation is a row
  error; formula cells read as values and are never evaluated.
- **normalize:** a table test for every accepted spelling of course, year
  level, type, major and flags, plus rejects.
- **importer:** the new / update / unchanged / invalid classification; the
  duplicate in the file points to the first row; the flag rules (column
  absent keeps, blank keeps, "No" clears, new defaults to No); the BIT
  major rule; preview writes nothing; commit writes exactly the new and
  update rows in one transaction (a simulated DB error mid-commit leaves
  nothing saved); the MX check is not called (patched to fail).
- **API:** Admin gets `200`; Registrar and Staff get `403`; anonymous gets
  `401`; `commit=true` emits `student.bulk_imported` with counts only; the
  template downloads as a valid .xlsx with the expected headers and
  dropdowns.
- **Removed route:** `POST /students/bulk-import` now returns `404` or
  `405`. `tests/test_student_priority_trust.py` moves its "trusted caller
  can set flags" check from the old JSON route to the file import.

**Frontend (Vitest):** `studentImportCsv` (columns + Error column, the
formula-guard prefixes, quoting of commas, quotes and newlines) and the
store actions (multipart body, `commit` param, error detail).

**End-to-end:** on `bsu_queue_test`, as Admin, download the template, fill
in about 20 rows (some new, one update, a few deliberately bad), preview,
import, check the list, and download the error file.

## Rollout

- **No database migration.** The import writes the existing `students`
  columns.
- Update `CLAUDE.md`: the new routes, the removal of `/students/bulk-import`
  in **Avoid Trusting User Input** (which names it as a trusted flag-setting
  path), the Input Validation table (file limits, accepted values), and the
  "format-only email on import" exception.
