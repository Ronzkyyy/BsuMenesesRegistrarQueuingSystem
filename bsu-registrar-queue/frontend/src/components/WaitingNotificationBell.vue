<template>
  <div class="relative" ref="rootEl">
    <button
      type="button"
      class="relative p-2 rounded-xl text-gray-500 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark transition-colors"
      :aria-expanded="open"
      aria-label="Waiting tickets"
      @click="open = !open"
    >
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
      </svg>
      <span
        v-if="summary.total > 0"
        class="absolute -top-0.5 -right-0.5 min-w-[1.1rem] h-[1.1rem] px-1 flex items-center justify-center rounded-full bg-red-500 text-white text-[0.65rem] font-bold leading-none"
      >
        {{ summary.total }}
      </span>
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="open"
        class="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-soft-lg border border-gray-100 py-2 z-50"
      >
        <p class="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Waiting ({{ summary.total }})
        </p>
        <p v-if="summary.byQueue.length === 0" class="px-4 py-2 text-sm text-gray-500">
          Nothing waiting right now.
        </p>
        <router-link
          v-for="q in summary.byQueue"
          :key="q.queue_id"
          to="/admin/counter"
          class="flex items-center justify-between px-4 py-2 text-sm text-gray-700 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark transition-colors"
          @click="open = false"
        >
          <span>{{ q.queue_name }}</span>
          <span class="font-semibold">{{ q.waiting_count }}</span>
        </router-link>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { summarizeWaiting } from '@/services/waitingSummary'

const queueStore = useQueueStore()
const open = ref(false)
const rootEl = ref(null)

const summary = computed(() => summarizeWaiting(queueStore.nowServingOverview))

// If the count drops to zero while the dropdown is open (e.g. the last
// waiting ticket was served from another tab), close it rather than leave
// an empty dropdown open with a now-hidden bell badge behind it.
watch(() => summary.value.total, (total) => {
  if (total === 0) open.value = false
})

const onDocumentClick = (event) => {
  if (open.value && rootEl.value && !rootEl.value.contains(event.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => document.removeEventListener('click', onDocumentClick))
</script>
