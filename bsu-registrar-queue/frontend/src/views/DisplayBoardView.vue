<template>
  <div class="min-h-screen bg-gray-950 text-white flex flex-col">
    <!-- Top bar -->
    <header class="flex items-center justify-between px-8 py-5 border-b border-white/10">
      <div class="flex items-center space-x-4">
        <svg class="w-9 h-9 text-bsu-gold" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
        </svg>
        <div>
          <h1 class="text-lg font-bold leading-tight">BSU Meneses Campus</h1>
          <p class="text-sm text-white/50">{{ queueName || 'Queue Display' }}</p>
        </div>
      </div>
      <div class="flex items-center space-x-6">
        <div class="text-right">
          <p class="text-2xl font-bold tabular-nums">{{ clockTime }}</p>
          <p class="text-xs text-white/50">{{ clockDate }}</p>
        </div>
        <button
          @click="toggleFullscreen"
          class="p-2 rounded-md border border-white/20 text-white/70 hover:text-white hover:border-white/40 transition-colors"
          title="Toggle fullscreen"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>
      </div>
    </header>

    <main class="flex-1 flex flex-col items-center justify-center px-8 py-10">
      <!-- Loading -->
      <div v-if="loading" class="flex flex-col items-center text-white/60">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-bsu-primary-light border-t-transparent mb-4"></div>
        <p>Loading display board…</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center max-w-md">
        <svg class="mx-auto h-14 w-14 text-red-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p class="text-white/70">{{ error }}</p>
        <button
          @click="initialize"
          class="mt-6 px-5 py-2.5 rounded-md bg-bsu-primary hover:bg-pink-800 text-white font-medium"
        >
          Retry
        </button>
      </div>

      <!-- Queue not active -->
      <div v-else-if="queueStatus && queueStatus !== 'active'" class="text-center max-w-md">
        <svg class="mx-auto h-14 w-14 text-white/30 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="text-2xl font-bold mb-1">{{ queueName }}</p>
        <p class="text-white/50 capitalize">This service is currently {{ queueStatus }}.</p>
      </div>

      <!-- Board -->
      <div v-else class="w-full max-w-5xl">
        <!-- Now Serving -->
        <section class="text-center mb-12">
          <h2 class="text-sm font-semibold tracking-[0.3em] text-white/40 uppercase mb-6">Now Serving</h2>

          <div v-if="servingTickets.length > 0" class="flex flex-wrap justify-center gap-6">
            <div
              v-for="ticket in servingTickets"
              :key="ticket.ticket_number"
              class="bg-bsu-primary rounded-2xl px-14 py-10 shadow-lg shadow-pink-900/40 animate-pulse-slow"
            >
              <span class="text-7xl md:text-8xl font-extrabold tabular-nums">{{ ticket.ticket_number }}</span>
            </div>
          </div>
          <div v-else class="inline-block bg-white/5 rounded-2xl px-14 py-10 border border-white/10">
            <span class="text-6xl md:text-7xl font-extrabold text-white/20">--</span>
          </div>
        </section>

        <!-- Waiting -->
        <section>
          <h2 class="text-sm font-semibold tracking-[0.3em] text-white/40 uppercase mb-4 text-center">
            Waiting ({{ waitingTickets.length }})
          </h2>

          <div v-if="waitingTickets.length > 0" class="flex flex-wrap justify-center gap-3">
            <div
              v-for="(ticket, idx) in waitingPreview"
              :key="ticket.ticket_number"
              class="rounded-xl px-6 py-4 text-center"
              :class="idx === 0 ? 'bg-bsu-gold text-gray-900' : 'bg-white/5 border border-white/10 text-white'"
            >
              <p class="text-3xl font-bold tabular-nums">{{ ticket.ticket_number }}</p>
              <p class="text-xs mt-1" :class="idx === 0 ? 'text-gray-800/70' : 'text-white/40'">
                {{ idx === 0 ? 'Up Next' : `~${ticket.estimated_wait_time_minutes ?? 0} min` }}
              </p>
            </div>
            <div
              v-if="waitingOverflow > 0"
              class="rounded-xl px-6 py-4 text-center bg-white/5 border border-white/10 text-white/50 flex items-center justify-center"
            >
              <span class="text-sm font-medium">+{{ waitingOverflow }} more</span>
            </div>
          </div>
          <p v-else class="text-center text-white/30">No one is waiting right now</p>
        </section>
      </div>
    </main>

    <footer class="text-center py-4 text-xs text-white/30 border-t border-white/10">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'

const route = useRoute()
const queueStore = useQueueStore()

const queueId = parseInt(route.params.id)
const WAITING_PREVIEW_LIMIT = 8

const loading = ref(true)
const error = ref(null)
const queueName = ref('')
const queueStatus = ref(null)

const now = ref(new Date())
const clockTime = computed(() => format(now.value, 'h:mm:ss a'))
const clockDate = computed(() => format(now.value, 'EEEE, MMMM d, yyyy'))

const display = computed(() => queueStore.queueDisplay)
const servingTickets = computed(() => display.value.filter(t => t.status === 'serving'))
const waitingTickets = computed(() =>
  display.value.filter(t => t.status === 'waiting').slice().sort((a, b) => a.position - b.position)
)
const waitingPreview = computed(() => waitingTickets.value.slice(0, WAITING_PREVIEW_LIMIT))
const waitingOverflow = computed(() => Math.max(0, waitingTickets.value.length - WAITING_PREVIEW_LIMIT))

let clockTimer = null

const resolveQueueInfo = async () => {
  try {
    await queueStore.fetchActiveQueues()
    const match = queueStore.activeQueues.find(q => q.id === queueId)
    if (match) {
      queueName.value = match.name
      queueStatus.value = match.status
      return
    }
  } catch (err) {
    // active-queues lookup failed; fall back to ticket data below
  }
  // Queue isn't active (or lookup failed) - infer name from any ticket, status unknown
  const anyTicket = queueStore.queueDisplay[0]
  queueName.value = anyTicket?.queue_name || `Queue #${queueId}`
  queueStatus.value = null
}

const initialize = async () => {
  loading.value = true
  error.value = null
  try {
    await queueStore.fetchQueueDisplay(queueId)
    await resolveQueueInfo()
    queueStore.startPollingQueueDisplay(queueId, 4000)
  } catch (err) {
    error.value = 'Unable to reach the server. Retrying automatically…'
  } finally {
    loading.value = false
  }
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

onMounted(() => {
  initialize()
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  queueStore.stopPolling()
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style scoped>
@keyframes pulse-slow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}
.animate-pulse-slow {
  animation: pulse-slow 2.5s ease-in-out infinite;
}
</style>
