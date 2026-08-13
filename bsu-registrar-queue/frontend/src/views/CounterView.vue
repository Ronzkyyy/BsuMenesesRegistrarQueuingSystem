<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-bsu-ink">Counter</h2>
      <p class="mt-2 text-gray-500">Serve tickets for a queue</p>
    </div>

    <div v-if="counterError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ counterError }}</p>
    </div>

    <div class="panel">
      <div class="panel-header flex items-center justify-between">
        <h3 class="text-xl font-bold text-bsu-ink">{{ selectedService?.label || 'Select a service' }}</h3>
        <select
          v-model="selectedServiceKey"
          class="field w-auto py-1.5"
        >
          <option :value="null">Select Service</option>
          <option :value="service.key" v-for="service in availableServices" :key="service.key">
            {{ service.label }}
          </option>
        </select>
      </div>

      <div class="p-6">
        <div v-if="selectedQueueId" class="space-y-6">
          <!-- Currently Serving -->
          <div class="bg-bsu-surface rounded-2xl p-8 text-center">
            <h4 class="text-sm text-gray-500 uppercase tracking-wide mb-4">Currently Serving</h4>

            <div v-if="servingTicket">
              <span class="inline-block px-8 py-4 bg-gradient-to-br from-bsu-primary to-bsu-peach text-white text-5xl font-extrabold rounded-2xl mb-3 shadow-soft">
                {{ servingTicket.ticket_code }}
              </span>
              <p v-if="servingTicket.purpose" class="text-sm text-gray-600 mb-2">{{ servingTicket.purpose }}</p>
              <div class="mb-6">
                <span
                  v-if="servingTicket.priority && servingTicket.priority !== 'normal'"
                  class="text-xs px-2 py-0.5 rounded-xl"
                  :class="servingTicket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-bsu-gold/20 text-bsu-gold-dark'"
                >
                  {{ servingTicket.priority }}
                </span>
              </div>

              <div class="flex justify-center gap-3">
                <button
                  @click="callCurrentTicket"
                  :disabled="loading"
                  class="btn-gold btn-md px-5 py-2.5"
                >
                  {{ justCalled ? 'Called ✓' : 'Call' }}
                </button>
                <button
                  @click="skipCurrentTicket"
                  :disabled="loading"
                  class="btn-danger-solid btn-md px-5 py-2.5"
                >
                  Skip
                </button>
                <button
                  @click="completeCurrentTicket"
                  :disabled="loading"
                  class="btn-success-solid btn-md px-5 py-2.5"
                >
                  Complete
                </button>
              </div>
            </div>

            <div v-else>
              <span class="inline-block px-8 py-4 bg-gray-200 text-gray-500 text-5xl font-extrabold rounded-2xl mb-6">
                --
              </span>
              <div>
                <button
                  @click="serveNext"
                  :disabled="loading || waitingTickets.length === 0"
                  class="btn-primary btn-md px-6 py-3"
                >
                  <span v-if="!loading">Serve Next Ticket</span>
                  <span v-else>Processing...</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Waiting list -->
          <div>
            <h4 class="text-sm text-gray-500 uppercase tracking-wide mb-3">Waiting ({{ waitingTickets.length }})</h4>
            <div class="space-y-2">
              <div
                v-for="ticket in waitingTickets"
                :key="ticket.ticket_number"
                class="flex items-center justify-between px-3 py-2.5 rounded-xl"
                :class="ticket.priority === 'urgent' ? 'bg-red-50 border-l-4 border-red-400' : ticket.priority === 'priority' ? 'bg-bsu-gold/10 border-l-4 border-bsu-gold' : 'bg-white border border-gray-200'"
              >
                <div class="flex items-center space-x-3">
                  <span class="font-medium text-bsu-ink">{{ ticket.ticket_code }}</span>
                  <span v-if="ticket.purpose" class="text-sm text-gray-500">{{ ticket.purpose }}</span>
                  <span
                    v-if="ticket.priority !== 'normal'"
                    class="text-xs px-2 py-0.5 rounded-xl"
                    :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-bsu-gold/20 text-bsu-gold-dark'"
                  >
                    {{ ticket.priority }}
                  </span>
                </div>
                <span class="text-sm text-gray-500">~{{ ticket.estimated_wait_time_minutes ?? 0 }} min</span>
              </div>

              <div v-if="waitingTickets.length === 0" class="text-center py-4 text-gray-500">
                No tickets waiting
              </div>
            </div>
          </div>
        </div>

        <div v-else class="text-center py-12">
          <p class="text-gray-500">Select a service to start serving tickets</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { SERVICES } from '@/services/studentServices'

const queueStore = useQueueStore()

const loading = ref(false)
const counterError = ref('')
const justCalled = ref(false)

const queues = ref([])
const selectedServiceKey = ref(null)
// Only offer services whose underlying queue is currently active - staff
// couldn't select a paused/closed queue before this change either.
const availableServices = computed(() =>
  SERVICES.filter((service) => queues.value.some((q) => q.queue_type === service.queueType))
)
const selectedService = computed(() =>
  availableServices.value.find((service) => service.key === selectedServiceKey.value) || null
)
// Several services share one underlying queue (e.g. Adding & Dropping,
// Enrollment, and Petition Class all resolve to the same Enrollment queue) -
// this is the actual queue id every fetch/serve action below operates on.
const selectedQueueId = computed(() => {
  if (!selectedService.value) return null
  const queue = queues.value.find((q) => q.queue_type === selectedService.value.queueType)
  return queue ? queue.id : null
})

const waitingTicketsRaw = ref([])
const servingTicket = ref(null)
const waitingTickets = computed(() =>
  waitingTicketsRaw.value.filter(t => t.status === 'waiting').slice().sort((a, b) => a.position - b.position)
)

const loadQueues = async () => {
  counterError.value = ''
  try {
    await queueStore.fetchActiveQueues()
    queues.value = queueStore.activeQueues
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to load queues'
  }
}

const updateQueueDisplay = async () => {
  if (!selectedQueueId.value) return
  const targetQueueId = selectedQueueId.value

  try {
    await queueStore.fetchQueueTickets(targetQueueId, 'waiting')
    if (selectedQueueId.value === targetQueueId) {
      waitingTicketsRaw.value = queueStore.queueTickets
    }
  } catch (err) {
    if (selectedQueueId.value === targetQueueId) {
      waitingTicketsRaw.value = []
    }
  }

  try {
    await queueStore.fetchQueueTickets(targetQueueId, 'serving')
    if (selectedQueueId.value !== targetQueueId) return
    const stillServing = queueStore.queueTickets[0] || null
    if (stillServing) {
      if (!servingTicket.value || servingTicket.value.id !== stillServing.id) {
        servingTicket.value = stillServing
      }
    } else if (servingTicket.value) {
      servingTicket.value = null
    }
  } catch (err) {
    // Leave servingTicket as-is if this lookup fails - the waiting-list
    // display above still updates, just without reconciling who's
    // currently being served.
  }
}

const serveNext = async () => {
  if (!selectedQueueId.value) return
  const targetQueueId = selectedQueueId.value
  loading.value = true
  counterError.value = ''
  try {
    const result = await queueStore.serveNextTicket(targetQueueId)
    if (selectedQueueId.value === targetQueueId) {
      servingTicket.value = result
      await updateQueueDisplay()
    }
  } catch (err) {
    if (selectedQueueId.value === targetQueueId) {
      counterError.value = err.response?.data?.detail || 'No waiting tickets'
    }
  } finally {
    loading.value = false
  }
}

const callCurrentTicket = async () => {
  if (!servingTicket.value) return
  loading.value = true
  counterError.value = ''
  try {
    await queueStore.callTicket(servingTicket.value.id)
    justCalled.value = true
    setTimeout(() => { justCalled.value = false }, 2000)
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to call ticket'
  } finally {
    loading.value = false
  }
}

const skipCurrentTicket = async () => {
  if (!servingTicket.value) return
  loading.value = true
  counterError.value = ''
  try {
    await queueStore.markNoShow(servingTicket.value.id)
    servingTicket.value = null
    await updateQueueDisplay()
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to skip ticket'
  } finally {
    loading.value = false
  }
}

const completeCurrentTicket = async () => {
  if (!servingTicket.value) return
  loading.value = true
  counterError.value = ''
  try {
    await queueStore.completeTicket(servingTicket.value.id)
    servingTicket.value = null
    await updateQueueDisplay()
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to complete ticket'
  } finally {
    loading.value = false
  }
}

watch(selectedQueueId, () => {
  servingTicket.value = null
  waitingTicketsRaw.value = []
  updateQueueDisplay()
})

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
