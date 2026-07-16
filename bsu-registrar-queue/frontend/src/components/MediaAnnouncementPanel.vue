<template>
  <div>
    <!-- Media Panel -->
    <section v-if="mediaItems.length > 0 && currentItem" class="mt-10 max-w-5xl mx-auto px-8">
      <div class="rounded-2xl overflow-hidden border border-white/10 bg-black aspect-video flex items-center justify-center">
        <img
          v-if="currentItem.media_type === 'image'"
          :src="currentItem.url"
          :alt="`Media item ${currentItem.id}`"
          class="w-full h-full object-contain"
        />
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
    <div v-if="tickerText" class="mt-6 bg-bsu-gold text-gray-900 overflow-hidden py-2">
      <div class="whitespace-nowrap inline-block animate-marquee font-semibold px-4">
        {{ tickerText }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()

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
