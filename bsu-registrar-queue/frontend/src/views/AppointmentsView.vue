<template>
  <div class="relative min-h-screen bg-bsu-surface flex items-center justify-center px-4 py-10">
    <div class="relative z-10 w-full max-w-2xl bg-white rounded-2xl shadow-soft-lg border border-gray-100 overflow-hidden">
      <div class="p-6 sm:p-8">
        <div class="flex flex-col items-center text-center mb-6">
          <h1 class="text-2xl font-bold text-bsu-ink">Book an Appointment</h1>
          <p class="mt-1 text-sm text-gray-500">Reserve a time slot and get a QR code to check in with at the registrar.</p>
        </div>

        <div class="flex justify-center gap-2 mb-6">
          <button
            @click="mode = 'book'"
            class="btn-sm px-4 py-1.5 rounded-xl"
            :class="mode === 'book' ? 'btn-primary' : 'btn-secondary'"
          >
            New Appointment
          </button>
          <button
            @click="mode = 'lookup'"
            class="btn-sm px-4 py-1.5 rounded-xl"
            :class="mode === 'lookup' ? 'btn-primary' : 'btn-secondary'"
          >
            View / Cancel Existing
          </button>
        </div>

        <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- ===================== BOOKING FLOW ===================== -->
        <template v-if="mode === 'book'">
          <div v-if="!bookedAppointment">
            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Student ID</label>
                <div class="flex gap-2">
                  <input v-model="studentIdInput" type="text" class="field" placeholder="e.g. 2021000001" />
                  <button @click="findStudent" :disabled="loading" class="btn-primary btn-md whitespace-nowrap">Find</button>
                </div>
                <p v-if="student" class="text-sm text-green-700 mt-1.5">{{ student.first_name }} {{ student.last_name }} found</p>
              </div>

              <div v-if="student">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Service</label>
                <select v-model="selectedQueueId" @change="onQueueChange" class="field">
                  <option :value="null">Select a service</option>
                  <option v-for="q in bookableQueues" :key="q.id" :value="q.id">{{ q.name }}</option>
                </select>
                <p v-if="bookableQueues.length === 0" class="text-sm text-gray-500 mt-1.5">
                  No services currently accept appointment bookings.
                </p>
              </div>

              <div v-if="selectedQueueId">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Date</label>
                <input v-model="selectedDate" @change="loadAvailability" type="date" :min="minDate" :max="maxDate" class="field" />
                <p class="text-xs text-gray-500 mt-1.5">
                  Same-day booking is not available - the earliest date you can choose is tomorrow.
                </p>
              </div>

              <div v-if="hourlySlots.length > 0">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Time</label>
                <div class="grid grid-cols-3 gap-2">
                  <button
                    v-for="slot in hourlySlots"
                    :key="slot.slot_start_time"
                    type="button"
                    @click="selectedSlot = slot"
                    :disabled="slot.is_full"
                    class="px-3 py-2 rounded-xl text-sm border"
                    :class="[
                      slot.is_full ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'hover:border-bsu-primary',
                      selectedSlot === slot ? 'border-bsu-primary bg-bsu-primary/10 font-semibold' : 'border-gray-200',
                    ]"
                  >
                    {{ formatTime(slot.slot_start_time) }}
                    <span v-if="slot.is_full" class="block text-xs">Full</span>
                  </button>
                </div>
              </div>
              <div v-else-if="selectedDate && !checkingAvailability" class="text-sm text-gray-500">No bookable slots for this date.</div>

              <div v-if="selectedSlot && isDocumentRequest">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Document Type</label>
                <select v-model="selectedDocumentType" class="field">
                  <option value="" disabled>Select a document type</option>
                  <option v-for="dt in DOCUMENT_TYPES" :key="dt.value" :value="dt.value">{{ dt.label }}</option>
                </select>
              </div>
              <div v-else-if="selectedSlot">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Purpose (optional)</label>
                <input v-model="purpose" type="text" class="field" placeholder="Briefly describe your purpose" />
              </div>

              <button
                v-if="selectedSlot"
                @click="submitBooking"
                :disabled="loading || (isDocumentRequest && !selectedDocumentType)"
                class="btn-primary btn-md w-full py-2.5"
              >
                Confirm Booking
              </button>
            </div>
          </div>

          <!-- Booking confirmation + QR -->
          <div v-else class="text-center">
            <h3 class="text-lg font-bold text-bsu-ink mb-1">Appointment Booked</h3>
            <p class="text-sm text-gray-500 mb-4">{{ bookedAppointment.queue_name }} - {{ bookedAppointment.appointment_date }} at {{ formatTime(bookedAppointment.slot_start_time) }}</p>

            <img v-if="qrDataUrl" :src="qrDataUrl" alt="Appointment QR code" class="mx-auto mb-3 rounded-xl border border-gray-200" />
            <p class="text-2xl font-bold text-bsu-ink tracking-wide mb-1">{{ bookedAppointment.reference_code }}</p>
            <p class="text-xs text-gray-500 mb-4">Show this QR code (or the code above) at the registrar counter.</p>

            <a
              v-if="qrDataUrl"
              :href="qrDataUrl"
              download="appointment-qr.png"
              class="btn-secondary btn-md inline-block mb-3"
            >
              Download QR Code
            </a>
            <p class="text-xs text-gray-400">Keep your Student ID ({{ student.student_id }}) and reference code to view or cancel this booking later.</p>
          </div>
        </template>

        <!-- ===================== LOOKUP / CANCEL FLOW ===================== -->
        <template v-else>
          <div v-if="!myAppointment" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Student ID</label>
              <input v-model="lookupStudentId" type="text" class="field" placeholder="e.g. 2021000001" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Reference Code</label>
              <input v-model="lookupReferenceCode" type="text" class="field uppercase" placeholder="APT-000482" />
            </div>
            <button @click="doLookup" :disabled="loading" class="btn-primary btn-md w-full py-2.5">Find Appointment</button>
          </div>

          <div v-else class="text-center">
            <h3 class="text-lg font-bold text-bsu-ink mb-1">{{ myAppointment.queue_name }}</h3>
            <p class="text-sm text-gray-500 mb-3">{{ myAppointment.appointment_date }} at {{ formatTime(myAppointment.slot_start_time) }}</p>

            <!-- Expired: an outcome to explain, not an error to report -->
            <div v-if="isExpired" class="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-xl text-left">
              <p class="text-sm font-semibold text-amber-900">This appointment has expired</p>
              <p class="text-sm text-amber-800 mt-1">
                The {{ formatTime(myAppointment.slot_start_time) }} slot on {{ myAppointment.appointment_date }}
                has already passed and the appointment was not checked in.
              </p>
              <p class="text-sm text-amber-800 mt-2">
                Book a new appointment below, or take a walk-in ticket at the registrar.
              </p>
            </div>

            <p v-else class="text-sm mb-4">
              Status:
              <span class="font-semibold capitalize">{{ statusLabel }}</span>
            </p>

            <button
              v-if="myAppointment.status === 'booked' && !isExpired"
              @click="doCancel"
              :disabled="loading"
              class="btn-danger-solid btn-md w-full py-2.5"
            >
              Cancel Appointment
            </button>
            <button v-if="isExpired" @click="startNewBooking" class="btn-primary btn-md w-full py-2.5">
              Book a New Appointment
            </button>
            <button @click="myAppointment = null" class="btn-secondary btn-md w-full py-2.5 mt-3">Back</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import QRCode from 'qrcode'
import { useQueueStore } from '@/stores/queue'
import { DOCUMENT_TYPES } from '@/services/documentTypes'

const queueStore = useQueueStore()
const loading = computed(() => queueStore.loading)
const error = ref('')

const mode = ref('book')

// --- booking flow state ---
const studentIdInput = ref('')
const student = ref(null)
const bookableQueues = ref([])
const selectedQueueId = ref(null)
const selectedDate = ref('')
const slots = ref([])
const selectedSlot = ref(null)
const checkingAvailability = ref(false)
const purpose = ref('')
const selectedDocumentType = ref('')
const bookedAppointment = ref(null)
const qrDataUrl = ref('')

// Local calendar date, not toISOString() - the campus is UTC+8, so a UTC
// date string names the previous day for the whole first 8 hours of business.
const toLocalISODate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

const addDays = (d, n) => {
  const out = new Date(d)
  out.setDate(out.getDate() + n)
  return out
}

const today = new Date()
// Same-day booking is not offered, so the picker opens at tomorrow.
const minDate = toLocalISODate(addDays(today, 1))

const selectedQueue = computed(() => bookableQueues.value.find((q) => q.id === selectedQueueId.value))
const isDocumentRequest = computed(() => selectedQueue.value?.queue_type === 'document_request')
const hourlySlots = computed(() => slots.value.filter((slot) => slot.slot_start_time.endsWith(':00:00')))

const maxDate = computed(() => {
  const windowDays = selectedQueue.value?.booking_window_days ?? 14
  return toLocalISODate(addDays(today, windowDays))
})

const formatTime = (t) => {
  const [h, m] = t.split(':').map(Number)
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 === 0 ? 12 : h % 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

const findStudent = async () => {
  error.value = ''
  try {
    student.value = await queueStore.searchStudent(studentIdInput.value.trim())
    const active = await queueStore.fetchActiveQueues()
    bookableQueues.value = active.filter((q) => q.booking_enabled)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Student not found'
    student.value = null
  }
}

const onQueueChange = () => {
  selectedDate.value = ''
  slots.value = []
  selectedSlot.value = null
  purpose.value = ''
  selectedDocumentType.value = ''
}

const loadAvailability = async () => {
  selectedSlot.value = null
  if (!selectedQueueId.value || !selectedDate.value) return
  error.value = ''
  checkingAvailability.value = true
  try {
    slots.value = await queueStore.fetchAppointmentAvailability(selectedQueueId.value, selectedDate.value)
    selectedSlot.value = hourlySlots.value.find((slot) => !slot.is_full) || null
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load available slots'
    slots.value = []
  } finally {
    checkingAvailability.value = false
  }
}

const submitBooking = async () => {
  error.value = ''
  try {
    const result = await queueStore.bookAppointment({
      student_id: student.value.id,
      queue_id: selectedQueueId.value,
      appointment_date: selectedDate.value,
      slot_start_time: selectedSlot.value.slot_start_time,
      purpose: isDocumentRequest.value ? selectedDocumentType.value : purpose.value || null,
    })
    bookedAppointment.value = result
    qrDataUrl.value = await QRCode.toDataURL(result.qr_token, { width: 240, margin: 2 })
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to book appointment'
  }
}

// --- lookup/cancel flow state ---
const lookupStudentId = ref('')
const lookupReferenceCode = ref('')
const myAppointment = ref(null)

// An appointment is expired once the backend has flipped it to EXPIRED, or -
// before the periodic expiry task has run - once its slot end has passed while
// still BOOKED. Either way it is a state to explain, not a failure to report.
const isExpired = computed(() => {
  const appt = myAppointment.value
  if (!appt) return false
  if (appt.status === 'expired') return true
  if (appt.status !== 'booked') return false
  return new Date(`${appt.appointment_date}T${appt.slot_end_time}`) < new Date()
})

const statusLabel = computed(() => myAppointment.value?.status.replace('_', ' ') ?? '')

const startNewBooking = () => {
  myAppointment.value = null
  error.value = ''
  mode.value = 'book'
}

const doLookup = async () => {
  error.value = ''
  try {
    myAppointment.value = await queueStore.lookupAppointment(
      lookupStudentId.value.trim(),
      lookupReferenceCode.value.trim().toUpperCase()
    )
  } catch (err) {
    error.value = err.response?.data?.detail || 'Appointment not found'
  }
}

const doCancel = async () => {
  error.value = ''
  try {
    myAppointment.value = await queueStore.cancelAppointment(myAppointment.value.id, lookupStudentId.value.trim())
  } catch (err) {
    // The slot can lapse between the lookup and the click - the backend refuses
    // to cancel an EXPIRED booking. Show the expired state rather than the 400.
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.includes('expired')) {
      myAppointment.value = { ...myAppointment.value, status: 'expired' }
      return
    }
    error.value = detail || 'Failed to cancel appointment'
  }
}
</script>
