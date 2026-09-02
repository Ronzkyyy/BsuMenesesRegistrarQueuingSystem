<template>
  <div>
    <div class="mb-6">
      <h2 class="text-3xl font-bold text-bsu-ink">Transaction History &amp; Audit</h2>
      <p class="mt-2 text-gray-500">
        Past tickets and appointments, and a monthly view of when the registrar is busiest.
      </p>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ error }}</p>
    </div>

    <!-- Calendar + busiest hours -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
      <div class="panel overflow-hidden lg:col-span-2">
        <div class="panel-header flex items-center justify-between">
          <h3 class="text-lg font-semibold text-bsu-ink">Peak Transactions</h3>
          <div class="flex items-center gap-2">
            <button class="btn btn-sm btn-secondary" @click="shiftMonth(-1)">&larr;</button>
            <span class="text-sm font-medium text-bsu-ink w-32 text-center">
              {{ monthLabel }}
            </span>
            <button class="btn btn-sm btn-secondary" @click="shiftMonth(1)">&rarr;</button>
          </div>
        </div>
        <div class="p-6">
          <div class="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-gray-400 mb-1">
            <div v-for="d in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']" :key="d">{{ d }}</div>
          </div>
          <div class="grid grid-cols-7 gap-1">
            <div v-for="n in leadingBlanks" :key="'b' + n"></div>
            <button
              v-for="cell in dayCells"
              :key="cell.iso"
              type="button"
              @click="selectDay(cell.iso)"
              class="aspect-square rounded-lg border text-left p-1.5 transition-colors"
              :class="[
                cell.intensity,
                selectedDay === cell.iso ? 'ring-2 ring-bsu-primary' : 'border-transparent',
                cell.isPeak ? 'outline outline-2 outline-bsu-gold' : '',
              ]"
            >
              <span class="text-[11px] font-semibold" :class="cell.count ? 'text-white' : 'text-gray-500'">
                {{ cell.day }}
              </span>
              <span v-if="cell.count" class="block text-[11px] font-bold text-white">{{ cell.count }}</span>
            </button>
          </div>
          <p class="mt-3 text-xs text-gray-500">
            <span v-if="calendar?.peak_day">
              Busiest day: <span class="font-semibold text-bsu-ink">{{ formatIso(calendar.peak_day) }}</span>
              ({{ calendar.peak_count }} transactions).
            </span>
            <span v-else>No transactions this month.</span>
            Click a day to filter the list below.
          </p>
        </div>
      </div>

      <div class="panel overflow-hidden">
        <div class="panel-header">
          <h3 class="text-lg font-semibold text-bsu-ink">Busiest Hours</h3>
        </div>
        <div class="p-6">
          <div v-if="hasHourData" class="h-64">
            <Bar :data="hourChartData" :options="hourChartOptions" />
          </div>
          <p v-else class="text-center text-gray-500 py-8">No data this month</p>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="panel p-4 mb-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">From</span>
          <input v-model="filters.date_from" type="date" class="field" />
        </label>
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">To</span>
          <input v-model="filters.date_to" type="date" class="field" />
        </label>
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">Queue</span>
          <select v-model="filters.queue_id" class="field">
            <option :value="null">All queues</option>
            <option v-for="q in queueStore.queues" :key="q.id" :value="q.id">{{ q.name }}</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">Student number</span>
          <input v-model="filters.student_number" maxlength="10" inputmode="numeric" placeholder="10 digits" class="field" />
        </label>
      </div>

      <div class="flex flex-wrap gap-4 mt-3 text-sm">
        <span class="text-gray-600">Type:</span>
        <label class="flex items-center gap-1">
          <input type="checkbox" value="ticket" v-model="filters.kind" /> Tickets
        </label>
        <label class="flex items-center gap-1">
          <input type="checkbox" value="appointment" v-model="filters.kind" /> Appointments
        </label>
      </div>

      <div class="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-sm">
        <span class="text-gray-600">Status:</span>
        <label v-for="s in ALL_STATUSES" :key="s" class="flex items-center gap-1">
          <input type="checkbox" :value="s" v-model="filters.status" /> {{ s.replace('_', ' ') }}
        </label>
        <span class="text-gray-400">(none checked = attended only)</span>
      </div>

      <div class="flex gap-3 mt-4">
        <button class="btn btn-primary btn-sm" @click="applyFilters">Apply</button>
        <button class="btn btn-secondary btn-sm" @click="resetFilters">Reset</button>
        <button class="btn btn-secondary btn-sm ml-auto" @click="downloadCsv">Download CSV</button>
      </div>
    </div>

    <!-- Table -->
    <div class="panel overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-bsu-surface text-gray-500 text-xs uppercase tracking-wide">
            <tr>
              <th class="px-4 py-3 text-left">Reference</th>
              <th class="px-4 py-3 text-left">Type</th>
              <th class="px-4 py-3 text-left">Student</th>
              <th class="px-4 py-3 text-left">Service</th>
              <th class="px-4 py-3 text-left">Queue</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Priority</th>
              <th class="px-4 py-3 text-left">Created</th>
              <th class="px-4 py-3 text-left">Occurred</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="row in history.items" :key="row.kind + '-' + row.id">
              <td class="px-4 py-3 font-medium text-bsu-ink">{{ row.reference }}</td>
              <td class="px-4 py-3 capitalize">{{ row.kind }}</td>
              <td class="px-4 py-3">
                <div class="text-bsu-ink">{{ row.student_name }}</div>
                <div class="text-xs text-gray-400">{{ row.student_number }}</div>
              </td>
              <td class="px-4 py-3">{{ row.service }}</td>
              <td class="px-4 py-3">{{ row.queue_name }}</td>
              <td class="px-4 py-3"><StatusBadge :status="row.status" /></td>
              <td class="px-4 py-3 capitalize">{{ row.priority || '—' }}</td>
              <td class="px-4 py-3 text-gray-500">{{ formatDateTime(row.created_at) }}</td>
              <td class="px-4 py-3 text-gray-500">{{ row.occurred_at ? formatDateTime(row.occurred_at) : '—' }}</td>
            </tr>
            <tr v-if="!history.items.length">
              <td colspan="9" class="px-4 py-10 text-center text-gray-500">No transactions match these filters.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
        <span>
          <template v-if="history.total">
            Showing {{ history.skip + 1 }}–{{ history.skip + history.items.length }} of {{ history.total }}
          </template>
          <template v-else>No results</template>
        </span>
        <div class="flex gap-2">
          <button class="btn btn-sm btn-secondary" :disabled="history.skip === 0" @click="changePage(-1)">Prev</button>
          <button class="btn btn-sm btn-secondary" :disabled="history.skip + history.limit >= history.total" @click="changePage(1)">Next</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  addMonths, eachDayOfInterval, endOfMonth, format, getDay, startOfMonth, subMonths,
} from 'date-fns'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, Legend,
} from 'chart.js'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const queueStore = useQueueStore()
const error = ref('')

const ALL_STATUSES = [
  'waiting', 'serving', 'completed', 'cancelled', 'no_show',
  'booked', 'checked_in', 'expired',
]

const PAGE_SIZE = 50

const today = new Date()
const isoOf = (d) => format(d, 'yyyy-MM-dd')

const filters = reactive({
  date_from: isoOf(subMonths(today, 1)),
  date_to: isoOf(today),
  kind: ['ticket', 'appointment'],
  status: [],
  queue_id: null,
  student_number: '',
})

const calendarMonth = ref(startOfMonth(today))
const selectedDay = ref(null)

const history = computed(() => queueStore.transactionHistory)
const calendar = computed(() => queueStore.transactionCalendar)

const monthLabel = computed(() => format(calendarMonth.value, 'MMMM yyyy'))
const leadingBlanks = computed(() => getDay(startOfMonth(calendarMonth.value)))

const dayCells = computed(() => {
  const days = eachDayOfInterval({
    start: startOfMonth(calendarMonth.value),
    end: endOfMonth(calendarMonth.value),
  })
  const byIso = {}
  let max = 0
  for (const d of calendar.value?.days ?? []) {
    byIso[d.date] = d.total
    if (d.total > max) max = d.total
  }
  const peakIso = calendar.value?.peak_day ?? null
  return days.map((d) => {
    const iso = isoOf(d)
    const count = byIso[iso] ?? 0
    return {
      iso,
      day: format(d, 'd'),
      count,
      isPeak: !!count && iso === peakIso,
      intensity: intensityClass(count, max),
    }
  })
})

function intensityClass(count, max) {
  if (!count) return 'bg-gray-50'
  const ratio = max ? count / max : 0
  if (ratio > 0.8) return 'bg-bsu-primary'
  if (ratio > 0.6) return 'bg-bsu-primary/80'
  if (ratio > 0.4) return 'bg-bsu-primary/60'
  if (ratio > 0.2) return 'bg-bsu-primary/40'
  return 'bg-bsu-primary/25'
}

const hasHourData = computed(() => (calendar.value?.busiest_hours ?? []).some((n) => n > 0))
const hourChartData = computed(() => ({
  labels: Array.from({ length: 24 }, (_, h) => `${h}`),
  datasets: [{
    label: 'Transactions',
    data: calendar.value?.busiest_hours ?? [],
    backgroundColor: '#E85D8E',
    borderRadius: 4,
  }],
}))
const hourChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#F1F1F1' } },
    x: { grid: { display: false } },
  },
}

function buildParams(extra = {}) {
  const p = {
    date_from: filters.date_from,
    date_to: filters.date_to,
    kind: filters.kind,
    ...extra,
  }
  if (filters.status.length) p.status = filters.status
  if (filters.queue_id) p.queue_id = filters.queue_id
  if (/^\d{10}$/.test(filters.student_number)) p.student_number = filters.student_number
  return p
}

async function loadHistory(skip = 0) {
  error.value = ''
  try {
    await queueStore.fetchTransactionHistory(buildParams({ skip, limit: PAGE_SIZE }))
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load transaction history.'
  }
}

async function loadCalendar() {
  try {
    await queueStore.fetchTransactionCalendar(
      calendarMonth.value.getFullYear(), calendarMonth.value.getMonth() + 1,
    )
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load the calendar.'
  }
}

function shiftMonth(delta) {
  calendarMonth.value = delta < 0
    ? subMonths(calendarMonth.value, 1)
    : addMonths(calendarMonth.value, 1)
  loadCalendar()
}

function selectDay(iso) {
  selectedDay.value = iso
  filters.date_from = iso
  filters.date_to = iso
  loadHistory(0)
}

function applyFilters() {
  selectedDay.value = null
  loadHistory(0)
}

function resetFilters() {
  filters.date_from = isoOf(subMonths(today, 1))
  filters.date_to = isoOf(today)
  filters.kind = ['ticket', 'appointment']
  filters.status = []
  filters.queue_id = null
  filters.student_number = ''
  selectedDay.value = null
  loadHistory(0)
}

function changePage(dir) {
  const next = history.value.skip + dir * history.value.limit
  if (next < 0) return
  loadHistory(next)
}

function downloadCsv() {
  const usp = new URLSearchParams()
  usp.set('date_from', filters.date_from)
  usp.set('date_to', filters.date_to)
  for (const k of filters.kind) usp.append('kind', k)
  for (const s of filters.status) usp.append('status', s)
  if (filters.queue_id) usp.set('queue_id', filters.queue_id)
  if (/^\d{10}$/.test(filters.student_number)) usp.set('student_number', filters.student_number)
  window.open(`/api/reports/transactions.csv?${usp.toString()}`, '_blank')
}

function formatDateTime(value) {
  return format(new Date(value), 'MMM d, yyyy • h:mm a')
}
function formatIso(value) {
  return format(new Date(value + 'T00:00:00'), 'MMM d, yyyy')
}

onMounted(async () => {
  if (!queueStore.queues.length) {
    queueStore.fetchQueues().catch(() => {})
  }
  await Promise.all([loadCalendar(), loadHistory(0)])
})
</script>
