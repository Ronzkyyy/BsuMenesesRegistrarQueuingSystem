<template>
  <div class="min-h-screen bg-bsu-surface text-bsu-ink flex flex-col">
    <!-- Top bar -->
    <header class="flex items-center justify-between px-8 py-5 bg-white border-b border-gray-100 shadow-soft">
      <div class="flex items-center space-x-3">
        <img :src="BSUlogo" alt="BSU Logo" class="w-10 h-10 object-contain" />
        <img :src="MENESESlogo" alt="Meneses Campus Logo" class="w-10 h-10 object-contain" />
        <div>
          <h1 class="text-lg font-bold leading-tight text-bsu-ink">BSU Meneses Campus</h1>
          <p class="text-sm text-gray-500">{{ queueName || 'Queue Display' }}</p>
        </div>
      </div>
      <div class="flex items-center space-x-6">
        <div class="text-right">
          <p class="text-2xl font-bold tabular-nums text-bsu-ink">{{ clockTime }}</p>
          <p class="text-xs text-gray-500">{{ clockDate }}</p>
        </div>
        <button
          @click="toggleFullscreen"
          class="p-2 rounded-xl border border-gray-200 text-gray-500 hover:text-bsu-primary hover:border-bsu-primary/40 transition-colors"
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
      <div v-if="loading" class="flex flex-col items-center text-gray-500">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-bsu-primary border-t-transparent mb-4"></div>
        <p>Loading display board…</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center max-w-md">
        <svg class="mx-auto h-14 w-14 text-red-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p class="text-gray-500">{{ error }}</p>
        <button
          @click="initialize"
          class="btn btn-primary mt-6 px-5 py-2.5"
        >
          Retry
        </button>
      </div>

      <!-- Queue not active -->
      <div v-else-if="queueStatus && queueStatus !== 'active'" class="text-center max-w-md">
        <svg class="mx-auto h-14 w-14 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="text-2xl font-bold mb-1 text-bsu-ink">{{ queueName }}</p>
        <p class="text-gray-500 capitalize">This service is currently {{ queueStatus }}.</p>
      </div>

      <!-- Board -->
      <div v-else class="w-full max-w-5xl">
        <!-- Now Serving -->
        <section class="text-center mb-12">
          <h2 class="text-xl md:text-2xl font-bold tracking-[0.25em] text-bsu-ink uppercase mb-6">Now Serving</h2>

          <div v-if="servingTickets.length > 0" class="flex flex-wrap justify-center gap-6">
            <div
              v-for="ticket in servingTickets"
              :key="ticket.ticket_number"
              class="bg-gradient-to-br from-bsu-primary to-bsu-peach rounded-3xl px-16 py-12 shadow-soft-lg"
              :class="justCalled[ticket.ticket_number] ? 'animate-called-pulse' : 'animate-pulse-slow'"
            >
              <span class="text-8xl md:text-9xl font-extrabold text-white tabular-nums drop-shadow-lg">{{ ticket.ticket_code }}</span>
            </div>
          </div>
          <div v-else class="inline-block bg-white rounded-3xl px-16 py-12 border border-gray-100 shadow-soft">
            <span class="text-7xl md:text-8xl font-extrabold text-gray-300">--</span>
          </div>
        </section>

        <!-- Waiting -->
        <section>
          <h2 class="text-sm font-semibold tracking-[0.3em] text-gray-400 uppercase mb-4 text-center">
            Waiting ({{ waitingTickets.length }})
          </h2>

          <div v-if="waitingTickets.length > 0" class="flex flex-wrap justify-center gap-3">
            <div
              v-for="(ticket, idx) in waitingPreview"
              :key="ticket.ticket_number"
              class="rounded-2xl px-6 py-4 text-center shadow-soft"
              :class="idx === 0 ? 'bg-bsu-gold text-bsu-ink' : 'bg-white border border-gray-100 text-bsu-ink'"
            >
              <p class="text-3xl font-bold tabular-nums">{{ ticket.ticket_code }}</p>
              <p class="text-xs mt-1" :class="idx === 0 ? 'text-bsu-ink/60' : 'text-gray-400'">
                {{ idx === 0 ? 'Up Next' : `~${ticket.estimated_wait_time_minutes ?? 0} min` }}
              </p>
            </div>
            <div
              v-if="waitingOverflow > 0"
              class="rounded-2xl px-6 py-4 text-center bg-white border border-gray-100 text-gray-400 shadow-soft flex items-center justify-center"
            >
              <span class="text-sm font-medium">+{{ waitingOverflow }} more</span>
            </div>
          </div>
          <p v-else class="text-center text-gray-400">No one is waiting right now</p>
        </section>
      </div>
    </main>

    <MediaAnnouncementPanel />

    <footer class="text-center py-4 text-xs text-gray-400 border-t border-gray-100">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
import MediaAnnouncementPanel from '@/components/MediaAnnouncementPanel.vue'
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

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

const lastCalledAt = ref({})
const justCalled = ref({})

const playChime = () => {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    const ctx = new AudioContextClass()
    const oscillator = ctx.createOscillator()
    const gain = ctx.createGain()
    oscillator.type = 'sine'
    oscillator.frequency.value = 880
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4)
    oscillator.connect(gain)
    gain.connect(ctx.destination)
    oscillator.start()
    oscillator.stop(ctx.currentTime + 0.4)
  } catch (err) {
    // Audio may be blocked by the browser's autoplay policy - fail silent,
    // the visual pulse below still happens regardless.
  }
}

watch(servingTickets, (tickets) => {
  // Object keys are always strings, so ticket_number (a number) must be
  // stringified here to match - otherwise every key looks stale on every
  // poll and the baseline needed for the fix below never sticks.
  const currentKeys = new Set(tickets.map((ticket) => String(ticket.ticket_number)))
  Object.keys(lastCalledAt.value).forEach((key) => {
    if (!currentKeys.has(key)) delete lastCalledAt.value[key]
  })
  Object.keys(justCalled.value).forEach((key) => {
    if (!currentKeys.has(key)) delete justCalled.value[key]
  })

  tickets.forEach((ticket) => {
    const key = ticket.ticket_number
    // hasBaseline tracks whether we've observed this ticket before at all
    // (even while called_at was still null) - otherwise a display board
    // that loads fresh would immediately pulse for a call that happened
    // before the page even opened.
    const hasBaseline = Object.prototype.hasOwnProperty.call(lastCalledAt.value, key)
    const previous = lastCalledAt.value[key]
    lastCalledAt.value[key] = ticket.called_at
    if (hasBaseline && ticket.called_at && previous !== ticket.called_at) {
      justCalled.value[key] = true
      playChime()
      setTimeout(() => {
        justCalled.value[key] = false
      }, 2000)
    }
  })
})

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

@keyframes called-pulse {
  0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(232, 93, 142, 0.6); }
  50% { transform: scale(1.05); box-shadow: 0 0 0 20px rgba(232, 93, 142, 0); }
}
.animate-called-pulse {
  animation: called-pulse 0.6s ease-in-out 3;
}
</style>
