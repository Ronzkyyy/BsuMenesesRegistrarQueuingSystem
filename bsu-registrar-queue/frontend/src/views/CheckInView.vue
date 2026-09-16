<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-bsu-ink">Appointment Check-In</h2>
      <p class="mt-2 text-gray-500">Scan a student's QR code or look them up manually to create their queue ticket</p>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ error }}</p>
    </div>

    <div v-if="expiredAppointment" class="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-6">
      <p class="text-sm font-semibold text-amber-900">Appointment expired</p>
      <p class="text-sm text-amber-800 mt-1">
        {{ expiredAppointment.reference_code }} - the
        {{ formatTime(expiredAppointment.slot_start_time) }} slot on
        {{ expiredAppointment.appointment_date }} has already passed.
      </p>
      <p class="text-sm text-amber-800 mt-1">Issue a walk-in ticket for this student instead.</p>
      <div class="flex gap-3 mt-3">
        <button @click="expiredAppointment = null" class="btn-secondary btn-sm">Dismiss</button>
        <button @click="removeExpiredAppointment(expiredAppointment)" class="btn-danger-solid btn-sm">Delete</button>
      </div>
    </div>

    <div v-if="pendingWindowConfirm" class="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-6">
      <p class="text-sm text-amber-800 mb-3">{{ pendingWindowConfirm.message }}</p>
      <div class="flex gap-3">
        <button @click="confirmOverride" class="btn-warning btn-sm">Check In Anyway</button>
        <button @click="pendingWindowConfirm = null" class="btn-secondary btn-sm">Cancel</button>
      </div>
    </div>

    <div v-if="lastTicket" class="bg-green-50 border border-green-200 rounded-2xl p-6 mb-6 text-center">
      <p class="text-sm text-green-700 mb-1">Checked in - ticket created</p>
      <p class="text-4xl font-extrabold text-bsu-ink">{{ lastTicket.ticket_code }}</p>
      <p class="text-sm text-gray-500 mt-1">{{ lastTicket.queue_name }}</p>
    </div>

    <div class="panel mb-6">
      <div class="panel-header flex items-center justify-between">
        <h3 class="text-xl font-bold text-bsu-ink">Scan QR Code</h3>
        <button @click="scanning ? stopScanning() : startScanning()" class="btn-primary btn-sm">
          {{ scanning ? 'Stop Camera' : 'Start Camera' }}
        </button>
      </div>
      <div class="p-6">
        <video ref="videoEl" class="w-full max-w-sm mx-auto rounded-xl bg-black" style="aspect-ratio: 1"></video>
        <p v-if="!scanning" class="text-center text-sm text-gray-500 mt-3">Click "Start Camera" to scan a student's QR code.</p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <h3 class="text-xl font-bold text-bsu-ink">Manual Lookup</h3>
      </div>
      <div class="p-6">
        <div class="flex gap-2 mb-4">
          <input
            v-model="manualQuery"
            @keyup.enter="doManualSearch"
            type="text"
            class="field"
            placeholder="Student ID or reference code (e.g. APT-000482)"
          />
          <button @click="doManualSearch" :disabled="loading" class="btn-primary btn-md whitespace-nowrap">Search</button>
        </div>

        <div v-if="searchResults.length > 0" class="space-y-2">
          <div
            v-for="appt in searchResults"
            :key="appt.id"
            class="flex items-center justify-between px-4 py-3 rounded-xl border border-gray-200"
          >
            <div>
              <p class="font-medium text-bsu-ink">
                {{ appt.reference_code }} - {{ appt.queue_name }}
                <span v-if="isOverdue(appt)" class="ml-2 text-xs px-2 py-0.5 rounded-xl bg-amber-100 text-amber-800">Expired</span>
              </p>
              <p class="text-sm text-gray-500">{{ appt.appointment_date }} at {{ formatTime(appt.slot_start_time) }}</p>
            </div>
            <button
              v-if="isOverdue(appt)"
              @click="removeExpiredAppointment(appt)"
              class="btn-danger-solid btn-sm"
            >
              Delete
            </button>
            <button v-else @click="checkIn({ referenceCode: appt.reference_code })" :disabled="loading" class="btn-success-solid btn-sm">
              Check In
            </button>
          </div>
        </div>
        <p v-else-if="searchedOnce" class="text-sm text-gray-500">No matching booked appointments found.</p>
      </div>
    </div>

    <ConfirmDialog
      v-model="confirmDialog.open"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      confirm-label="Yes, Delete"
      variant="danger"
      :loading="confirmLoading"
      @confirm="handleConfirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, onUnmounted, computed } from 'vue'
import QrScanner from 'qr-scanner'
import { useQueueStore } from '@/stores/queue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const queueStore = useQueueStore()
const loading = computed(() => queueStore.loading)
const error = ref('')

const lastTicket = ref(null)
const pendingWindowConfirm = ref(null)
const expiredAppointment = ref(null)

const formatTime = (t) => {
  const [h, m] = t.split(':').map(Number)
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 === 0 ? 12 : h % 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

// An appointment counts as overdue once it's already flipped to EXPIRED, or -
// before the periodic expiry task has caught up - once its slot end has
// passed the same buffer_minutes cutoff appointment_service.py uses to flip
// it. Matches AppointmentService._is_overdue on the backend.
const EXPIRE_BUFFER_MINUTES = 60
const isOverdue = (appt) => {
  if (appt.status === 'expired') return true
  if (appt.status !== 'booked') return false
  const slotEnd = new Date(`${appt.appointment_date}T${appt.slot_end_time}`)
  return slotEnd.getTime() < Date.now() - EXPIRE_BUFFER_MINUTES * 60000
}

// --- delete (soft-cancel) an overdue appointment ---
const confirmDialog = ref({ open: false, title: '', message: '' })
const confirmLoading = ref(false)
let appointmentToDelete = null

const removeExpiredAppointment = (appt) => {
  appointmentToDelete = appt
  confirmDialog.value = {
    open: true,
    title: 'Delete this expired appointment?',
    message: `${appt.reference_code} on ${appt.appointment_date} has already expired. This cannot be undone.`,
  }
}

const handleConfirmDelete = async () => {
  if (!appointmentToDelete) return
  confirmLoading.value = true
  try {
    await queueStore.staffCancelAppointment(appointmentToDelete.id)
    searchResults.value = searchResults.value.filter((a) => a.id !== appointmentToDelete.id)
    if (expiredAppointment.value?.id === appointmentToDelete.id) {
      expiredAppointment.value = null
    }
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to delete appointment'
  } finally {
    confirmLoading.value = false
    confirmDialog.value.open = false
    appointmentToDelete = null
  }
}

// --- camera scanning ---
const videoEl = ref(null)
const scanning = ref(false)
let scanner = null

const startScanning = async () => {
  if (!videoEl.value) return
  scanner = new QrScanner(
    videoEl.value,
    (result) => {
      stopScanning()
      checkIn({ token: result.data })
    },
    { highlightScanRegion: true, highlightCodeOutline: true }
  )
  try {
    await scanner.start()
    scanning.value = true
  } catch (err) {
    scanner?.destroy()
    scanner = null
    scanning.value = false
    error.value = 'Could not start the camera. Check camera permissions or use manual lookup below.'
  }
}

const stopScanning = () => {
  scanner?.stop()
  scanner?.destroy()
  scanner = null
  scanning.value = false
}

onUnmounted(() => stopScanning())

// --- manual lookup ---
const manualQuery = ref('')
const searchResults = ref([])
const searchedOnce = ref(false)

const doManualSearch = async () => {
  if (!manualQuery.value.trim()) return
  error.value = ''
  searchedOnce.value = true
  try {
    searchResults.value = await queueStore.searchAppointments(manualQuery.value.trim())
  } catch (err) {
    error.value = err.response?.data?.detail || 'Search failed'
    searchResults.value = []
  }
}

// --- check-in ---
const checkIn = async ({ token = null, referenceCode = null, force = false }) => {
  error.value = ''
  pendingWindowConfirm.value = null
  expiredAppointment.value = null
  try {
    const ticket = await queueStore.checkInAppointment({ token, referenceCode, force })
    lastTicket.value = ticket
    searchResults.value = searchResults.value.filter((a) => a.reference_code !== referenceCode)
    manualQuery.value = ''
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409) {
      pendingWindowConfirm.value = {
        message: detail,
        retry: { token, referenceCode },
      }
    } else if (err.response?.status === 410) {
      // 410 carries the expired booking's own details - show it as a state,
      // not as a check-in failure, and drop the now-dead row so staff can't
      // retry it.
      expiredAppointment.value = detail
      searchResults.value = searchResults.value.filter(
        (a) => a.reference_code !== detail.reference_code
      )
    } else {
      error.value = (typeof detail === 'string' ? detail : detail?.message) || 'Check-in failed'
    }
  }
}

const confirmOverride = () => {
  const retry = pendingWindowConfirm.value.retry
  checkIn({ ...retry, force: true })
}
</script>
