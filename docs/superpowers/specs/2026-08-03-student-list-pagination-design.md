# Student List Pagination — Design

## Problem

The newly added Student Management admin page (`StudentManagementView.vue`) lists students via `GET /api/students`, which is hardcoded to `skip=0, limit=50` with no way to page further. The system is expected to hold 2,000+ student records at campus scale, so anything beyond the first 50 (in DB order) is invisible and un-editable from this screen, with no indication more records exist. An admin searching for a student outside that first page would wrongly conclude the student isn't registered, risking a duplicate re-creation attempt.

Separately, the Add/Edit Student form's Major `<select>` has no blank placeholder option. When `form.major` is `''` (unset) and the Course is switched to "Bachelor of Industrial Technology," the browser visually pre-highlights the first `<option>` even though the bound value is still empty - if the admin trusts the visual state and submits without touching the dropdown, they hit a "Major is required" error despite what looked like a valid selection.

## Decision

Add classic numbered pagination (Prev/Next + page numbers, with a "Showing X-Y of Z students" count) to the student list, backed by a `{ items, total }` envelope response from `GET /api/students`, at a page size of 25. Bundle in the trivial Major-dropdown placeholder fix since it touches the same file.

### Why an envelope response over the alternatives

- **`X-Total-Count` header**: avoids a body-shape change, but header-based totals are easy to misread and unusual for this codebase's internal admin APIs.
- **Separate `/students/count` endpoint**: doubles the requests per page load for no real benefit.
- **`{ items, total }` envelope (chosen)**: one request per page, total always matches the actual filtered result set. Confirmed via grep that `GET /api/students` / `queueStore.searchStudents` has no other consumers in the frontend, so changing its response shape is non-breaking.

### Why page size 25

Matches campus scale (2,000+ students → ~80-90 pages, a sane range for numbered pagination with ellipsis truncation) and is a reasonable row count for an admin data table.

## Changes

### Backend

**`app/models/student.py`** - add a new response envelope model:
```python
class StudentListResponse(BaseModel):
    items: List[Student]
    total: int
    skip: int
    limit: int
```

**`app/services/student_service.py`** - `search_students` builds the filtered query once (same `query`/`course`/`year_level` filters as today), then:
- `total = q.count()`
- `items = q.offset(skip).limit(limit).all()`

Returns both instead of just the list. One extra `COUNT(*)` per request, same filter predicates as the existing query - negligible cost even at 2,000+ rows given `student_id` lookups are already indexed (unique column).

**`app/api/students.py`** - `list_students` response model becomes `StudentListResponse`; default `limit` query param changes from 50 to 25.

### Frontend

**`src/stores/queue.js`** - `searchStudents(query, course, yearLevel, skip, limit)` keeps its signature, but now sets `this.students = response.data.items` and a new state field `this.studentsTotal = response.data.total` (added to `state()` and reset in `reset()`).

**`src/views/StudentManagementView.vue`**:
- New reactive `page` (starts at 1); computed `totalPages = Math.max(1, Math.ceil(queueStore.studentsTotal / 25))`.
- New `loadStudents()` helper: computes `skip = (page - 1) * 25` and calls `queueStore.searchStudents(filters.query, filters.course || null, filters.year_level || null, skip, 25)`. Replaces the current direct calls in `onMounted` and `applyFilters`.
- `applyFilters` resets `page = 1` before calling `loadStudents()`.
- New pagination control rendered under the table: `‹ Prev` / numbered page buttons (current page ±2, plus first/last, with `…` truncation once `totalPages > 7`) / `Next ›`, plus a "Showing {start}-{end} of {total} students" label (or "No students found" when `total === 0`, matching the existing empty-state row).
- `removeStudent`: after a successful delete, call `loadStudents()` to refresh the current page/total. If the refreshed `queueStore.students` comes back empty and `page > 1`, decrement `page` by 1 and call `loadStudents()` again (handles deleting the last row on the last page).
- `submitForm` (create path only - edit already patches the row in place via the store): after a successful create, call `loadStudents()` to refresh the current page/total; no attempt to locate/jump to the new row, since default DB ordering doesn't guarantee where it lands.
- Major-dropdown fix: add `<option value="" disabled>Select major</option>` as the first option in the Major `<select>`, so an unset `form.major` renders as genuinely blank instead of visually pre-selecting "BIT Computer Technology."

## Testing

No automated test framework is configured for this project (per `CLAUDE.md`). Manual verification plan, against the real running stack:

1. Seed or bulk-import enough students (e.g. via the existing `POST /students/bulk-import`) to exceed 25 records, and confirm `GET /api/students?limit=25` returns `{ items, total, skip, limit }` with `items.length <= 25` and `total` matching the true row count.
2. On the Student Management page, confirm the pagination bar shows the correct total and page count, Prev is disabled on page 1, Next is disabled on the last page, and clicking a page number fetches the right slice (spot-check a middle page's `student_id`s against a direct API call with matching `skip`).
3. Apply a search/course/year-level filter that narrows the result set below the current page number (e.g. filter down to 1 page while sitting on page 3) and confirm the view resets to page 1 and shows the filtered `total`, not the unfiltered one.
4. Delete the sole student on the last page and confirm the view steps back to the new last page instead of showing an empty page.
5. Create a new student while on some page > 1 and confirm the total count updates and the list re-fetches without erroring.
6. On the Add/Edit Student form, set Course to "Bachelor of Industrial Technology" for a new (unedited) student and confirm the Major dropdown shows no option selected until the admin explicitly picks one, and that submitting without picking one still correctly blocks with "Major is required."

## Out of Scope

- A page-size selector (fixed at 25).
- Sorting controls (list order stays DB-default, unchanged from today).
- CSV export or bulk-review tooling for the full 2,000+ roster.
- Changing `POST /students/bulk-import`'s response shape or behavior.
