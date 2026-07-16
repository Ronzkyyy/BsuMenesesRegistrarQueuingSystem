<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <AppHeader subtitle="Display Board Selector">
      <template #actions>
        <router-link
          to="/"
          class="hidden md:inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-bsu-primary bg-bsu-gold hover:bg-yellow-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-gold"
        >
          Home
        </router-link>
      </template>
    </AppHeader>

    <main class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
      <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Queue Display Boards</h2>
        <p class="mt-2 text-gray-600">
          Pick a service to open its public "Now Serving" board — meant to be shown full-screen on a waiting-area TV or monitor.
        </p>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-4 border-bsu-primary border-t-transparent"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p class="text-red-700">{{ error }}</p>
        <button
          @click="fetchQueues"
          class="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800"
        >
          Try Again
        </button>
      </div>

      <!-- Empty State -->
      <div v-else-if="queues.length === 0" class="text-center py-12">
        <p class="text-gray-500">No active services to display right now.</p>
      </div>

      <!-- Queue List -->
      <div v-else class="space-y-3">
        <router-link
          v-for="queue in queues"
          :key="queue.id"
          :to="`/display/${queue.id}`"
          target="_blank"
          class="flex items-center justify-between bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-lg hover:border-bsu-primary/20 transition-all p-5"
        >
          <div class="flex items-center space-x-4">
            <component :is="getQueueIcon(queue.queue_type)" class="w-10 h-10 text-bsu-primary" />
            <div>
              <h3 class="text-lg font-bold text-gray-900">{{ queue.name }}</h3>
              <p class="text-sm text-gray-500">{{ formatQueueType(queue.queue_type) }}</p>
            </div>
          </div>
          <span class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-bsu-primary">
            Open Board
            <svg class="ml-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </span>
        </router-link>
      </div>
    </main>

    <AppFooter />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import { getQueueIcon, formatQueueType } from '@/components/icons/QueueIcons'

const queueStore = useQueueStore()

const loading = ref(true)
const error = ref(null)
const queues = ref([])

const fetchQueues = async () => {
  loading.value = true
  error.value = null
  try {
    await queueStore.fetchActiveQueues()
    queues.value = queueStore.activeQueues.filter(q => q.status === 'active')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load services. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchQueues()
})
</script>
