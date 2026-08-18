<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-bsu-ink">Queue Management</h2>
      <p class="mt-2 text-gray-500">Manage queues and serve tickets</p>
    </div>

    <div v-if="dashboardError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ dashboardError }}</p>
    </div>

    <div class="panel mb-6">
      <div class="panel-header">
        <h3 class="text-xl font-bold text-bsu-ink">Queue Management</h3>
      </div>
      <div class="p-6">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div
            v-for="{ service, queue } in serviceCards"
            :key="service.key"
            class="border border-gray-200 rounded-2xl p-4"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-3">
                <div class="w-11 h-11 rounded-xl bg-bsu-primary/10 flex items-center justify-center flex-shrink-0">
                  <component :is="service.icon" class="w-6 h-6 text-bsu-primary" />
                </div>
                <div>
                  <h4 class="font-medium text-bsu-ink">{{ service.label }}</h4>
                  <p class="text-sm text-gray-500">Queue: {{ formatQueueType(service.queueType) }}</p>
                </div>
              </div>
              <StatusBadge v-if="queue" :status="queue.status" />
            </div>

            <template v-if="queue">
              <div class="text-sm text-gray-500 mb-3">
                <p>Capacity: {{ queue.max_capacity }} | Slot: {{ queue.slot_duration_minutes }} min</p>
                <p class="mt-1">
                  Appointment booking:
                  <span :class="queue.booking_enabled ? 'text-green-700 font-medium' : 'text-gray-400'">
                    {{ queue.booking_enabled ? 'Enabled' : 'Disabled' }}
                  </span>
                </p>
              </div>

              <div class="flex space-x-2 mb-2">
                <button
                  @click="openBookingSettings(queue)"
                  class="btn-secondary btn-sm flex-1"
                >
                  Manage Booking
                </button>
              </div>

              <div class="flex space-x-2">
                <button
                  v-if="queue.status === 'active'"
                  @click="pauseQueue(queue.id)"
                  :disabled="loading"
                  class="btn-warning btn-sm flex-1"
                >
                  Pause
                </button>
                <button
                  v-else-if="queue.status === 'paused'"
                  @click="resumeQueue(queue.id)"
                  :disabled="loading"
                  class="btn-success btn-sm flex-1"
                >
                  Resume
                </button>
                <button
                  v-if="queue.status !== 'closed'"
                  @click="closeQueue(queue.id)"
                  :disabled="loading"
                  class="btn-danger btn-sm flex-1"
                >
                  Close
                </button>
                <router-link
                  :to="`/display/${queue.id}`"
                  target="_blank"
                  class="btn-secondary btn-sm flex-1"
                >
                  Display Board
                </router-link>
                <button
                  @click="deleteQueue(queue.id)"
                  :disabled="loading"
                  class="btn-danger-solid btn-sm flex-1"
                >
                  Delete
                </button>
              </div>
            </template>
            <p v-else class="text-sm text-gray-500 italic">
              No "{{ formatQueueType(service.queueType) }}" queue exists yet - create it below to enable this service.
            </p>
          </div>
        </div>

        <div v-if="queueStore.currentUser?.role === 'admin'" class="mt-6">
          <button
            @click="showCreateQueueModal = true"
            class="btn-primary btn-md"
          >
            <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            Create New Queue
          </button>
        </div>
      </div>
    </div>

    <div class="panel mb-6">
      <div class="panel-header flex items-center justify-between">
        <h3 class="text-xl font-bold text-bsu-ink">Queue Display</h3>
        <router-link to="/display" target="_blank" class="text-sm font-medium text-bsu-primary hover:underline transition-colors hover:text-bsu-primary-dark">
          View All Boards ↗
        </router-link>
      </div>
      <div class="p-6">
        <div class="flex items-center justify-between mb-4">
          <h4 class="text-lg font-medium text-bsu-ink">{{ selectedQueue?.name || 'No queue selected' }}</h4>
          <select
            v-model="selectedQueueId"
            class="field w-auto py-1.5"
          >
            <option :value="null">Select Queue</option>
            <option :value="q.id" v-for="q in queues" :key="q.id">
              {{ q.name }}
            </option>
          </select>
        </div>

        <div v-if="selectedQueue" class="space-y-4">
          <div class="bg-bsu-surface rounded-2xl p-6">
            <div class="text-center mb-6">
              <h5 class="text-sm text-gray-500 uppercase tracking-wide">CURRENTLY SERVING</h5>
              <div class="mt-2">
                <span
                  v-if="servingTicket"
                  class="inline-block px-6 py-3 bg-bsu-primary text-white text-3xl font-bold rounded-2xl shadow-soft"
                >
                  {{ servingTicket.ticket_code }}
                </span>
                <span
                  v-else
                  class="inline-block px-6 py-3 bg-gray-200 text-gray-500 text-3xl font-bold rounded-2xl"
                >
                  --
                </span>
              </div>
            </div>

            <div class="border-t border-gray-200 pt-4">
              <h5 class="text-sm text-gray-500 uppercase tracking-wide mb-3">Waiting Queue</h5>
              <div class="space-y-2">
                <div
                  v-for="ticket in queueDisplay"
                  :key="ticket.id"
                  class="flex items-center justify-between px-3 py-2.5 rounded-xl"
                  :class="ticket.priority === 'urgent' ? 'bg-red-50 border-l-4 border-red-400' : ticket.priority === 'priority' ? 'bg-bsu-gold/10 border-l-4 border-bsu-gold' : 'bg-white border border-gray-200'"
                >
                  <div class="flex items-center space-x-3">
                    <span class="font-medium text-bsu-ink">{{ ticket.ticket_code }}</span>
                    <span v-if="ticket.priority !== 'normal'" class="text-xs px-2 py-0.5 rounded-xl"
                      :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-bsu-gold/20 text-bsu-gold-dark'"
                    >
                      {{ ticket.priority }}
                    </span>
                  </div>
                  <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
                  </svg>
                </div>

                <div v-if="queueDisplay.length === 0" class="text-center py-4 text-gray-500">
                  No tickets waiting
                </div>
              </div>
            </div>
          </div>

          <div class="flex space-x-3 pt-4">
            <button
              @click="serveNextTicket"
              :disabled="loading || queueDisplay.length === 0"
              class="btn-primary btn-md flex-1"
            >
              <span v-if="!loading">Serve Next Ticket</span>
              <span v-else>Processing...</span>
            </button>
            <button
              @click="completeCurrentTicket"
              :disabled="loading || !servingTicket"
              class="btn-success-solid btn-md flex-1"
            >
              <span v-if="!loading">Mark Complete</span>
              <span v-else>Processing...</span>
            </button>
          </div>
        </div>
        <div v-else class="text-center py-8">
          <p class="text-gray-500">Select a queue to view the display board</p>
        </div>
      </div>
    </div>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div v-if="showCreateQueueModal" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50">
      <Transition
        appear
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">Create New Queue</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Queue Name</label>
            <input
              v-model="newQueueForm.name"
              type="text"
              class="field"
              placeholder="e.g., Document Request"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Queue Type</label>
            <select
              v-model="newQueueForm.queue_type"
              @change="onQueueTypeChange"
              class="field"
            >
              <option :value="type.value" v-for="type in queueTypeOptions" :key="type.value">
                {{ type.label }}
              </option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Ticket Letter</label>
            <input
              v-model="newQueueForm.ticket_letter"
              @input="onTicketLetterInput"
              type="text"
              maxlength="1"
              class="field w-24 uppercase"
              placeholder="E"
            />
            <p class="text-xs text-gray-500 mt-1">Prefixes this queue's tickets (e.g. E-007). Must be unique across all queues.</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Description</label>
            <textarea
              v-model="newQueueForm.description"
              rows="2"
              class="field"
              placeholder="Brief description of the service"
            ></textarea>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Max Capacity</label>
              <input
                v-model.number="newQueueForm.max_capacity"
                type="number"
                min="1"
                max="200"
                class="field"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Slot Duration (min)</label>
              <input
                v-model.number="newQueueForm.slot_duration_minutes"
                type="number"
                min="5"
                max="120"
                class="field"
              />
            </div>
          </div>

          <div class="flex items-center">
            <input
              id="allow_priority"
              type="checkbox"
              v-model="newQueueForm.allow_priority"
              class="h-4 w-4 text-bsu-primary border-gray-300 rounded focus:ring-bsu-primary"
            />
            <label for="allow_priority" class="ml-2 text-sm text-gray-700">
              Allow Priority Access
            </label>
          </div>

          <div v-if="createQueueError" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ createQueueError }}</p>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
          <button
            @click="showCreateQueueModal = false"
            class="btn-secondary btn-md"
          >
            Cancel
          </button>
          <button
            @click="createQueue"
            :disabled="loading"
            class="btn-primary btn-md"
          >
            Create
          </button>
        </div>
      </div>
      </Transition>
    </div>
    </Transition>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div v-if="showBookingSettingsModal" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">Manage Booking - {{ bookingSettingsQueue?.name }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div class="flex items-center">
            <input
              id="booking_enabled"
              type="checkbox"
              v-model="bookingSettingsForm.booking_enabled"
              class="h-4 w-4 text-bsu-primary border-gray-300 rounded focus:ring-bsu-primary"
            />
            <label for="booking_enabled" class="ml-2 text-sm text-gray-700">
              Allow students to book appointments for this service
            </label>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Operating Start</label>
              <input v-model="bookingSettingsForm.operating_start_time" type="time" class="field" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Operating End</label>
              <input v-model="bookingSettingsForm.operating_end_time" type="time" class="field" />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Slot Capacity</label>
              <input v-model.number="bookingSettingsForm.slot_capacity" type="number" min="1" max="50" class="field" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Booking Window (days)</label>
              <input v-model.number="bookingSettingsForm.booking_window_days" type="number" min="1" max="90" class="field" />
            </div>
          </div>

          <div v-if="bookingSettingsError" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ bookingSettingsError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
          <button @click="showBookingSettingsModal = false" class="btn-secondary btn-md">Cancel</button>
          <button @click="saveBookingSettings" :disabled="loading" class="btn-primary btn-md">Save</button>
        </div>
      </div>
    </div>
    </Transition>

    <ConfirmDialog
      v-model="confirmDialog.open"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :confirm-label="confirmDialog.confirmLabel"
      :variant="confirmDialog.variant"
      :loading="confirmLoading"
      @confirm="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import axios from 'axios'
import StatusBadge from '@/components/StatusBadge.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { formatQueueType } from '@/components/icons/QueueIcons'
import { SERVICES } from '@/services/studentServices'

const queueStore = useQueueStore()

const loading = ref(false)
const dashboardError = ref('')
const createQueueError = ref('')
const showCreateQueueModal = ref(false)

const showBookingSettingsModal = ref(false)
const bookingSettingsQueue = ref(null)
const bookingSettingsError = ref('')
const bookingSettingsForm = ref({
  booking_enabled: false,
  operating_start_time: '08:00',
  operating_end_time: '17:00',
  slot_capacity: 3,
  booking_window_days: 14,
})

const openBookingSettings = (queue) => {
  bookingSettingsQueue.value = queue
  bookingSettingsError.value = ''
  bookingSettingsForm.value = {
    booking_enabled: queue.booking_enabled,
    operating_start_time: (queue.operating_start_time || '08:00:00').slice(0, 5),
    operating_end_time: (queue.operating_end_time || '17:00:00').slice(0, 5),
    slot_capacity: queue.slot_capacity,
    booking_window_days: queue.booking_window_days,
  }
  showBookingSettingsModal.value = true
}

const saveBookingSettings = async () => {
  if (!bookingSettingsQueue.value) return
  loading.value = true
  bookingSettingsError.value = ''
  try {
    const payload = {
      ...bookingSettingsForm.value,
      operating_start_time: `${bookingSettingsForm.value.operating_start_time}:00`,
      operating_end_time: `${bookingSettingsForm.value.operating_end_time}:00`,
    }
    await api_patchBookingSettings(bookingSettingsQueue.value.id, payload)
    showBookingSettingsModal.value = false
    await loadQueues()
  } catch (err) {
    bookingSettingsError.value = err.response?.data?.detail || 'Failed to save booking settings'
  } finally {
    loading.value = false
  }
}

const confirmDialog = ref({ open: false, title: '', message: '', confirmLabel: 'Confirm', variant: 'primary' })
const confirmLoading = ref(false)
let confirmAction = null

const openConfirm = ({ title, message, confirmLabel = 'Confirm', variant = 'primary', action }) => {
  confirmAction = action
  confirmDialog.value = { open: true, title, message, confirmLabel, variant }
}

const handleConfirm = async () => {
  if (!confirmAction) return
  confirmLoading.value = true
  try {
    await confirmAction()
  } catch (err) {
    // the action itself already recorded a user-facing error message
  } finally {
    confirmLoading.value = false
    confirmDialog.value.open = false
    confirmAction = null
  }
}

const queues = ref([])
const selectedQueueId = ref(null)
const selectedQueue = computed(() => queues.value.find(q => q.id === selectedQueueId.value))
const serviceCards = computed(() =>
  SERVICES.map((service) => ({
    service,
    queue: queues.value.find((q) => q.queue_type === service.queueType) || null,
  }))
)
const queueDisplay = ref([])
const servingTicket = ref(null)

const newQueueForm = ref({
  name: '',
  queue_type: 'enrollment',
  ticket_letter: 'E',
  description: '',
  max_capacity: 50,
  slot_duration_minutes: 30,
  allow_priority: true,
})

const queueTypeOptions = [
  { value: 'enrollment', label: 'Enrollment' },
  { value: 'document_request', label: 'Document Request' },
  { value: 'clearance', label: 'Clearance' },
  { value: 'scholarship', label: 'Scholarship' },
  { value: 'others', label: 'Others' },
  { value: 'adding_dropping', label: 'Adding & Dropping' },
  { value: 'petition_class', label: 'Petition Class' },
  { value: 'other_concerns', label: 'Others (Miscellaneous)' },
]

const TYPE_TO_DEFAULT_LETTER = {
  enrollment: 'E',
  document_request: 'D',
  clearance: 'C',
  scholarship: 'S',
  others: 'O',
  adding_dropping: 'A',
  petition_class: 'P',
  other_concerns: 'X',
}

// Tracks whether the admin has typed their own letter, so picking a new
// Queue Type doesn't clobber a deliberate override.
const ticketLetterTouched = ref(false)

const onQueueTypeChange = () => {
  if (!ticketLetterTouched.value) {
    newQueueForm.value.ticket_letter = TYPE_TO_DEFAULT_LETTER[newQueueForm.value.queue_type] || ''
  }
}

const onTicketLetterInput = () => {
  ticketLetterTouched.value = true
  newQueueForm.value.ticket_letter = newQueueForm.value.ticket_letter.toUpperCase().slice(0, 1)
}

const loadQueues = async () => {
  dashboardError.value = ''
  try {
    await queueStore.fetchQueues()
    queues.value = queueStore.queues
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to load queues'
  }
}

const pauseQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.pauseQueue(queueId)
    await loadQueues()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to pause queue'
  } finally {
    loading.value = false
  }
}

const resumeQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.resumeQueue(queueId)
    await loadQueues()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to resume queue'
  } finally {
    loading.value = false
  }
}

const closeQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.closeQueue(queueId)
    await loadQueues()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to close queue'
  } finally {
    loading.value = false
  }
}

const deleteQueue = (queueId) => {
  const queueName = queues.value.find((q) => q.id === queueId)?.name || 'this queue'
  openConfirm({
    title: 'Delete this queue?',
    message: `Are you sure you want to delete "${queueName}"? This cannot be undone.`,
    confirmLabel: 'Yes, Delete',
    variant: 'danger',
    action: async () => {
      loading.value = true
      dashboardError.value = ''
      try {
        await queueStore.deleteQueue(queueId)
        queues.value = queues.value.filter((q) => q.id !== queueId)
        await loadQueues()
      } catch (err) {
        dashboardError.value = err.response?.data?.detail || 'Failed to delete queue'
      } finally {
        loading.value = false
      }
    },
  })
}

const createQueue = async () => {
  if (!newQueueForm.value.name) return

  loading.value = true
  createQueueError.value = ''
  try {
    await queueStore.createQueue(newQueueForm.value)
    showCreateQueueModal.value = false
    newQueueForm.value = {
      name: '',
      queue_type: 'enrollment',
      ticket_letter: 'E',
      description: '',
      max_capacity: 50,
      slot_duration_minutes: 30,
      allow_priority: true,
    }
    ticketLetterTouched.value = false
    await loadQueues()
  } catch (err) {
    createQueueError.value = err.response?.data?.detail || 'Failed to create queue'
  } finally {
    loading.value = false
  }
}

const serveNextTicket = async () => {
  if (!selectedQueueId.value) return

  loading.value = true
  try {
    const result = await queueStore.serveNextTicket(selectedQueueId.value)
    servingTicket.value = result
    await updateQueueDisplay()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'No waiting tickets'
  } finally {
    loading.value = false
  }
}

const completeCurrentTicket = async () => {
  if (!servingTicket.value) return

  loading.value = true
  try {
    await queueStore.completeTicket(servingTicket.value.id)
    servingTicket.value = null
    await updateQueueDisplay()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to complete ticket'
  } finally {
    loading.value = false
  }
}

const updateQueueDisplay = async () => {
  if (!selectedQueueId.value) return
  try {
    await queueStore.fetchQueueDisplay(selectedQueueId.value)
    queueDisplay.value = queueStore.queueDisplay.map(t => ({
      ...t,
      priority: t.priority || 'normal',
    }))
  } catch (err) {
    queueDisplay.value = []
  }
}

// Booking settings is a one-off admin action with no other frontend
// consumer, so it calls the API directly rather than adding a rarely-used
// store action - reuses the store's auth token the same way the store's own
// axios instance does.
const api_patchBookingSettings = (queueId, payload) => {
  const token = localStorage.getItem('registrar_token')
  return axios.patch(`/api/queues/${queueId}/booking-settings`, payload, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
}

let displayRefreshTimer = null

onMounted(async () => {
  await loadQueues()
  displayRefreshTimer = setInterval(() => {
    if (selectedQueueId.value) {
      updateQueueDisplay()
    }
  }, 5000)
})

onUnmounted(() => {
  if (displayRefreshTimer) clearInterval(displayRefreshTimer)
})
</script>
