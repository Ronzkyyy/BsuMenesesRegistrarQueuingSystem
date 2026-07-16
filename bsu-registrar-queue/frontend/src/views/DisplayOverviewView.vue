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
          <p class="text-sm text-white/50">All Queues Overview</p>
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

    <main class="flex-1 px-8 py-10">
      <!-- Loading -->
      <div v-if="loading && overview.length === 0" class="flex flex-col items-center justify-center h-full text-white/60">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-bsu-primary-light border-t-transparent mb-4"></div>
        <p>Loading queue overview…</p>
      </div>

      <!-- Error -->
      <div v-else-if="error && overview.length === 0" class="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto">
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

      <!-- Empty -->
      <div v-else-if="overview.length === 0" class="flex items-center justify-center h-full">
        <p class="text-white/30 text-xl">No active services right now</p>
      </div>

      <!-- Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="q in overview"
          :key="q.queue_id"
          class="bg-white/5 border border-white/10 rounded-2xl p-6 text-center"
        >
          <h2 class="text-sm font-semibold tracking-[0.2em] text-white/40 uppercase mb-4">{{ q.queue_name }}</h2>

          <div class="mb-4">
            <p class="text-xs uppercase tracking-wide text-white/30 mb-2">Now Serving</p>
            <div v-if="q.serving_ticket_numbers.length > 0" class="flex flex-wrap justify-center gap-2">
              <span
                v-for="num in q.serving_ticket_numbers"
                :key="num"
                class="inline-block bg-bsu-primary rounded-xl px-5 py-3 text-3xl font-extrabold tabular-nums"
              >
                {{ num }}
              </span>
            </div>
            <span v-else class="inline-block bg-white/5 border border-white/10 rounded-xl px-5 py-3 text-3xl font-extrabold text-white/20">
              --
            </span>
          </div>

          <div class="flex items-center justify-center space-x-6 text-sm">
            <div>
              <p class="text-white/30">Waiting</p>
              <p class="text-lg font-bold tabular-nums">{{ q.waiting_count }}</p>
            </div>
            <div>
              <p class="text-white/30">Next</p>
              <p class="text-lg font-bold tabular-nums">{{ q.next_ticket_number ?? '--' }}</p>
            </div>
          </div>
        </div>
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
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()

const loading = ref(true)
const error = ref(null)

const now = ref(new Date())
const clockTime = computed(() => format(now.value, 'h:mm:ss a'))
const clockDate = computed(() => format(now.value, 'EEEE, MMMM d, yyyy'))

const overview = computed(() => queueStore.nowServingOverview)

let clockTimer = null

const initialize = async () => {
  loading.value = true
  error.value = null
  try {
    await queueStore.fetchNowServingOverview()
  } catch (err) {
    error.value = 'Unable to reach the server. Retrying automatically…'
  } finally {
    loading.value = false
  }
  queueStore.startPollingNowServingOverview()
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
