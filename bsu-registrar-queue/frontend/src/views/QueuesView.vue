<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <AppHeader subtitle="Available Services">
      <template #actions>
        <router-link
          to="/"
          class="hidden md:inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-bsu-primary bg-bsu-gold hover:bg-yellow-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-gold"
        >
          <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Home
        </router-link>
      </template>
    </AppHeader>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
      <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Available Services</h2>
        <p class="mt-2 text-gray-600">Select a service to join the queue</p>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-4 border-bsu-primary border-t-transparent"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center mb-6">
        <svg class="mx-auto h-12 w-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-red-800">Error</h3>
        <p class="mt-1 text-sm text-red-700">{{ error }}</p>
        <button
          @click="fetchQueues"
          class="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800"
        >
          Try Again
        </button>
      </div>

      <!-- Empty State -->
      <div v-else-if="queues.length === 0" class="text-center py-12">
        <svg class="mx-auto h-16 w-16 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-5.586a1 1 0 01-.707-.293L9 5z" />
        </svg>
        <h3 class="mt-4 text-lg font-medium text-gray-900">No Services Available</h3>
        <p class="mt-2 text-gray-500">There are currently no active services available. Please check back later.</p>
      </div>

      <!-- Queue Cards Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="queue in queues"
          :key="queue.id"
          class="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-200 overflow-hidden"
        >
          <div class="relative bg-bsu-primary/5 border-b border-bsu-primary/10">
            <div class="px-6 py-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                  <component :is="getQueueIcon(queue.queue_type)" class="w-10 h-10 text-bsu-primary" />
                  <div>
                    <h3 class="text-xl font-bold text-gray-900">{{ queue.name }}</h3>
                    <p class="text-sm text-gray-500">{{ formatQueueType(queue.queue_type) }}</p>
                  </div>
                </div>
                <StatusBadge :status="queue.status" />
              </div>
            </div>
          </div>

          <div class="px-6 py-4">
            <p class="text-gray-600 text-sm line-clamp-2 mb-4">
              {{ queue.description || 'No description available' }}
            </p>

            <div class="space-y-3">
              <div class="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p class="text-lg font-bold text-bsu-primary">{{ queue.current_ticket_number || 0 }}</p>
                  <p class="text-xs text-gray-500 uppercase">Tickets Issued</p>
                </div>
                <div>
                  <p class="text-lg font-bold text-bsu-primary">{{ queue.max_capacity }}</p>
                  <p class="text-xs text-gray-500 uppercase">Capacity</p>
                </div>
                <div>
                  <p class="text-lg font-bold text-bsu-primary">{{ queue.slot_duration_minutes }}m</p>
                  <p class="text-xs text-gray-500 uppercase">Slot Time</p>
                </div>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-500">Priority Access</span>
                <span
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                  :class="queue.allow_priority ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'"
                >
                  {{ queue.allow_priority ? 'Available' : 'Not Available' }}
                </span>
              </div>

              <button
                v-if="queue.status === 'active'"
                @click="goToQueueDetail(queue.id)"
                class="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary transition-colors"
              >
                Join Queue
                <svg class="ml-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </button>
              <button
                v-else
                class="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-gray-500 bg-gray-100 cursor-not-allowed"
                disabled
              >
                Service Unavailable
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <AppFooter />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQueueStore } from '@/stores/queue'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { getQueueIcon, formatQueueType } from '@/components/icons/QueueIcons'

const router = useRouter()
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

const goToQueueDetail = (queueId) => {
  router.push(`/queues/${queueId}`)
}

onMounted(() => {
  fetchQueues()
})
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
