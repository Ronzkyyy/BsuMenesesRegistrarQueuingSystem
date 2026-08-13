<template>
  <div class="h-screen overflow-hidden bg-bsu-surface text-bsu-ink flex flex-col">
    <!-- Top bar -->
    <header class="flex items-center justify-between px-6 py-2 bg-white border-b border-gray-100 shadow-soft shrink-0">
      <div class="flex items-center space-x-2">
        <img :src="BSUlogo" alt="BSU Logo" class="w-7 h-7 object-contain" />
        <img :src="MENESESlogo" alt="Meneses Campus Logo" class="w-7 h-7 object-contain" />
        <div>
          <h1 class="text-sm font-bold leading-tight text-bsu-ink">BSU Meneses Campus</h1>
          <p class="text-xs text-gray-500">All Queues Overview</p>
        </div>
      </div>
      <div class="flex items-center space-x-4">
        <div class="text-right">
          <p class="text-lg font-bold tabular-nums leading-tight text-bsu-ink">{{ clockTime }}</p>
          <p class="text-xs text-gray-500">{{ clockDate }}</p>
        </div>
        <button
          @click="toggleFullscreen"
          class="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:text-bsu-primary hover:border-bsu-primary/40 transition-colors"
          title="Toggle fullscreen"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>
      </div>
    </header>

    <main class="flex-1 min-h-0 px-6 py-3 flex flex-col overflow-hidden">
      <!-- Loading -->
      <div v-if="loading && overview.length === 0" class="flex flex-col items-center justify-center h-full text-gray-500">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-bsu-primary border-t-transparent mb-4"></div>
        <p>Loading queue overview…</p>
      </div>

      <!-- Error -->
      <div v-else-if="error && overview.length === 0" class="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto">
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

      <!-- Empty -->
      <div v-else-if="overview.length === 0" class="flex items-center justify-center h-full">
        <p class="text-gray-400 text-xl">No active services right now</p>
      </div>

      <!-- Grid -->
      <div
        v-else
        class="flex-1 min-h-0 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 auto-rows-fr gap-3"
      >
        <div
          v-for="q in overview"
          :key="q.queue_id"
          class="bg-white border border-gray-100 shadow-soft rounded-2xl p-3 flex flex-col items-center justify-center text-center min-h-0"
        >
          <h2 class="text-[clamp(0.65rem,1.4vh,0.9rem)] font-semibold tracking-[0.2em] text-gray-400 uppercase mb-2">{{ q.queue_name }}</h2>

          <div class="mb-2">
            <p class="text-[clamp(0.6rem,1.3vh,0.85rem)] font-bold uppercase tracking-wide text-gray-500 mb-1">Now Serving</p>
            <div v-if="q.serving_ticket_codes.length > 0" class="flex flex-wrap justify-center gap-2">
              <span
                v-for="code in q.serving_ticket_codes"
                :key="code"
                class="inline-block bg-gradient-to-br from-bsu-primary to-bsu-peach rounded-xl px-4 py-2 text-[clamp(1.5rem,5.5vh,3rem)] font-extrabold text-white tabular-nums drop-shadow"
              >
                {{ code }}
              </span>
            </div>
            <span v-else class="inline-block bg-bsu-surface border border-gray-100 rounded-xl px-4 py-2 text-[clamp(1.5rem,5.5vh,3rem)] font-extrabold text-gray-300">
              --
            </span>
          </div>

          <div class="flex items-center justify-center space-x-4 text-[clamp(0.65rem,1.3vh,0.875rem)]">
            <div>
              <p class="text-gray-400">Waiting</p>
              <p class="font-bold tabular-nums text-bsu-ink">{{ q.waiting_count }}</p>
            </div>
            <div>
              <p class="text-gray-400">Next</p>
              <p class="font-bold tabular-nums text-bsu-ink">{{ q.next_ticket_code ?? '--' }}</p>
            </div>
          </div>
        </div>
      </div>
    </main>

    <MediaAnnouncementPanel :media-max-height-vh="26" class="shrink-0" />

    <footer class="text-center py-1.5 text-xs text-gray-400 border-t border-gray-100 shrink-0">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
import MediaAnnouncementPanel from '@/components/MediaAnnouncementPanel.vue'
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

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
