<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <AppHeader subtitle="Registrar Staff Dashboard">
      <template #actions>
        <template v-if="queueStore.isAuthenticated">
          <span class="hidden md:block text-sm text-pink-100">
            Logged in as: {{ queueStore.currentUser?.full_name || queueStore.currentUser?.username || 'Staff' }}
          </span>
          <button
            @click="logout"
            class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            Logout
          </button>
        </template>
      </template>
    </AppHeader>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
      <!-- Login Form (if not authenticated) -->
      <div v-if="!queueStore.isAuthenticated" class="max-w-md mx-auto">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 p-6">
            <h2 class="text-2xl font-bold text-gray-900">Staff Login</h2>
            <p class="mt-1 text-gray-600">Access the registrar dashboard</p>
          </div>
          <div class="p-6">
            <form @submit.prevent="handleLogin" class="space-y-4">
              <div>
                <label for="username" class="block text-sm font-medium text-gray-700 mb-1">
                  Username
                </label>
                <input
                  id="username"
                  v-model="loginForm.username"
                  type="text"
                  required
                  autocomplete="username"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                  placeholder="Enter your username"
                />
              </div>

              <div>
                <label for="password" class="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <input
                  id="password"
                  v-model="loginForm.password"
                  type="password"
                  required
                  autocomplete="current-password"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                  placeholder="Enter your password"
                />
              </div>

              <button
                type="submit"
                :disabled="loading"
                class="w-full py-2 px-4 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
              >
                <span v-if="!loading">Login</span>
                <span v-else>Logging in...</span>
              </button>
            </form>

            <div v-if="loginError" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p class="text-sm text-red-700">{{ loginError }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Dashboard Content (if authenticated) -->
      <div v-else>
        <div class="mb-8">
          <h2 class="text-3xl font-bold text-gray-900">Staff Dashboard</h2>
          <p class="mt-2 text-gray-600">Manage queues and serve tickets</p>
        </div>

        <!-- Stats Overview -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div class="flex items-center">
              <div class="p-3 bg-bsu-primary/10 rounded-full">
                <svg class="w-6 h-6 text-bsu-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-5.586a1 1 0 01-.707-.293L9 5z" />
                </svg>
              </div>
              <div class="ml-4">
                <p class="text-sm text-gray-500">Active Queues</p>
                <p class="text-2xl font-bold text-gray-900">{{ stats.activeQueues || 0 }}</p>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div class="flex items-center">
              <div class="p-3 bg-yellow-100 rounded-full">
                <svg class="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div class="ml-4">
                <p class="text-sm text-gray-500">Waiting Tickets</p>
                <p class="text-2xl font-bold text-gray-900">{{ stats.waitingTickets || 0 }}</p>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div class="flex items-center">
              <div class="p-3 bg-green-100 rounded-full">
                <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div class="ml-4">
                <p class="text-sm text-gray-500">Today's Completed</p>
                <p class="text-2xl font-bold text-gray-900">{{ stats.completedToday || 0 }}</p>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div class="flex items-center">
              <div class="p-3 bg-red-100 rounded-full">
                <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18 9l-3 3-3-3m0 6a3 3 0 00-3 3v1a3 3 0 006 0v-1a3 3 0 00-3-3z" />
                </svg>
              </div>
              <div class="ml-4">
                <p class="text-sm text-gray-500">No-Shows</p>
                <p class="text-2xl font-bold text-gray-900">{{ stats.noShows || 0 }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Error banner for dashboard-level failures -->
        <div v-if="dashboardError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p class="text-sm text-red-700">{{ dashboardError }}</p>
        </div>

        <!-- Queue Management Section -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 mb-6">
          <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4">
            <h3 class="text-xl font-bold text-gray-900">Queue Management</h3>
          </div>
          <div class="p-6">
            <div v-if="queues.length > 0" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div
                v-for="queue in queues"
                :key="queue.id"
                class="border border-gray-200 rounded-lg p-4"
              >
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center space-x-3">
                    <component :is="getQueueIcon(queue.queue_type)" class="w-8 h-8 text-bsu-primary" />
                    <div>
                      <h4 class="font-medium text-gray-900">{{ queue.name }}</h4>
                      <p class="text-sm text-gray-500">{{ formatQueueType(queue.queue_type) }}</p>
                    </div>
                  </div>
                  <StatusBadge :status="queue.status" />
                </div>

                <div class="text-sm text-gray-500 mb-3">
                  <p>Capacity: {{ queue.max_capacity }} | Slot: {{ queue.slot_duration_minutes }} min</p>
                </div>

                <div class="flex space-x-2">
                  <button
                    v-if="queue.status === 'active'"
                    @click="pauseQueue(queue.id)"
                    :disabled="loading"
                    class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-yellow-100 text-yellow-800 hover:bg-yellow-200 focus:outline-none focus:ring-2 focus:ring-yellow-500 disabled:opacity-50"
                  >
                    Pause
                  </button>
                  <button
                    v-else-if="queue.status === 'paused'"
                    @click="resumeQueue(queue.id)"
                    :disabled="loading"
                    class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-green-100 text-green-800 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                  >
                    Resume
                  </button>
                  <button
                    v-if="queue.status !== 'closed'"
                    @click="closeQueue(queue.id)"
                    :disabled="loading"
                    class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                  >
                    Close
                  </button>
                  <router-link
                    :to="`/display/${queue.id}`"
                    target="_blank"
                    class="flex-1 inline-flex justify-center items-center px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200"
                  >
                    Display Board
                  </router-link>
                  <button
                    @click="deleteQueue(queue.id)"
                    :disabled="loading"
                    class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-600 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>

            <div v-else class="text-center py-8">
              <svg class="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-5.586a1 1 0 01-.707-.293L9 5z" />
              </svg>
              <p class="mt-2 text-gray-500">No queues found. Create a new queue to get started.</p>
            </div>

            <div class="mt-6">
              <button
                @click="showCreateQueueModal = true"
                class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
              >
                <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                Create New Queue
              </button>
            </div>
          </div>
        </div>

        <!-- Queue Display Section -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 mb-6">
          <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
            <h3 class="text-xl font-bold text-gray-900">Queue Display</h3>
            <router-link to="/display" target="_blank" class="text-sm font-medium text-bsu-primary hover:underline">
              View All Boards ↗
            </router-link>
          </div>
          <div class="p-6">
            <div class="flex items-center justify-between mb-4">
              <h4 class="text-lg font-medium text-gray-900">{{ selectedQueue?.name || 'No queue selected' }}</h4>
              <select
                v-model="selectedQueueId"
                class="px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              >
                <option :value="null">Select Queue</option>
                <option :value="q.id" v-for="q in queues" :key="q.id">
                  {{ q.name }}
                </option>
              </select>
            </div>

            <div v-if="selectedQueue" class="space-y-4">
              <!-- Display Board -->
              <div class="bg-gray-50 rounded-lg p-6">
                <div class="text-center mb-6">
                  <h5 class="text-sm text-gray-500 uppercase tracking-wide">CURRENTLY SERVING</h5>
                  <div class="mt-2">
                    <span
                      v-if="servingTicket"
                      class="inline-block px-6 py-3 bg-bsu-primary text-white text-3xl font-bold rounded-full"
                    >
                      {{ servingTicket.ticket_number }}
                    </span>
                    <span
                      v-else
                      class="inline-block px-6 py-3 bg-gray-200 text-gray-600 text-3xl font-bold rounded-full"
                    >
                      --
                    </span>
                  </div>
                </div>

                <!-- Waiting Queue -->
                <div class="border-t border-gray-200 pt-4">
                  <h5 class="text-sm text-gray-500 uppercase tracking-wide mb-3">Waiting Queue</h5>
                  <div class="space-y-2">
                    <div
                      v-for="ticket in queueDisplay"
                      :key="ticket.id"
                      class="flex items-center justify-between px-3 py-2 rounded-md"
                      :class="ticket.priority === 'urgent' ? 'bg-red-50 border-l-4 border-red-400' : ticket.priority === 'priority' ? 'bg-yellow-50 border-l-4 border-yellow-400' : 'bg-white border border-gray-200'"
                    >
                      <div class="flex items-center space-x-3">
                        <span class="font-medium text-gray-900">#{{ ticket.ticket_number }}</span>
                        <span v-if="ticket.priority !== 'normal'" class="text-xs px-2 py-0.5 rounded-full"
                          :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
                        >
                          {{ ticket.priority }}
                        </span>
                      </div>
                      <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
                      </svg>
                    </div>

                    <div v-if="queueDisplay.length === 0" class="text-center py-4 text-gray-500">
                      No tickets waiting
                    </div>
                  </div>
                </div>
              </div>

              <!-- Control Buttons -->
              <div class="flex space-x-3 pt-4">
                <button
                  @click="serveNextTicket"
                  :disabled="loading || queueDisplay.length === 0"
                  class="flex-1 px-4 py-2 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
                >
                  <span v-if="!loading">Serve Next Ticket</span>
                  <span v-else>Processing...</span>
                </button>
                <button
                  @click="completeCurrentTicket"
                  :disabled="loading || !servingTicket"
                  class="flex-1 px-4 py-2 text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                >
                  <span v-if="!loading">Mark Complete</span>
                  <span v-else>Processing...</span>
                </button>
              </div>
            </div>
            <div v-else class="text-center py-8">
              <p class="text-gray-500">Select a queue to view the display board</p>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Create Queue Modal -->
    <div v-if="showCreateQueueModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">Create New Queue</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Queue Name</label>
            <input
              v-model="newQueueForm.name"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="e.g., Document Request"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Queue Type</label>
            <select
              v-model="newQueueForm.queue_type"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            >
              <option :value="type.value" v-for="type in queueTypeOptions" :key="type.value">
                {{ type.label }}
              </option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              v-model="newQueueForm.description"
              rows="2"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="Brief description of the service"
            ></textarea>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Max Capacity</label>
              <input
                v-model.number="newQueueForm.max_capacity"
                type="number"
                min="1"
                max="200"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Slot Duration (min)</label>
              <input
                v-model.number="newQueueForm.slot_duration_minutes"
                type="number"
                min="5"
                max="120"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
          </div>

          <div class="flex items-center">
            <input
              id="allow_priority"
              type="checkbox"
              v-model="newQueueForm.allow_priority"
              class="h-4 w-4 text-bsu-primary border-gray-300 rounded"
            />
            <label for="allow_priority" class="ml-2 text-sm text-gray-700">
              Allow Priority Access
            </label>
          </div>

          <div v-if="createQueueError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ createQueueError }}</p>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showCreateQueueModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="createQueue"
            :disabled="loading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>

    <AppFooter />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { getQueueIcon, formatQueueType } from '@/components/icons/QueueIcons'

const queueStore = useQueueStore()

// State
const loading = ref(false)
const loginError = ref('')
const dashboardError = ref('')
const createQueueError = ref('')
const showCreateQueueModal = ref(false)

// Queues
const queues = ref([])
const selectedQueueId = ref(null)
const selectedQueue = computed(() => queues.value.find(q => q.id === selectedQueueId.value))
const queueDisplay = ref([])
const servingTicket = ref(null)

// Stats
const stats = ref({
  activeQueues: 0,
  waitingTickets: 0,
  completedToday: 0,
  noShows: 0,
})

// Login form
const loginForm = ref({
  username: '',
  password: '',
})

// Create queue form
const newQueueForm = ref({
  name: '',
  queue_type: 'enrollment',
  description: '',
  max_capacity: 50,
  slot_duration_minutes: 30,
  allow_priority: true,
})

const queueTypeOptions = [
  { value: 'enrollment', label: 'Enrollment' },
  { value: 'document_request', label: 'Document Request' },
  { value: 'clearance', label: 'Clearance' },
  { value: 'scholarship', label: 'Scholarship' },
  { value: 'others', label: 'Others' },
]

// Login handler
const handleLogin = async () => {
  loading.value = true
  loginError.value = ''

  try {
    await queueStore.login(loginForm.value.username, loginForm.value.password)
    await fetchDashboardData()
  } catch (err) {
    loginError.value = err.response?.data?.detail || 'Login failed. Please check your credentials.'
  } finally {
    loading.value = false
  }
}

const logout = () => {
  queueStore.logout()
  queues.value = []
  selectedQueueId.value = null
  queueDisplay.value = []
  servingTicket.value = null
}

// Fetch dashboard data
const fetchDashboardData = async () => {
  dashboardError.value = ''
  try {
    await queueStore.fetchQueues()
    queues.value = queueStore.queues
    await fetchStats()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to load dashboard data'
  }
}

// Fetch statistics
const fetchStats = async () => {
  let totalWaiting = 0
  let totalCompleted = 0
  let totalNoShows = 0

  for (const queue of queues.value) {
    try {
      await queueStore.fetchQueueTickets(queue.id, 'waiting')
      totalWaiting += queueStore.queueTickets.length

      await queueStore.fetchQueueStats(queue.id)
      if (queueStore.queueStats) {
        totalCompleted += queueStore.queueStats.completed_today || 0
        totalNoShows += queueStore.queueStats.no_shows || 0
      }
    } catch (e) {
      // Continue with next queue
    }
  }

  stats.value = {
    activeQueues: queues.value.filter(q => q.status === 'active').length,
    waitingTickets: totalWaiting,
    completedToday: totalCompleted,
    noShows: totalNoShows,
  }
}

// Queue actions
const pauseQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.pauseQueue(queueId)
    await fetchDashboardData()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to pause queue'
  } finally {
    loading.value = false
  }
}

const resumeQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.resumeQueue(queueId)
    await fetchDashboardData()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to resume queue'
  } finally {
    loading.value = false
  }
}

const closeQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.closeQueue(queueId)
    await fetchDashboardData()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to close queue'
  } finally {
    loading.value = false
  }
}

const deleteQueue = async (queueId) => {
  if (!confirm('Are you sure you want to delete this queue? This cannot be undone.')) return
  loading.value = true
  try {
    await queueStore.deleteQueue(queueId)
    queues.value = queues.value.filter((q) => q.id !== queueId)
    await fetchDashboardData()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to delete queue'
  } finally {
    loading.value = false
  }
}

// Create queue
const createQueue = async () => {
  if (!newQueueForm.value.name) return

  loading.value = true
  createQueueError.value = ''
  try {
    await queueStore.createQueue(newQueueForm.value)
    showCreateQueueModal.value = false
    newQueueForm.value = {
      name: '',
      queue_type: 'enrollment',
      description: '',
      max_capacity: 50,
      slot_duration_minutes: 30,
      allow_priority: true,
    }
    await fetchDashboardData()
  } catch (err) {
    createQueueError.value = err.response?.data?.detail || 'Failed to create queue'
  } finally {
    loading.value = false
  }
}

// Serve next ticket
const serveNextTicket = async () => {
  if (!selectedQueueId.value) return

  loading.value = true
  try {
    const result = await queueStore.serveNextTicket(selectedQueueId.value)
    servingTicket.value = result
    await updateQueueDisplay()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'No waiting tickets'
  } finally {
    loading.value = false
  }
}

// Complete current ticket
const completeCurrentTicket = async () => {
  if (!servingTicket.value) return

  loading.value = true
  try {
    await queueStore.completeTicket(servingTicket.value.id)
    servingTicket.value = null
    await updateQueueDisplay()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to complete ticket'
  } finally {
    loading.value = false
  }
}

// Update queue display
const updateQueueDisplay = async () => {
  if (!selectedQueueId.value) return
  try {
    await queueStore.fetchQueueDisplay(selectedQueueId.value)
    queueDisplay.value = queueStore.queueDisplay.map(t => ({
      ...t,
      priority: t.priority || 'normal',
    }))
  } catch (err) {
    queueDisplay.value = []
  }
}

let displayRefreshTimer = null

// Lifecycle
onMounted(async () => {
  if (queueStore.isAuthenticated) {
    try {
      await queueStore.fetchCurrentUser()
      await fetchDashboardData()
    } catch (err) {
      // Token expired or invalid - force re-login
      queueStore.logout()
    }
  }

  displayRefreshTimer = setInterval(() => {
    if (queueStore.isAuthenticated && selectedQueueId.value) {
      updateQueueDisplay()
    }
  }, 5000)
})

onUnmounted(() => {
  if (displayRefreshTimer) clearInterval(displayRefreshTimer)
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
