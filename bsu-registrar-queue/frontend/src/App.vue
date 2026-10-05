<template>
  <router-view />

  <!-- Shown while requests wait for the (free-tier) backend to wake up -->
  <div
    v-if="queueStore.serverWaking"
    role="status"
    aria-live="polite"
    class="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-full bg-white shadow-soft-lg border border-gray-100 text-sm font-medium text-bsu-ink max-w-[calc(100vw-2rem)]"
  >
    <span class="w-4 h-4 shrink-0 rounded-full border-2 border-bsu-primary border-t-transparent animate-spin"></span>
    Starting up the server, please wait&hellip;
  </div>
</template>

<script setup>
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()
</script>
