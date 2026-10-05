<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-bsu-ink">Counter</h2>
      <p class="mt-2 text-gray-500">Select a service or a queue</p>
    </div>

    <div v-if="counterError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ counterError }}</p>
    </div>

    <!-- Service selector -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <button
        v-for="service in availableServices"
        :key="service.key"
        type="button"
        @click="selectedServiceKey = service.key"
        class="relative text-left p-5 rounded-2xl bg-white transition-all duration-200 ease-out hover:-translate-y-0.5 active:scale-[0.98]"
        :class="selectedServiceKey === service.key
          ? 'border-2 border-bsu-primary shadow-soft-lg ring-4 ring-bsu-primary/10'
          : 'border border-gray-100 shadow-soft hover:shadow-soft-lg'"
      >
        <div
          class="absolute top-4 right-4 w-6 h-6 rounded-full flex items-center justify-center"
          :class="selectedServiceKey === service.key ? 'bg-bsu-primary text-white' : 'border-2 border-gray-200'"
        >
          <svg v-if="selectedServiceKey === service.key" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <div class="w-11 h-11 rounded-xl bg-bsu-primary/10 flex items-center justify-center mb-3">
          <component :is="service.icon" class="w-6 h-6 text-bsu-primary" />
        </div>
        <h3 class="font-bold text-bsu-ink mb-1 pr-6">{{ service.label }}</h3>
        <p class="text-sm text-gray-500 mb-4 pr-2">{{ service.description }}</p>

        <div class="flex items-center justify-between text-sm">
          <span class="flex items-center gap-1.5 text-gray-500">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <span v-if="serviceStats(service).waiting !== null">{{ serviceStats(service).waiting }} waiting</span>
            <span v-else>&ndash;</span>
          </span>
          <span class="text-gray-400" v-if="serviceStats(service).eta !== null">~{{ serviceStats(service).eta }} min</span>
        </div>
      </button>

      <div v-if="availableServices.length === 0" class="col-span-full text-center py-10 text-gray-400">
        No active services right now
      </div>
    </div>

    <!-- Selected service panel -->
    <div v-if="selectedService" class="panel overflow-hidden">
      <div class="panel-header flex items-center justify-between gap-4 flex-wrap">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-bsu-primary/10 flex items-center justify-center shrink-0">
            <component :is="selectedService.icon" class="w-5 h-5 text-bsu-primary" />
          </div>
          <div>
            <p class="text-xs font-semibold tracking-widest uppercase text-bsu-primary">Selected Service</p>
            <h3 class="text-xl font-bold text-bsu-ink leading-tight">{{ selectedService.label }}</h3>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <span class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white shadow-soft text-sm font-medium text-bsu-ink">
            <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            Live &middot; {{ waitingTickets.length }} waiting
          </span>
          <select
            v-model="selectedServiceKey"
            class="field w-auto py-1.5"
          >
            <option :value="null">Switch service&hellip;</option>
            <option :value="service.key" v-for="service in availableServices" :key="service.key">
              {{ service.label }}
            </option>
          </select>
        </div>
      </div>

      <div v-if="selectedQueueId" class="grid grid-cols-1 lg:grid-cols-3">
        <!-- Now serving -->
        <div class="lg:col-span-2 p-6 lg:border-r border-gray-100">
          <div v-if="servingTicket">
            <div class="flex items-center justify-between flex-wrap gap-2 mb-5">
              <span class="flex items-center gap-2 text-xs font-bold tracking-widest uppercase text-bsu-primary">
                <span class="w-2 h-2 rounded-full bg-bsu-primary"></span>
                Now Serving
              </span>
              <span v-if="servingTicket.called_at" class="text-sm text-gray-400">
                Called at {{ format(new Date(servingTicket.called_at), 'h:mm a') }}
                <template v-if="calledElapsed"> &middot; {{ calledElapsed }} elapsed</template>
              </span>
            </div>

            <div class="text-7xl font-extrabold text-bsu-ink tabular-nums leading-none mb-3">
              {{ servingTicket.ticket_code }}
            </div>
            <div class="flex items-center gap-2 mb-8 min-h-[1.5rem]">
              <span
                v-if="servingTicket.document_type"
                class="text-sm text-gray-500"
              >
                {{ servingTicket.document_type }}
              </span>
              <span
                v-if="servingTicket.priority && servingTicket.priority !== 'normal'"
                class="text-xs px-2 py-0.5 rounded-xl"
                :class="servingTicket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-bsu-gold/20 text-bsu-gold-dark'"
              >
                {{ servingTicket.priority }}
              </span>
              <span
                v-if="servingTicket.recalled_at"
                class="text-xs px-2 py-0.5 rounded-xl bg-blue-100 text-blue-800"
              >
                recalled
              </span>
            </div>

            <div class="flex flex-wrap gap-3">
              <button
                @click="callCurrentTicket"
                :disabled="loading"
                class="btn-gold rounded-full px-5 py-2.5"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                </svg>
                {{ justCalled ? 'Called ✓' : 'Repeat call' }}
              </button>
              <button
                @click="skipCurrentTicket"
                :disabled="loading"
                class="btn-danger rounded-full px-5 py-2.5"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Skip ticket
              </button>
              <button
                @click="completeCurrentTicket"
                :disabled="loading"
                class="btn-success-solid rounded-full px-6 py-2.5 ml-auto"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Complete ticket
              </button>
            </div>
          </div>

          <div v-else class="py-6">
            <span class="flex items-center gap-2 text-xs font-bold tracking-widest uppercase text-gray-400 mb-5">
              <span class="w-2 h-2 rounded-full bg-gray-300"></span>
              Now Serving
            </span>
            <div class="text-7xl font-extrabold text-gray-200 tabular-nums leading-none mb-8">&ndash;&ndash;</div>
            <button
              @click="serveNext"
              :disabled="loading || waitingTickets.length === 0"
              class="btn-primary rounded-full px-6 py-3"
            >
              <span v-if="!loading">Serve Next Ticket</span>
              <span v-else>Processing&hellip;</span>
            </button>
          </div>
        </div>

        <!-- Next in queue -->
        <div class="p-6 bg-bsu-surface/60">
          <div class="flex items-center justify-between mb-1">
            <h4 class="font-bold text-bsu-ink">Next in queue</h4>
            <span class="text-xs px-2.5 py-1 rounded-full bg-bsu-primary/10 text-bsu-primary font-semibold">
              {{ waitingTickets.length }} total
            </span>
          </div>
          <p class="text-sm text-gray-400 mb-4">
            Estimated wait &middot; {{ waitingTickets[0]?.estimated_wait_time_minutes ?? 0 }} minutes
          </p>

          <div class="space-y-2">
            <div
              v-for="ticket in waitingPreview"
              :key="ticket.ticket_number"
              class="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white shadow-soft"
            >
              <span
                class="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0"
                :class="priorityAvatarClass(ticket.priority)"
              >
                {{ ticket.ticket_code.charAt(0) }}
              </span>
              <div class="min-w-0">
                <p class="font-bold text-bsu-ink text-sm truncate">{{ ticket.ticket_code }}</p>
                <p class="text-xs text-gray-400 truncate">{{ priorityLabel(ticket.priority) }}</p>
              </div>
              <span class="ml-auto text-sm text-gray-400 shrink-0">~{{ ticket.estimated_wait_time_minutes ?? 0 }} min</span>
            </div>

            <div v-if="waitingTickets.length === 0" class="text-center py-6 text-gray-400 text-sm">
              No tickets waiting
            </div>
          </div>

          <div v-if="waitingOverflow > 0" class="flex items-center justify-between mt-3 text-sm">
            <span class="text-gray-400">+{{ waitingOverflow }} more tickets</span>
            <router-link
              :to="`/display/${selectedQueueId}`"
              target="_blank"
              class="text-bsu-primary font-semibold hover:text-bsu-primary-dark"
            >
              View full queue &rarr;
            </router-link>
          </div>

          <!-- Skipped today: a late student can be recalled once -->
          <div class="mt-6 pt-5 border-t border-gray-200/70">
            <div class="flex items-center justify-between mb-1">
              <h4 class="font-bold text-bsu-ink">Skipped</h4>
              <span class="text-xs px-2.5 py-1 rounded-full bg-red-50 text-red-700 font-semibold">
                {{ skippedTickets.length }} today
              </span>
            </div>
            <p class="text-sm text-gray-400 mb-4">
              <template v-if="servingTicket">Finish the current ticket to recall one</template>
              <template v-else>Recall a late student &middot; once per ticket</template>
            </p>

            <div class="space-y-2">
              <div
                v-for="ticket in skippedTickets"
                :key="ticket.id"
                class="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white shadow-soft"
              >
                <div class="min-w-0">
                  <p class="font-bold text-bsu-ink text-sm truncate">{{ ticket.ticket_code }}</p>
                  <p v-if="ticket.updated_at" class="text-xs text-gray-400 truncate">
                    Skipped {{ format(new Date(ticket.updated_at), 'h:mm a') }}
                  </p>
                </div>
                <button
                  @click="recallSkippedTicket(ticket)"
                  :disabled="loading || !!servingTicket"
                  class="btn-gold btn-sm rounded-full ml-auto shrink-0"
                >
                  Recall
                </button>
              </div>

              <div v-if="skippedTickets.length === 0" class="text-center py-4 text-gray-400 text-sm">
                No skipped tickets
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-12 text-gray-500">
        Select a service to start serving tickets
      </div>
    </div>

    <div v-else class="panel text-center py-12 text-gray-500">
      Select a service to start serving tickets
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
import { SERVICES } from '@/services/studentServices'

const queueStore = useQueueStore()

const loading = ref(false)
const counterError = ref('')
const justCalled = ref(false)

const now = ref(new Date())

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
const skippedTickets = ref([])
const waitingTickets = computed(() =>
  waitingTicketsRaw.value.filter(t => t.status === 'waiting').slice().sort((a, b) => a.position - b.position)
)

const WAITING_PREVIEW_LIMIT = 4
const waitingPreview = computed(() => waitingTickets.value.slice(0, WAITING_PREVIEW_LIMIT))
const waitingOverflow = computed(() => Math.max(0, waitingTickets.value.length - WAITING_PREVIEW_LIMIT))

// Card-level "N waiting / ~N min" preview for services that aren't currently
// selected - sourced from the same now-serving-overview endpoint the display
// boards already use, matched against this service's underlying queue.
const serviceStats = (service) => {
  const queue = queues.value.find((q) => q.queue_type === service.queueType)
  if (!queue) return { waiting: null, eta: null }
  const overviewEntry = queueStore.nowServingOverview.find((o) => o.queue_id === queue.id)
  if (!overviewEntry) return { waiting: null, eta: null }
  return { waiting: overviewEntry.waiting_count, eta: overviewEntry.waiting_count * queue.slot_duration_minutes }
}

const priorityLabel = (priority) => {
  if (priority === 'urgent') return 'Urgent'
  if (priority === 'priority') return 'Priority lane'
  return 'Standard queue'
}

const priorityAvatarClass = (priority) => {
  if (priority === 'urgent') return 'bg-red-100 text-red-700'
  if (priority === 'priority') return 'bg-bsu-gold/20 text-bsu-gold-dark'
  return 'bg-gray-100 text-gray-500'
}

const calledElapsed = computed(() => {
  if (!servingTicket.value?.called_at) return null
  const calledDate = new Date(servingTicket.value.called_at)
  const diffSeconds = Math.max(0, Math.floor((now.value - calledDate) / 1000))
  const mins = String(Math.floor(diffSeconds / 60)).padStart(2, '0')
  const secs = String(diffSeconds % 60).padStart(2, '0')
  return `${mins}:${secs}`
})

const loadQueues = async () => {
  counterError.value = ''
  try {
    await queueStore.fetchActiveQueues()
    queues.value = queueStore.activeQueues
    await queueStore.fetchNowServingOverview()
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

  try {
    const recallable = await queueStore.fetchRecallableTickets(targetQueueId)
    if (selectedQueueId.value === targetQueueId) {
      skippedTickets.value = recallable
    }
  } catch (err) {
    // Keep the last known list; the next refresh will try again.
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

const recallSkippedTicket = async (ticket) => {
  if (servingTicket.value) return
  loading.value = true
  counterError.value = ''
  try {
    servingTicket.value = await queueStore.recallTicket(ticket.id)
    await updateQueueDisplay()
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to recall ticket'
    await updateQueueDisplay()
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
  skippedTickets.value = []
  updateQueueDisplay()
})

let displayRefreshTimer = null
let clockTimer = null

onMounted(async () => {
  await loadQueues()
  displayRefreshTimer = setInterval(() => {
    if (selectedQueueId.value) {
      updateQueueDisplay()
    }
    queueStore.fetchNowServingOverview().catch(() => {})
  }, 5000)
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  if (displayRefreshTimer) clearInterval(displayRefreshTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>
