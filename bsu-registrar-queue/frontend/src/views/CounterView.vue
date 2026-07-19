<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-gray-900">Counter</h2>
      <p class="mt-2 text-gray-600">Serve tickets for a queue</p>
    </div>

    <div v-if="counterError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ counterError }}</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
        <h3 class="text-xl font-bold text-gray-900">{{ selectedQueue?.name || 'Select a queue' }}</h3>
        <select
          v-model="selectedQueueId"
          class="px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
        >
          <option :value="null">Select Queue</option>
          <option :value="q.id" v-for="q in queues" :key="q.id">
            {{ q.name }}
          </option>
        </select>
      </div>

      <div class="p-6">
        <div v-if="selectedQueue" class="space-y-6">
          <!-- Currently Serving -->
          <div class="bg-gray-50 rounded-lg p-8 text-center">
            <h4 class="text-sm text-gray-500 uppercase tracking-wide mb-4">Currently Serving</h4>

            <div v-if="servingTicket">
              <span class="inline-block px-8 py-4 bg-bsu-primary text-white text-5xl font-extrabold rounded-full mb-3">
                {{ servingTicket.ticket_number }}
              </span>
              <div class="mb-6">
                <span
                  v-if="servingTicket.priority && servingTicket.priority !== 'normal'"
                  class="text-xs px-2 py-0.5 rounded-full"
                  :class="servingTicket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
                >
                  {{ servingTicket.priority }}
                </span>
              </div>

              <div class="flex justify-center gap-3">
                <button
                  @click="callCurrentTicket"
                  :disabled="loading"
                  class="px-5 py-2.5 text-sm font-medium rounded-md bg-bsu-gold text-gray-900 hover:bg-yellow-500 focus:outline-none focus:ring-2 focus:ring-bsu-gold disabled:opacity-50"
                >
                  {{ justCalled ? 'Called ✓' : 'Call' }}
                </button>
                <button
                  @click="skipCurrentTicket"
                  :disabled="loading"
                  class="px-5 py-2.5 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                >
                  Skip
                </button>
                <button
                  @click="completeCurrentTicket"
                  :disabled="loading"
                  class="px-5 py-2.5 text-sm font-medium rounded-md bg-green-600 text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                >
                  Complete
                </button>
              </div>
            </div>

            <div v-else>
              <span class="inline-block px-8 py-4 bg-gray-200 text-gray-500 text-5xl font-extrabold rounded-full mb-6">
                --
              </span>
              <div>
                <button
                  @click="serveNext"
                  :disabled="loading || waitingTickets.length === 0"
                  class="px-6 py-3 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
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
                class="flex items-center justify-between px-3 py-2 rounded-md"
                :class="ticket.priority === 'urgent' ? 'bg-red-50 border-l-4 border-red-400' : ticket.priority === 'priority' ? 'bg-yellow-50 border-l-4 border-yellow-400' : 'bg-white border border-gray-200'"
              >
                <div class="flex items-center space-x-3">
                  <span class="font-medium text-gray-900">#{{ ticket.ticket_number }}</span>
                  <span
                    v-if="ticket.priority !== 'normal'"
                    class="text-xs px-2 py-0.5 rounded-full"
                    :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
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
          <p class="text-gray-500">Select a queue to start serving tickets</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()

const loading = ref(false)
const counterError = ref('')
const justCalled = ref(false)

const queues = ref([])
const selectedQueueId = ref(null)
const selectedQueue = computed(() => queues.value.find(q => q.id === selectedQueueId.value))

const queueDisplay = ref([])
const servingTicket = ref(null)
const waitingTickets = computed(() =>
  queueDisplay.value.filter(t => t.status === 'waiting').slice().sort((a, b) => a.position - b.position)
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
    await queueStore.fetchQueueDisplay(targetQueueId)
    if (selectedQueueId.value === targetQueueId) {
      queueDisplay.value = queueStore.queueDisplay
    }
  } catch (err) {
    if (selectedQueueId.value === targetQueueId) {
      queueDisplay.value = []
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
  queueDisplay.value = []
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
