<template>
  <div>
    <!-- Media Panel -->
    <section v-if="mediaItems.length > 0 && currentItem" class="mt-2 px-8 flex justify-center">
      <div
        class="max-w-full aspect-video rounded-2xl overflow-hidden border border-white/10 bg-black flex items-center justify-center"
        :style="mediaBoxStyle"
      >
        <img
          v-if="currentItem.media_type === 'image'"
          :src="currentItem.url"
          :alt="`Media item ${currentItem.id}`"
          class="w-full h-full object-contain"
        />
        <video
          v-else-if="currentItem.source === 'upload'"
          :key="currentItem.id"
          :src="currentItem.url"
          class="w-full h-full object-contain"
          autoplay
          muted
          loop
          playsinline
        ></video>
        <iframe
          v-else
          :src="currentItem.url"
          class="w-full h-full"
          frameborder="0"
          allow="autoplay; encrypted-media"
          allowfullscreen
        ></iframe>
      </div>
    </section>

    <!-- Announcement Ticker -->
    <div v-if="tickerText" class="mt-2 bg-bsu-gold text-gray-900 overflow-hidden py-1.5">
      <div class="whitespace-nowrap inline-block animate-marquee font-semibold px-4 text-sm">
        {{ tickerText }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'

const props = defineProps({
  // Caps the media box's height as a fraction of the viewport, so the same
  // panel can sit comfortably under a single-queue board (more room) or the
  // denser all-queues overview grid (less room) without either scrolling.
  mediaMaxHeightVh: {
    type: Number,
    default: 45,
  },
})

const queueStore = useQueueStore()

const mediaBoxStyle = computed(() => ({ height: `calc(${props.mediaMaxHeightVh}vh - 3rem)` }))

const currentIndex = ref(0)
let rotationTimer = null
let refreshTimer = null

const mediaItems = computed(() => queueStore.activeMediaItems)
const currentItem = computed(() => mediaItems.value[currentIndex.value] || null)

const announcements = computed(() => queueStore.activeAnnouncements)
const tickerText = computed(() =>
  announcements.value.length > 0
    ? announcements.value.map((a) => a.text).join('     •     ')
    : ''
)

const scheduleNextRotation = () => {
  if (rotationTimer) clearTimeout(rotationTimer)
  if (mediaItems.value.length === 0) return
  const duration = (currentItem.value?.display_duration_seconds || 10) * 1000
  rotationTimer = setTimeout(() => {
    currentIndex.value = (currentIndex.value + 1) % mediaItems.value.length
    scheduleNextRotation()
  }, duration)
}

const refreshContent = async () => {
  const hadItems = mediaItems.value.length > 0
  try {
    await queueStore.fetchActiveMediaItems()
    await queueStore.fetchActiveAnnouncements()
  } catch (err) {
    // Fail silent - this is a non-critical decorative panel on a live public screen;
    // the core "now serving" content must never be blocked or hidden by this failing.
  }
  if (mediaItems.value.length === 0) {
    if (rotationTimer) clearTimeout(rotationTimer)
    currentIndex.value = 0
  } else if (currentIndex.value >= mediaItems.value.length) {
    currentIndex.value = 0
  }
  if (!hadItems && mediaItems.value.length > 0) {
    scheduleNextRotation()
  }
}

onMounted(async () => {
  await refreshContent()
  if (mediaItems.value.length > 0) {
    scheduleNextRotation()
  }
  refreshTimer = setInterval(refreshContent, 30000)
})

onUnmounted(() => {
  if (rotationTimer) clearTimeout(rotationTimer)
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
@keyframes marquee {
  0% { transform: translateX(100vw); }
  100% { transform: translateX(-100%); }
}
.animate-marquee {
  animation: marquee 20s linear infinite;
}
</style>
