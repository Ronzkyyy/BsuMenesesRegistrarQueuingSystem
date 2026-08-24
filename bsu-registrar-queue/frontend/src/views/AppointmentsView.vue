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
              </div>

              <div v-if="selectedSlot" class="text-sm text-gray-600">
                Assigned time: <span class="font-semibold text-bsu-ink">{{ formatTime(selectedSlot.slot_start_time) }}</span>
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
            <p class="text-sm mb-4">
              Status:
              <span class="font-semibold capitalize">{{ myAppointment.status.replace('_', ' ') }}</span>
            </p>

            <button
              v-if="myAppointment.status === 'booked'"
              @click="doCancel"
              :disabled="loading"
              class="btn-danger-solid btn-md w-full py-2.5"
            >
              Cancel Appointment
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

const today = new Date()
const minDate = today.toISOString().slice(0, 10)

const selectedQueue = computed(() => bookableQueues.value.find((q) => q.id === selectedQueueId.value))
const isDocumentRequest = computed(() => selectedQueue.value?.queue_type === 'document_request')

const maxDate = computed(() => {
  const windowDays = selectedQueue.value?.booking_window_days ?? 14
  const max = new Date(today)
  max.setDate(max.getDate() + windowDays)
  return max.toISOString().slice(0, 10)
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
    selectedSlot.value = slots.value.find((slot) => !slot.is_full) || null
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
    error.value = err.response?.data?.detail || 'Failed to cancel appointment'
  }
}
</script>
