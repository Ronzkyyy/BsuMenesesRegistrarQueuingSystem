<template>
  <div>
    <div class="mb-6">
      <h2 class="text-3xl font-bold text-bsu-ink">Appointments</h2>
      <p class="mt-2 text-gray-500">See who's booked an appointment, upcoming or past.</p>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ error }}</p>
    </div>

    <div class="panel p-4 mb-6 space-y-4">
      <div class="flex gap-2">
        <button
          @click="setUpcoming(true)"
          class="btn-sm px-4 py-1.5 rounded-xl"
          :class="upcoming ? 'btn-primary' : 'btn-secondary'"
        >
          Upcoming
        </button>
        <button
          @click="setUpcoming(false)"
          class="btn-sm px-4 py-1.5 rounded-xl"
          :class="!upcoming ? 'btn-primary' : 'btn-secondary'"
        >
          Past / History
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">From</span>
          <input v-model="filters.date_from" type="date" class="field" />
        </label>
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">To</span>
          <input v-model="filters.date_to" type="date" class="field" />
        </label>
        <div class="flex items-end gap-2">
          <button @click="applyFilters" class="btn-primary btn-md">Search</button>
          <button @click="clearFilters" class="btn-secondary btn-md">Clear</button>
        </div>
      </div>
    </div>

    <div class="panel overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-100">
        <thead class="bg-bsu-surface">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Reference</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Student ID</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Service</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Date</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Time</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Document</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="appt in queueStore.appointmentsList" :key="appt.id" class="table-row-hover">
            <td class="px-6 py-4 text-sm font-medium text-bsu-ink">{{ appt.reference_code }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ appt.student_number }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ appt.student_name }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ appt.queue_name }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ formatDate(appt.appointment_date) }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ formatTime(appt.slot_start_time) }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ appt.document_type || '—' }}</td>
            <td class="px-6 py-4 text-sm"><StatusBadge :status="appt.status" /></td>
          </tr>

          <tr v-if="!loading && queueStore.appointmentsList.length === 0">
            <td colspan="8" class="px-6 py-8 text-center text-gray-500">
              {{ upcoming ? 'No upcoming appointments.' : 'No past appointments found.' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="queueStore.appointmentsTotal > 0" class="mt-4 flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-gray-500">
        Showing {{ rangeStart }}-{{ rangeEnd }} of {{ queueStore.appointmentsTotal }} appointments
      </p>
      <nav class="flex items-center gap-1">
        <button @click="goToPage(page - 1)" :disabled="page === 1" class="btn-secondary btn-sm">‹ Prev</button>
        <button @click="goToPage(page + 1)" :disabled="page === totalPages" class="btn-secondary btn-sm">Next ›</button>
      </nav>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'

const queueStore = useQueueStore()
const loading = computed(() => queueStore.loading)
const error = ref('')

const upcoming = ref(true)
const filters = ref({ date_from: '', date_to: '' })

const PAGE_SIZE = 25
const page = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(queueStore.appointmentsTotal / PAGE_SIZE)))
const rangeStart = computed(() => (queueStore.appointmentsTotal === 0 ? 0 : (page.value - 1) * PAGE_SIZE + 1))
const rangeEnd = computed(() => Math.min(page.value * PAGE_SIZE, queueStore.appointmentsTotal))

function formatDate(value) {
  return format(new Date(value + 'T00:00:00'), 'MMM d, yyyy')
}

function formatTime(t) {
  const [h, m] = t.split(':').map(Number)
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 === 0 ? 12 : h % 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

const load = async () => {
  error.value = ''
  try {
    await queueStore.fetchAppointmentsList({
      upcoming: upcoming.value,
      dateFrom: filters.value.date_from || null,
      dateTo: filters.value.date_to || null,
      skip: (page.value - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
    })
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load appointments'
  }
}

const setUpcoming = (value) => {
  if (upcoming.value === value) return
  upcoming.value = value
  page.value = 1
  load()
}

const applyFilters = () => {
  page.value = 1
  load()
}

const clearFilters = () => {
  filters.value = { date_from: '', date_to: '' }
  page.value = 1
  load()
}

const goToPage = (targetPage) => {
  if (targetPage < 1 || targetPage > totalPages.value || targetPage === page.value) return
  page.value = targetPage
  load()
}

onMounted(load)
</script>
