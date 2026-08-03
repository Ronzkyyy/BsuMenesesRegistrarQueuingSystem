<template>
  <div>
    <div class="mb-8 flex items-center justify-between">
      <div>
        <h2 class="text-3xl font-bold text-gray-900">Student Management</h2>
        <p class="mt-2 text-gray-600">View and edit student records</p>
      </div>
      <button
        v-if="canEdit"
        @click="openCreateModal"
        class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
      >
        <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Add Student
      </button>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 mb-6 flex flex-wrap gap-3">
      <input
        v-model="filters.query"
        @keyup.enter="applyFilters"
        type="text"
        placeholder="Search by ID, name, or email"
        class="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
      />
      <select v-model="filters.course" class="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
        <option value="">All Courses</option>
        <option v-for="c in courses" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="filters.year_level" class="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
        <option value="">All Year Levels</option>
        <option v-for="y in yearLevels" :key="y.value" :value="y.value">{{ y.label }}</option>
      </select>
      <button
        @click="applyFilters"
        class="px-4 py-2 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200"
      >
        Search
      </button>
    </div>

    <div v-if="listError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ listError }}</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student ID</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Course</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Year Level</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Flags</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
          <tr v-for="student in queueStore.students" :key="student.id">
            <td class="px-6 py-4 text-sm font-medium text-gray-900">{{ student.student_id }}</td>
            <td class="px-6 py-4 text-sm text-gray-500">{{ student.first_name }} {{ student.last_name }}</td>
            <td class="px-6 py-4 text-sm text-gray-500">{{ student.course }}</td>
            <td class="px-6 py-4 text-sm text-gray-500">{{ yearLevelLabel(student.year_level) }}</td>
            <td class="px-6 py-4 text-sm text-gray-500 space-x-1">
              <span v-if="student.is_scholar" class="inline-block px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">Scholar</span>
              <span v-if="student.is_varsity" class="inline-block px-2 py-0.5 text-xs rounded-full bg-purple-100 text-purple-800">Varsity</span>
              <span v-if="student.is_graduating" class="inline-block px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-800">Graduating</span>
            </td>
            <td class="px-6 py-4 text-right space-x-2 whitespace-nowrap">
              <button
                v-if="canEdit"
                @click="openEditModal(student)"
                class="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200"
              >
                Edit
              </button>
              <button
                v-if="canDelete"
                @click="removeStudent(student)"
                :disabled="actionLoading"
                class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
              >
                Delete
              </button>
            </td>
          </tr>

          <tr v-if="queueStore.students.length === 0">
            <td colspan="6" class="px-6 py-8 text-center text-gray-500">No students found.</td>
          </tr>
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
    <div v-if="showFormModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">{{ editingStudent ? 'Edit Student' : 'Add Student' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Student ID</label>
            <input
              v-model="form.student_id"
              type="text"
              :disabled="!!editingStudent"
              maxlength="10"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary disabled:bg-gray-100"
              placeholder="10-digit student number"
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">First Name</label>
              <input v-model="form.first_name" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
              <input v-model="form.last_name" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input v-model="form.email" type="email" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary" />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Student Type</label>
              <select v-model="form.student_type" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
                <option v-for="t in studentTypes" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Year Level</label>
              <select v-model="form.year_level" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
                <option v-for="y in yearLevels" :key="y.value" :value="y.value">{{ y.label }}</option>
              </select>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Course</label>
            <select v-model="form.course" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
              <option v-for="c in courses" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>

          <div v-if="form.course === BIT_COURSE">
            <label class="block text-sm font-medium text-gray-700 mb-1">Major</label>
            <select v-model="form.major" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary">
              <option value="" disabled>Select major</option>
              <option v-for="m in majors" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>

          <div class="flex items-center gap-6 pt-1">
            <label class="flex items-center gap-2 text-sm text-gray-700">
              <input v-model="form.is_scholar" type="checkbox" class="rounded border-gray-300 text-bsu-primary focus:ring-bsu-primary" />
              Scholar
            </label>
            <label class="flex items-center gap-2 text-sm text-gray-700">
              <input v-model="form.is_varsity" type="checkbox" class="rounded border-gray-300 text-bsu-primary focus:ring-bsu-primary" />
              Varsity
            </label>
            <label class="flex items-center gap-2 text-sm text-gray-700">
              <input v-model="form.is_graduating" type="checkbox" class="rounded border-gray-300 text-bsu-primary focus:ring-bsu-primary" />
              Graduating
            </label>
          </div>

          <div v-if="formError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ formError }}</p>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showFormModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="submitForm"
            :disabled="actionLoading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            {{ editingStudent ? 'Save Changes' : 'Create' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useQueueStore } from '@/stores/queue'

const BIT_COURSE = 'Bachelor of Industrial Technology'

const courses = [
  'Bachelor of Science in Information Technology',
  'Bachelor of Science in Hospitality Management',
  'Bachelor of Science in Business Administration',
  BIT_COURSE,
]

const majors = [
  'BIT Computer Technology',
  'Food Processing Technology',
]

const studentTypes = ['undergraduate', 'graduate', 'alumni']

const yearLevels = [
  { value: '1st_year', label: '1st Year' },
  { value: '2nd_year', label: '2nd Year' },
  { value: '3rd_year', label: '3rd Year' },
  { value: '4th_year', label: '4th Year' },
  { value: '5th_year', label: '5th Year' },
  { value: 'graduate', label: 'Graduate' },
]

const yearLevelLabel = (value) => yearLevels.find((y) => y.value === value)?.label || value

const queueStore = useQueueStore()

const canEdit = computed(() => ['admin', 'registrar'].includes(queueStore.currentUser?.role))
const canDelete = computed(() => queueStore.currentUser?.role === 'admin')

const listError = ref('')
const formError = ref('')
const actionLoading = ref(false)
const showFormModal = ref(false)
const editingStudent = ref(null)

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

const openCreateModal = () => {
  editingStudent.value = null
  formError.value = ''
  form.value = emptyForm()
  showFormModal.value = true
}

const openEditModal = (student) => {
  editingStudent.value = student
  formError.value = ''
  form.value = {
    student_id: student.student_id,
    first_name: student.first_name,
    last_name: student.last_name,
    email: student.email,
    student_type: student.student_type,
    course: student.course,
    major: student.major || '',
    year_level: student.year_level,
    is_scholar: student.is_scholar,
    is_varsity: student.is_varsity,
    is_graduating: student.is_graduating,
  }
  showFormModal.value = true
}

const buildPayload = () => {
  const payload = { ...form.value }
  payload.major = payload.course === BIT_COURSE ? payload.major || null : null
  return payload
}

const submitForm = async () => {
  if (!form.value.student_id || !form.value.first_name || !form.value.last_name || !form.value.email) {
    formError.value = 'Please fill in all required fields.'
    return
  }
  if (!/^\d{10}$/.test(form.value.student_id)) {
    formError.value = 'Student ID must be exactly 10 digits.'
    return
  }
  if (form.value.course === BIT_COURSE && !form.value.major) {
    formError.value = 'Major is required for Bachelor of Industrial Technology.'
    return
  }

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
  } catch (err) {
    const detail = err.response?.data?.detail
    formError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to save student'
  } finally {
    actionLoading.value = false
  }
}

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

onMounted(async () => {
  await loadStudents()
})
</script>
