<template>
  <div class="h-screen overflow-hidden board-bg text-bsu-ink flex flex-col">
    <!-- Top bar -->
    <header class="flex items-center justify-between px-6 py-2.5 board-header shrink-0">
      <div class="flex items-center space-x-3">
        <div class="flex items-center space-x-1.5 university-badge">
          <img :src="BSUlogo" alt="BSU Logo" class="w-7 h-7 object-contain" />
          <img :src="MENESESlogo" alt="Meneses Campus Logo" class="w-7 h-7 object-contain" />
        </div>
        <div>
          <h1 class="text-sm font-extrabold leading-tight text-white tracking-tight">BSU Meneses Campus</h1>
          <p class="text-[0.65rem] text-white/70 font-semibold uppercase tracking-widest">All Queues Overview</p>
        </div>
      </div>
      <div class="flex items-center space-x-4">
        <div class="flex items-center space-x-2 text-white">
          <p class="text-lg font-bold tabular-nums leading-tight">{{ clockTime }}</p>
          <span class="w-1.5 h-1.5 rounded-full bg-bsu-gold"></span>
          <p class="text-xs text-white/70">{{ clockDate }}</p>
        </div>
        <button
          @click="toggleFullscreen"
          class="p-1.5 rounded-lg border border-white/30 text-white/80 hover:text-white hover:border-white/60 transition-colors"
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
        class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3"
      >
        <article
          v-for="q in overview"
          :key="q.queue_id"
          class="window-card flex flex-col text-center"
        >
          <div class="window-card-heading">
            <p class="window-name">
              {{ q.queue_name }}
              <span class="open-label">Open</span>
            </p>
            <p class="service-name">{{ formatQueueType(q.queue_type) }}</p>
          </div>

          <p class="serving-label">Now Serving</p>

          <p v-if="q.serving_ticket_codes.length > 0" class="served-ticket">
            {{ q.serving_ticket_codes.join(', ') }}
          </p>
          <p v-else class="served-ticket text-gray-300">--</p>

          <div class="queue-stats">
            <div>
              <p class="queue-stats-label">Waiting</p>
              <p class="queue-stats-value">{{ q.waiting_count }}</p>
            </div>
            <div>
              <p class="queue-stats-label">Next</p>
              <p class="queue-stats-value">{{ q.next_ticket_code ?? '--' }}</p>
            </div>
          </div>
        </article>
      </div>
    </main>

    <MediaAnnouncementPanel :media-max-height-vh="36" class="shrink-0" />

    <footer class="text-center py-1.5 text-xs text-gray-400 border-t border-gray-200 bg-white shrink-0 uppercase tracking-widest font-medium">
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
import { formatQueueType } from '@/components/icons/QueueIcons'
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

<style scoped>
.board-bg {
  font-family: 'Inter', sans-serif;
  background:
    linear-gradient(rgba(255, 255, 255, 0.35) 1px, transparent 1px),
    #e9eef7;
  background-size: 100% 2.5rem;
}

.board-header {
  background: linear-gradient(to right, #E85D8E, #F7A76C);
  border-bottom: 0.3rem solid #C94577;
  box-shadow: 0 6px 16px rgba(201, 69, 119, 0.25);
}

.university-badge {
  padding: 0.3rem 0.45rem;
  border-radius: 9999px;
  background: #F8C95A;
  border: 2px solid rgba(255, 255, 255, 0.75);
  box-shadow: inset 0 0 0 3px #C94577;
}

.window-card {
  position: relative;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #d5dce8;
  border-radius: 0.35rem;
  box-shadow: 0 6px 16px rgba(45, 58, 79, 0.1);
}

.window-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 1rem;
  height: 1rem;
  background: #F8C95A;
  clip-path: polygon(0 0, 100% 0, 0 100%);
}

.window-card-heading {
  display: flex;
  min-height: 3.2rem;
  flex: none;
  flex-direction: column;
  justify-content: center;
  padding: 0.55rem 0.6rem 0.4rem;
}

.window-name {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  margin: 0;
  color: #4c1820;
  font-size: clamp(0.68rem, 1.5vh, 0.95rem);
  font-weight: 900;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.open-label {
  color: #26945a;
  font-size: 0.6em;
  font-weight: 800;
  letter-spacing: 0;
}

.service-name {
  overflow: hidden;
  margin: 0.2rem 0 0;
  color: #8b929f;
  font-size: clamp(0.5rem, 1vh, 0.62rem);
  font-weight: 700;
  letter-spacing: 0.1em;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}

.serving-label {
  flex: none;
  margin: 0;
  padding: 0.3rem 0.5rem;
  background: #e0c71b;
  color: #211d16;
  font-size: clamp(0.55rem, 1vh, 0.7rem);
  font-weight: 900;
  line-height: 1;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.served-ticket {
  margin: 0;
  padding: 0.85rem 0.6rem;
  color: #171d29;
  font-size: clamp(1.3rem, 5vh, 2.3rem);
  font-weight: 700;
  letter-spacing: 0.05em;
  line-height: 1;
}

.queue-stats {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  padding: 0.5rem 0.6rem 0.6rem;
  border-top: 1px solid #ebeef4;
}

.queue-stats-label {
  margin: 0;
  color: #9aa1ad;
  font-size: clamp(0.52rem, 1vh, 0.65rem);
}

.queue-stats-value {
  margin: 0;
  color: #2d2d2d;
  font-weight: 700;
  font-size: clamp(0.62rem, 1.2vh, 0.78rem);
  font-variant-numeric: tabular-nums;
}
</style>
