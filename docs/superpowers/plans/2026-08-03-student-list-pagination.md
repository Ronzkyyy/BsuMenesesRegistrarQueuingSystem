# Student List Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins browse and edit the full student roster (2,000+ records expected) via numbered pagination on the Student Management admin page, instead of the current hardcoded 50-row cap with no way to see anything past it.

**Architecture:** `GET /api/students` changes from returning a bare array to a `{ items, total, skip, limit }` envelope, computed via one extra `COUNT(*)` alongside the existing filtered query. The Pinia store's `searchStudents` action consumes that envelope into `students` + a new `studentsTotal` state field. `StudentManagementView.vue` adds page-number state, a `loadStudents()` helper that derives `skip` from the current page, a numbered Prev/Next pagination control with ellipsis truncation, and edge-case handling for delete (step back a page if the last row on a page is removed) and create (refresh the current page/total). A small unrelated bug found in the same file - the Major dropdown visually pre-selecting an option it hasn't actually set in `form.major` - is fixed in the same task since it touches the same component.

**Tech Stack:** Python FastAPI + SQLAlchemy (backend), Vue 3 + Pinia (frontend). No test framework is configured for either side (per `CLAUDE.md`) - verification is manual, against the real running stack (backend + Postgres + frontend dev server), per this project's established convention.

## Global Constraints

- Page size is fixed at 25 (`limit` default changes from 50 to 25 on both the backend endpoint and the frontend's `searchStudents` default) - no page-size selector.
- `GET /api/students` response shape becomes `{ items: List[Student], total: int, skip: int, limit: int }` - confirmed via grep that no other frontend code consumes this endpoint besides `queueStore.searchStudents`, so this is a safe non-breaking change within this codebase.
- No sorting controls, no CSV export, no change to `POST /students/bulk-import`'s request/response shape - out of scope.
- Do not touch the edit (`PATCH`) code path's payload shape - it already works and isn't part of this feature.

---

### Task 1: Backend — paginated envelope response from `GET /api/students`

**Files:**
- Modify: `bsu-registrar-queue/backend/app/models/student.py`
- Modify: `bsu-registrar-queue/backend/app/services/student_service.py:1-10,57-86`
- Modify: `bsu-registrar-queue/backend/app/api/students.py:1-16,59-77`

**Interfaces:**
- Consumes: existing `StudentDB` model and `Student`/`Course`/`YearLevel` schemas - no changes to those.
- Produces: `StudentListResponse` Pydantic model (`items: List[Student]`, `total: int`, `skip: int`, `limit: int`) and `StudentService.search_students(...) -> Tuple[List[Student], int]` (now returns `(page_of_students, total_matching_count)` instead of just the list) - Task 2's frontend work consumes the resulting JSON shape (`response.data.items`, `response.data.total`).

- [ ] **Step 1: Add the `StudentListResponse` envelope model**

In `bsu-registrar-queue/backend/app/models/student.py`, change the import on line 5 from:

```python
from typing import Optional
```

to:

```python
from typing import List, Optional
```

Then append this new class at the end of the file (after `StudentInDB`):

```python


class StudentListResponse(BaseModel):
    items: List[Student]
    total: int
    skip: int
    limit: int
```

- [ ] **Step 2: Make `search_students` return `(items, total)`**

In `bsu-registrar-queue/backend/app/services/student_service.py`, change the import on line 5 from:

```python
from typing import List, Optional
```

to:

```python
from typing import List, Optional, Tuple
```

Then replace the `search_students` method (lines 57-85):

```python
    def search_students(
        self,
        query: str = "",
        course: Optional[Course] = None,
        year_level: Optional[YearLevel] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Student]:
        """Search students with filters"""
        q = self.db.query(StudentDB)

        if query:
            q = q.filter(
                or_(
                    StudentDB.student_id.ilike(f"%{query}%"),
                    StudentDB.first_name.ilike(f"%{query}%"),
                    StudentDB.last_name.ilike(f"%{query}%"),
                    StudentDB.email.ilike(f"%{query}%"),
                )
            )

        if course:
            q = q.filter(StudentDB.course == course)

        if year_level:
            q = q.filter(StudentDB.year_level == year_level)

        students = q.offset(skip).limit(limit).all()
        return [self._to_student(s) for s in students]
```

with:

```python
    def search_students(
        self,
        query: str = "",
        course: Optional[Course] = None,
        year_level: Optional[YearLevel] = None,
        skip: int = 0,
        limit: int = 25
    ) -> Tuple[List[Student], int]:
        """Search students with filters. Returns (page of students, total matching count)."""
        q = self.db.query(StudentDB)

        if query:
            q = q.filter(
                or_(
                    StudentDB.student_id.ilike(f"%{query}%"),
                    StudentDB.first_name.ilike(f"%{query}%"),
                    StudentDB.last_name.ilike(f"%{query}%"),
                    StudentDB.email.ilike(f"%{query}%"),
                )
            )

        if course:
            q = q.filter(StudentDB.course == course)

        if year_level:
            q = q.filter(StudentDB.year_level == year_level)

        total = q.count()
        students = q.offset(skip).limit(limit).all()
        return [self._to_student(s) for s in students], total
```

- [ ] **Step 3: Update the `list_students` endpoint to return the envelope**

In `bsu-registrar-queue/backend/app/api/students.py`, change the import on line 11 from:

```python
from ..models.student import Student, StudentCreate, StudentBase
```

to:

```python
from ..models.student import Student, StudentCreate, StudentBase, StudentListResponse
```

Then replace the `list_students` endpoint (lines 59-77):

```python
@router.get("", response_model=List[Student])
def list_students(
    query: str = "",
    course: Optional[Course] = None,
    year_level: Optional[YearLevel] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """List students with filters (staff only)"""
    service = StudentService(db)
    return service.search_students(
        query=query,
        course=course,
        year_level=year_level,
        skip=skip,
        limit=limit
    )
```

with:

```python
@router.get("", response_model=StudentListResponse)
def list_students(
    query: str = "",
    course: Optional[Course] = None,
    year_level: Optional[YearLevel] = None,
    skip: int = 0,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """List students with filters (staff only)"""
    service = StudentService(db)
    items, total = service.search_students(
        query=query,
        course=course,
        year_level=year_level,
        skip=skip,
        limit=limit
    )
    return StudentListResponse(items=items, total=total, skip=skip, limit=limit)
```

- [ ] **Step 4: Start the backend against the real dev database**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload
```

Expected: starts with no import/startup errors (confirms the new `StudentListResponse` import and `Tuple` import are both valid).

- [ ] **Step 5: Seed 30 test students and verify the paginated envelope, in a second terminal**

```bash
python -c "
import urllib.request, urllib.parse, json

BASE = 'http://localhost:8000/api'

login_data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request(f'{BASE}/auth/login', data=login_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = json.loads(urllib.request.urlopen(req, timeout=5).read())['access_token']
auth_headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

students = [
    {
        'student_id': f'90000000{str(i).zfill(2)}',
        'first_name': f'Test{i}',
        'last_name': 'Pagination',
        'email': f'test.pagination{i}@bsu.edu.ph',
        'student_type': 'undergraduate',
        'course': 'Bachelor of Science in Information Technology',
        'year_level': '1st_year',
    }
    for i in range(1, 31)
]
req = urllib.request.Request(f'{BASE}/students/bulk-import', data=json.dumps(students).encode(), headers=auth_headers, method='POST')
result = json.loads(urllib.request.urlopen(req, timeout=10).read())
print('Seeded:', result['imported'], 'errors:', result['errors'])
assert result['imported'] == 30, f\"expected to seed 30 students, got {result['imported']} (errors: {result['errors_detail']})\"

req = urllib.request.Request(f'{BASE}/students?query=Pagination&limit=25&skip=0', headers=auth_headers)
page1 = json.loads(urllib.request.urlopen(req, timeout=5).read())
print('Page 1:', len(page1['items']), 'items, total', page1['total'], 'skip', page1['skip'], 'limit', page1['limit'])
assert set(page1.keys()) == {'items', 'total', 'skip', 'limit'}, f'unexpected envelope keys: {page1.keys()}'
assert len(page1['items']) == 25, f\"expected 25 items on page 1, got {len(page1['items'])}\"
assert page1['total'] == 30, f\"expected total 30, got {page1['total']}\"

req = urllib.request.Request(f'{BASE}/students?query=Pagination&limit=25&skip=25', headers=auth_headers)
page2 = json.loads(urllib.request.urlopen(req, timeout=5).read())
print('Page 2:', len(page2['items']), 'items, total', page2['total'])
assert len(page2['items']) == 5, f\"expected 5 items on page 2, got {len(page2['items'])}\"

page1_ids = {s['student_id'] for s in page1['items']}
page2_ids = {s['student_id'] for s in page2['items']}
assert not (page1_ids & page2_ids), 'page 1 and page 2 overlap - offset/limit is broken'

print('OK - envelope shape, total count, and offset slicing all correct')
"
```

Expected: prints `Seeded: 30 errors: 0`, then `Page 1: 25 items, total 30 skip 0 limit 25`, then `Page 2: 5 items, total 30`, then `OK - envelope shape, total count, and offset slicing all correct`, with no assertion errors.

**Leave these 30 seeded students in place** - Task 2's manual verification reuses them (do not delete yet; cleanup happens at the end of Task 2).

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/backend/app/models/student.py bsu-registrar-queue/backend/app/services/student_service.py bsu-registrar-queue/backend/app/api/students.py
git commit -m "feat(students): return paginated envelope from GET /api/students"
```

---

### Task 2: Frontend — numbered pagination UI + Major dropdown fix

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js:38-41,746-762,850-865`
- Modify: `bsu-registrar-queue/frontend/src/views/StudentManagementView.vue`

**Interfaces:**
- Consumes: `StudentListResponse` envelope produced by Task 1 (`{ items, total, skip, limit }` from `GET /api/students`) - this task cannot be meaningfully verified end-to-end until Task 1 is deployed and its 30 `Pagination`-tagged test students exist in the database.
- Produces: `queueStore.studentsTotal` (new state field) and `queueStore.searchStudents(query, course, yearLevel, skip, limit)` now populating `this.students` from `response.data.items` - no other frontend code consumes `searchStudents` besides this same view, so no other files need updating.

- [ ] **Step 1: Update the Pinia store to consume the envelope**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, replace the Students state block (lines 38-41):

```javascript
    // Students
    currentStudent: null,
    students: [],
    studentStats: null,
```

with:

```javascript
    // Students
    currentStudent: null,
    students: [],
    studentsTotal: 0,
    studentStats: null,
```

Replace the `searchStudents` action (lines 746-762):

```javascript
    async searchStudents(query = '', course = null, yearLevel = null, skip = 0, limit = 50) {
      this.loading = true
      this.error = null
      try {
        const params = { query, skip, limit }
        if (course) params.course = course
        if (yearLevel) params.year_level = yearLevel
        const response = await api.get('/students', { params })
        this.students = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to search students'
        throw err
      } finally {
        this.loading = false
      }
    },
```

with:

```javascript
    async searchStudents(query = '', course = null, yearLevel = null, skip = 0, limit = 25) {
      this.loading = true
      this.error = null
      try {
        const params = { query, skip, limit }
        if (course) params.course = course
        if (yearLevel) params.year_level = yearLevel
        const response = await api.get('/students', { params })
        this.students = response.data.items
        this.studentsTotal = response.data.total
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to search students'
        throw err
      } finally {
        this.loading = false
      }
    },
```

In the `reset()` action, replace this line (currently around line 860):

```javascript
      this.students = []
```

with:

```javascript
      this.students = []
      this.studentsTotal = 0
```

- [ ] **Step 2: Add pagination state and a `loadStudents()` helper to the view's script**

In `bsu-registrar-queue/frontend/src/views/StudentManagementView.vue`, replace this block:

```javascript
const filters = ref({ query: '', course: '', year_level: '' })

const emptyForm = () => ({
  student_id: '',
  first_name: '',
  last_name: '',
  email: '',
  student_type: 'undergraduate',
  course: courses[0],
  major: '',
  year_level: '1st_year',
  is_scholar: false,
  is_varsity: false,
  is_graduating: false,
})

const form = ref(emptyForm())

const applyFilters = async () => {
  listError.value = ''
  try {
    await queueStore.searchStudents(filters.value.query, filters.value.course || null, filters.value.year_level || null)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to load students'
  }
}
```

with:

```javascript
const filters = ref({ query: '', course: '', year_level: '' })

const PAGE_SIZE = 25
const page = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(queueStore.studentsTotal / PAGE_SIZE)))
const rangeStart = computed(() => (queueStore.studentsTotal === 0 ? 0 : (page.value - 1) * PAGE_SIZE + 1))
const rangeEnd = computed(() => Math.min(page.value * PAGE_SIZE, queueStore.studentsTotal))

const paginationRange = computed(() => {
  const total = totalPages.value
  const current = page.value
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }
  const pages = new Set([1, total, current, current - 1, current - 2, current + 1, current + 2])
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b)
  const withEllipses = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) withEllipses.push('…')
    withEllipses.push(p)
  })
  return withEllipses
})

const emptyForm = () => ({
  student_id: '',
  first_name: '',
  last_name: '',
  email: '',
  student_type: 'undergraduate',
  course: courses[0],
  major: '',
  year_level: '1st_year',
  is_scholar: false,
  is_varsity: false,
  is_graduating: false,
})

const form = ref(emptyForm())

const loadStudents = async () => {
  listError.value = ''
  try {
    const skip = (page.value - 1) * PAGE_SIZE
    await queueStore.searchStudents(filters.value.query, filters.value.course || null, filters.value.year_level || null, skip, PAGE_SIZE)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to load students'
  }
}

const applyFilters = async () => {
  page.value = 1
  await loadStudents()
}

const goToPage = async (targetPage) => {
  if (targetPage < 1 || targetPage > totalPages.value || targetPage === page.value) return
  page.value = targetPage
  await loadStudents()
}
```

- [ ] **Step 3: Add the pagination control to the template**

In the same file, replace this block:

```html
        </tbody>
      </table>
    </div>

    <!-- Create / Edit Modal -->
```

with:

```html
        </tbody>
      </table>
    </div>

    <div v-if="queueStore.studentsTotal > 0" class="mt-4 flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-gray-600">
        Showing {{ rangeStart }}-{{ rangeEnd }} of {{ queueStore.studentsTotal }} students
      </p>
      <nav class="flex items-center gap-1">
        <button
          @click="goToPage(page - 1)"
          :disabled="page === 1"
          class="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ‹ Prev
        </button>
        <template v-for="(p, idx) in paginationRange" :key="idx">
          <span v-if="p === '…'" class="px-2 text-sm text-gray-400">…</span>
          <button
            v-else
            @click="goToPage(p)"
            class="px-3 py-1.5 text-sm font-medium rounded-md"
            :class="p === page ? 'bg-bsu-primary text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
          >
            {{ p }}
          </button>
        </template>
        <button
          @click="goToPage(page + 1)"
          :disabled="page === totalPages"
          class="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next ›
        </button>
      </nav>
    </div>

    <!-- Create / Edit Modal -->
```

- [ ] **Step 4: Handle the "deleted the last row on the last page" edge case**

Replace the `removeStudent` function:

```javascript
const removeStudent = async (student) => {
  if (!confirm(`Are you sure you want to delete ${student.first_name} ${student.last_name} (${student.student_id})? This cannot be undone.`)) return

  actionLoading.value = true
  listError.value = ''
  try {
    await queueStore.deleteStudent(student.id)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to delete student'
  } finally {
    actionLoading.value = false
  }
}
```

with:

```javascript
const removeStudent = async (student) => {
  if (!confirm(`Are you sure you want to delete ${student.first_name} ${student.last_name} (${student.student_id})? This cannot be undone.`)) return

  actionLoading.value = true
  listError.value = ''
  try {
    await queueStore.deleteStudent(student.id)
    await loadStudents()
    if (queueStore.students.length === 0 && page.value > 1) {
      page.value -= 1
      await loadStudents()
    }
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to delete student'
  } finally {
    actionLoading.value = false
  }
}
```

- [ ] **Step 5: Refresh the list after creating a student, and fix the Major dropdown placeholder**

Replace the `submitForm` function's try block:

```javascript
  actionLoading.value = true
  formError.value = ''
  try {
    const payload = buildPayload()
    if (editingStudent.value) {
      // PATCH validates against StudentBase, which requires student_id even
      // though the service ignores it for updates - keep it in the payload.
      await queueStore.updateStudent(editingStudent.value.id, payload)
    } else {
      await queueStore.createStudent(payload)
    }
    showFormModal.value = false
```

with:

```javascript
  actionLoading.value = true
  formError.value = ''
  try {
    const payload = buildPayload()
    if (editingStudent.value) {
      // PATCH validates against StudentBase, which requires student_id even
      // though the service ignores it for updates - keep it in the payload.
      await queueStore.updateStudent(editingStudent.value.id, payload)
    } else {
      await queueStore.createStudent(payload)
      await loadStudents()
    }
    showFormModal.value = false
```

Then replace the Major `<select>` in the template:

```html
          <div v-if="form.course === BIT_COURSE">
            <label class="block text-sm font-medium text-gray-700 mb-1">Major</label>
            <select v-model="form.major" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
              <option v-for="m in majors" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
```

with:

```html
          <div v-if="form.course === BIT_COURSE">
            <label class="block text-sm font-medium text-gray-700 mb-1">Major</label>
            <select v-model="form.major" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
              <option value="" disabled>Select major</option>
              <option v-for="m in majors" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
```

Finally, replace the `onMounted` hook:

```javascript
onMounted(async () => {
  try {
    await queueStore.searchStudents()
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to load students'
  }
})
```

with:

```javascript
onMounted(async () => {
  await loadStudents()
})
```

- [ ] **Step 6: Verify the build compiles**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: succeeds with no errors.

- [ ] **Step 7: Manually verify pagination behavior in the browser, using Task 1's seeded data**

With Task 1's backend still running (port 8000) and the 30 `Pagination`-tagged test students still in the database, start the frontend dev server:

```bash
cd bsu-registrar-queue/frontend
npm run dev
```

If browser automation (e.g. `claude-in-chrome`) is available in this environment, drive the checklist below directly. Otherwise, perform it yourself if you have a browser, or ask the user to run through it and report back - **do not mark this task complete without this checklist passing**, since none of this page-stepping logic is covered by the API-level script in Task 1:

1. Log in at `/login` as `admin` / `admin123`, go to Admin → Students.
2. Type `Pagination` in the search box, press Enter. Confirm the label reads "Showing 1-25 of 30 students", page buttons show `[1]` (highlighted) and `[2]`, `‹ Prev` is disabled, `Next ›` is enabled.
3. Click `Next ›` (or page `[2]`). Confirm the label reads "Showing 26-30 of 30 students", 5 rows are shown, `Next ›` is now disabled, `‹ Prev` is enabled.
4. **While still on page 2** (page > 1), click "Add Student" and create one more with student ID `9000000099`, last name `Pagination`, course "Bachelor of Science in Information Technology". Confirm it saves without error, the total in the label becomes 31, and the view doesn't crash or navigate away from page 2 (this exercises "create while on page > 1 refreshes the total without erroring").
5. On page 2 (now showing 6 of 31), delete 5 of the 6 remaining students one at a time (confirm the dialog each time). After each delete, confirm the total in the label decrements and the row count matches.
6. Delete the 6th (last) remaining student on page 2. Confirm the view automatically steps back to page 1, showing "Showing 1-25 of 25 students", with `Next ›` now disabled (only 1 page left) - it should NOT show an empty page 2.
7. Click "Add Student" again, set Course to "Bachelor of Industrial Technology". Confirm the Major dropdown shows no option highlighted (placeholder "Select major" is what's visually selected, not "BIT Computer Technology"). Click Create without picking a major and confirm the error "Major is required for Bachelor of Industrial Technology." appears. Cancel out of the modal.
8. With the search box still containing `Pagination`, change the Course filter dropdown to "Bachelor of Science in Information Technology" and click Search while sitting on page 1 - then click to page 2 if more than 25 results remain, or confirm it stays correct if not. Then clear the Course filter back to "All Courses" and click Search again - confirm the view resets to page 1 rather than staying on whatever page you were on.

- [ ] **Step 8: Clean up the seeded test data**

```bash
python -c "
import urllib.request, urllib.parse, json

BASE = 'http://localhost:8000/api'

login_data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request(f'{BASE}/auth/login', data=login_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = json.loads(urllib.request.urlopen(req, timeout=5).read())['access_token']
auth_headers = {'Authorization': f'Bearer {token}'}

req = urllib.request.Request(f'{BASE}/students?query=Pagination&limit=100&skip=0', headers=auth_headers)
remaining = json.loads(urllib.request.urlopen(req, timeout=5).read())
print('Deleting', remaining['total'], 'leftover test students')

for student in remaining['items']:
    del_req = urllib.request.Request(f\"{BASE}/students/{student['id']}\", headers=auth_headers, method='DELETE')
    urllib.request.urlopen(del_req, timeout=5)

req = urllib.request.Request(f'{BASE}/students?query=Pagination&limit=100&skip=0', headers=auth_headers)
check = json.loads(urllib.request.urlopen(req, timeout=5).read())
assert check['total'] == 0, f\"expected 0 leftover test students, got {check['total']}\"
print('OK - all test students cleaned up')
"
```

Expected: prints the count being deleted, then `OK - all test students cleaned up`.

- [ ] **Step 9: Commit**

```bash
git add bsu-registrar-queue/frontend/src/stores/queue.js bsu-registrar-queue/frontend/src/views/StudentManagementView.vue
git commit -m "feat(students): add numbered pagination to Student Management admin page"
```
