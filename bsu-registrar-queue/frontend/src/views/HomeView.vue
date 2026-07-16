<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <AppHeader subtitle="Registrar Queue Management System">
      <template #actions>
        <router-link
          to="/admin"
          class="hidden md:inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-bsu-primary bg-bsu-gold hover:bg-yellow-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-gold"
        >
          Admin Dashboard
        </router-link>
      </template>
    </AppHeader>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
      <!-- Hero Section -->
      <section class="text-center mb-12">
        <h2 class="text-4xl font-bold text-gray-900 mb-4">Welcome to the Registrar Queue System</h2>
        <p class="text-xl text-gray-600 max-w-2xl mx-auto">
          Skip the line! Select a service below to get your digital queue ticket and track your position in real-time.
        </p>
        <router-link
          to="/queues"
          class="mt-6 inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary transition-colors"
        >
          Browse All Services
          <svg class="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </router-link>
      </section>

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-4 border-bsu-primary border-t-transparent"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <svg class="mx-auto h-12 w-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p class="mt-2 text-red-700">{{ error }}</p>
        <button
          @click="fetchQueues"
          class="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800"
        >
          <svg class="mr-2 -ml-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Try Again
        </button>
      </div>

      <!-- Queue Cards Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <router-link
          v-for="queue in queues"
          :key="queue.id"
          :to="`/queues/${queue.id}`"
          class="group relative bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-xl hover:border-bsu-primary/20 transition-all duration-300 overflow-hidden"
        >
          <!-- Queue Type Icon -->
          <div class="relative h-40 bg-gradient-to-br from-bsu-primary to-pink-700">
            <div class="absolute inset-0 bg-black/10"></div>
            <div class="absolute inset-0 flex items-center justify-center">
              <component :is="getQueueIcon(queue.queue_type)" class="w-16 h-16 text-white" />
            </div>
            <div class="absolute top-3 right-3">
              <StatusBadge :status="queue.status" solid />
            </div>
          </div>

          <!-- Queue Info -->
          <div class="p-6">
            <h3 class="text-xl font-bold text-gray-900 group-hover:text-bsu-primary transition-colors">
              {{ queue.name }}
            </h3>
            <p class="mt-2 text-gray-600 line-clamp-2">{{ queue.description }}</p>

            <div class="mt-4 space-y-2">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500">Capacity</span>
                <span class="font-medium text-gray-900">{{ queue.max_capacity }}</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500">Slot Duration</span>
                <span class="font-medium text-gray-900">{{ queue.slot_duration_minutes }} min</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500">Priority Access</span>
                <span class="font-medium" :class="queue.allow_priority ? 'text-green-600' : 'text-gray-400'">
                  {{ queue.allow_priority ? 'Enabled' : 'Disabled' }}
                </span>
              </div>
            </div>

            <div class="mt-4 pt-4 border-t border-gray-100">
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-bsu-primary/10 text-bsu-primary">
                {{ formatQueueType(queue.queue_type) }}
              </span>
            </div>
          </div>

          <!-- Arrow indicator -->
          <div class="absolute inset-0 flex items-center justify-end pr-4 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
            <svg class="w-6 h-6 text-bsu-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </router-link>

        <!-- Empty State -->
        <div v-if="queues.length === 0" class="col-span-full text-center py-12">
          <svg class="mx-auto h-16 w-16 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-gray-900">No Active Services</h3>
          <p class="mt-2 text-gray-500">There are currently no active queue services available.</p>
        </div>
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
import StatusBadge from '@/components/StatusBadge.vue'
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
    queues.value = queueStore.activeQueues
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

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
