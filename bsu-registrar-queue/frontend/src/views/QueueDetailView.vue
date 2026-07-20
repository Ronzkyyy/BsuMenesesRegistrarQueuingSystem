<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <AppHeader subtitle="Queue Details">
      <template #actions>
        <button
          @click="goBack"
          class="hidden md:inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-bsu-primary bg-bsu-gold hover:bg-yellow-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-gold"
        >
          <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
      </template>
    </AppHeader>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
      <!-- Loading State -->
      <div v-if="loading && !queue" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-4 border-bsu-primary border-t-transparent"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error && !queue" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center mb-6">
        <svg class="mx-auto h-12 w-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-red-800">Error</h3>
        <p class="mt-1 text-sm text-red-700">{{ error }}</p>
        <button
          @click="fetchQueue"
          class="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800"
        >
          Try Again
        </button>
      </div>

      <!-- Queue Not Found -->
      <div v-else-if="!queue" class="text-center py-12">
        <svg class="mx-auto h-16 w-16 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-5.586a1 1 0 01-.707-.293L9 5z" />
        </svg>
        <h3 class="mt-4 text-lg font-medium text-gray-900">Queue Not Found</h3>
        <p class="mt-2 text-gray-500">The requested queue service does not exist.</p>
        <button
          @click="goToQueues"
          class="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800"
        >
          Browse Services
        </button>
      </div>

      <!-- Queue Details View -->
      <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Queue Information Card -->
        <div class="lg:col-span-1">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 p-6">
              <h2 class="text-xl font-bold text-gray-900">Service Details</h2>
            </div>
            <div class="p-6 space-y-4">
              <div class="flex items-center space-x-3">
                <component :is="getQueueIcon(queue.queue_type)" class="w-12 h-12 text-bsu-primary" />
                <div>
                  <h3 class="text-lg font-bold text-gray-900">{{ queue.name }}</h3>
                  <p class="text-sm text-gray-500">{{ formatQueueType(queue.queue_type) }}</p>
                </div>
              </div>

              <p class="text-gray-600">{{ queue.description || 'No description available' }}</p>

              <div class="border-t border-gray-100 pt-4 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm text-gray-500">Status</span>
                  <StatusBadge :status="queue.status" />
                </div>

                <div class="flex items-center justify-between">
                  <span class="text-sm text-gray-500">Slot Duration</span>
                  <span class="font-medium text-gray-900">{{ queue.slot_duration_minutes }} minutes</span>
                </div>

                <div class="flex items-center justify-between">
                  <span class="text-sm text-gray-500">Queue Capacity</span>
                  <span class="font-medium text-gray-900">{{ queue.max_capacity }} students</span>
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
              </div>
            </div>
          </div>
        </div>

        <!-- Ticket Status or Take Ticket -->
        <div class="lg:col-span-2">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 p-6">
              <h2 class="text-xl font-bold text-gray-900">
                {{ hasActiveTicket ? 'Your Ticket' : 'Take a Ticket' }}
              </h2>
            </div>

            <div class="p-6">
              <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <p class="text-sm text-red-700">{{ error }}</p>
              </div>

              <!-- Active Ticket Display -->
              <div v-if="hasActiveTicket && myTicket">
                <div class="text-center mb-6">
                  <div class="inline-flex items-center justify-center w-20 h-20 bg-bsu-primary text-white rounded-full mb-4">
                    <span class="text-3xl font-bold">{{ myTicket.ticket_code }}</span>
                  </div>
                  <h3 class="text-lg font-bold text-gray-900">Your Ticket Number</h3>
                  <p class="text-gray-500">Queue: {{ queue.name }}</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div class="bg-gray-50 rounded-lg p-4 text-center">
                    <p class="text-sm text-gray-500 mb-1">Position</p>
                    <p class="text-2xl font-bold text-bsu-primary">
                      {{ myTicket.position || 0 }}
                    </p>
                  </div>

                  <div class="bg-gray-50 rounded-lg p-4 text-center">
                    <p class="text-sm text-gray-500 mb-1">Estimated Wait</p>
                    <p class="text-2xl font-bold text-bsu-gold">
                      {{ myTicket.estimated_wait_time_minutes || 0 }} min
                    </p>
                  </div>
                </div>

                <div class="bg-gray-50 rounded-lg p-4 mb-6">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-gray-600 text-sm">Status</span>
                    <StatusBadge :status="myTicket.status" />
                  </div>

                  <div v-if="myTicket.priority !== 'normal'" class="flex items-center justify-between">
                    <span class="text-gray-600 text-sm">Priority</span>
                    <span class="text-gray-900 font-medium capitalize">{{ myTicket.priority }}</span>
                  </div>
                </div>

                <div class="flex flex-col sm:flex-row gap-3">
                  <button
                    v-if="myTicket.status === 'waiting'"
                    @click="cancelTicket"
                    :disabled="loading"
                    class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                  >
                    Cancel Ticket
                  </button>

                  <button
                    v-if="myTicket.status === 'waiting'"
                    @click="refreshTicket"
                    :disabled="loading"
                    class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
                  >
                    Refresh
                  </button>

                  <button
                    v-if="['completed', 'cancelled', 'no_show'].includes(myTicket.status)"
                    @click="takeTicket"
                    :disabled="loading"
                    class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
                  >
                    Take New Ticket
                  </button>
                </div>

                <div class="flex flex-col sm:flex-row gap-3 mt-3">
                  <button
                    @click="takeAnotherTicket"
                    :disabled="loading"
                    class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-bsu-primary text-sm font-medium rounded-md text-bsu-primary bg-white hover:bg-bsu-primary/5 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
                  >
                    Take Another Ticket (Different Service)
                  </button>

                  <button
                    @click="viewAllMyTickets"
                    :disabled="loading"
                    class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
                  >
                    View All My Tickets
                  </button>
                </div>
              </div>

              <!-- No Active Ticket - Take Ticket Form -->
              <div v-else>
                <div v-if="queue.status !== 'active'" class="text-center py-8">
                  <svg class="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p class="mt-2 text-gray-500">This queue is currently {{ queue.status }}. Please check back later.</p>
                </div>

                <div v-else class="space-y-4">
                  <!-- Student Search/Registration -->
                  <div v-if="!currentStudentId">
                    <h3 class="text-lg font-medium text-gray-900 mb-3">Student Identification</h3>

                    <div class="space-y-3">
                      <div>
                        <label for="studentId" class="block text-sm font-medium text-gray-700 mb-1">
                          Student ID
                        </label>
                        <div class="relative">
                          <input
                            id="studentId"
                            v-model="studentIdInput"
                            type="text"
                            inputmode="numeric"
                            maxlength="10"
                            placeholder="Enter your 10-digit student number (e.g., 2020201163)"
                            class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                            @keyup.enter="searchOrRegisterStudent"
                          />
                          <button
                            @click="searchOrRegisterStudent"
                            :disabled="loading"
                            class="absolute inset-y-0 right-0 px-4 py-2 bg-bsu-primary text-white rounded-r-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
                          >
                            <svg v-if="!loading" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.354-4.354A7 7 0 1010.5 3a7 7 0 009.5 7.646z" />
                            </svg>
                            <svg v-else class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      <div v-if="notFound" class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <p class="text-sm text-yellow-800 mb-3">Student not found in the system.</p>
                        <button
                          @click="showRegistrationModal = true"
                          class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-yellow-600 hover:bg-yellow-700"
                        >
                          Register New Student
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- Take Ticket Button (if student is registered) -->
                  <div v-else>
                    <div class="text-center mb-4">
                      <p class="text-gray-600 mb-2">Ready to take your ticket, {{ queueStore.studentFullName }}?</p>
                      <p class="text-sm text-gray-500">
                        Queue: <span class="font-medium text-gray-900">{{ queue.name }}</span>
                      </p>
                    </div>

                    <button
                      @click="takeTicket"
                      :disabled="loading"
                      class="w-full py-3 px-4 text-lg font-medium text-white bg-bsu-primary rounded-lg hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary focus:ring-offset-2 disabled:opacity-50"
                    >
                      <span v-if="!loading">Take Ticket</span>
                      <span v-else>Processing...</span>
                    </button>

                    <button
                      @click="viewAllMyTickets"
                      :disabled="loading"
                      class="w-full mt-3 py-2 px-4 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-bsu-primary focus:ring-offset-2 disabled:opacity-50"
                    >
                      View All My Tickets
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Registration Modal -->
      <div v-if="showRegistrationModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
          <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-bold text-gray-900">Register New Student</h3>
          </div>
          <div class="px-6 py-4 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                <input
                  v-model="registrationForm.first_name"
                  type="text"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                <input
                  v-model="registrationForm.last_name"
                  type="text"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                />
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                v-model="registrationForm.email"
                type="email"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
              />
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Course</label>
                <select
                  v-model="registrationForm.course"
                  @change="onCourseChange"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                >
                  <option :value="course.value" v-for="course in courseOptions" :key="course.value">
                    {{ course.label }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Year Level</label>
                <select
                  v-model="registrationForm.year_level"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                >
                  <option :value="year.value" v-for="year in yearLevelOptions" :key="year.value">
                    {{ year.label }}
                  </option>
                </select>
              </div>
            </div>

            <div v-if="isBitCourse">
              <label class="block text-sm font-medium text-gray-700 mb-1">Major</label>
              <select
                v-model="registrationForm.major"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
              >
                <option :value="null" disabled>Select a major</option>
                <option :value="major.value" v-for="major in majorOptions" :key="major.value">
                  {{ major.label }}
                </option>
              </select>
            </div>

            <div class="space-y-3">
              <div class="flex items-center">
                <input
                  id="is_scholar"
                  type="checkbox"
                  v-model="registrationForm.is_scholar"
                  class="h-4 w-4 text-bsu-primary border-gray-300 rounded"
                />
                <label for="is_scholar" class="ml-2 text-sm text-gray-700">Scholar</label>
              </div>

              <div class="flex items-center">
                <input
                  id="is_varsity"
                  type="checkbox"
                  v-model="registrationForm.is_varsity"
                  class="h-4 w-4 text-bsu-primary border-gray-300 rounded"
                />
                <label for="is_varsity" class="ml-2 text-sm text-gray-700">Varsity Athlete</label>
              </div>

              <div class="flex items-center">
                <input
                  id="is_graduating"
                  type="checkbox"
                  v-model="registrationForm.is_graduating"
                  class="h-4 w-4 text-bsu-primary border-gray-300 rounded"
                />
                <label for="is_graduating" class="ml-2 text-sm text-gray-700">Graduating Student</label>
              </div>
            </div>
          </div>

          <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button
              @click="showRegistrationModal = false"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
            >
              Cancel
            </button>
            <button
              @click="registerStudent"
              :disabled="loading"
              class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              Register
            </button>
          </div>
        </div>
      </div>

      <!-- My Tickets Modal -->
      <div v-if="showMyTicketsModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
          <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-bold text-gray-900">My Active Tickets</h3>
          </div>
          <div class="px-6 py-4 space-y-3 max-h-96 overflow-y-auto">
            <div v-if="queueStore.myTickets.length === 0" class="text-center text-gray-500 py-4">
              You have no active tickets right now.
            </div>
            <div
              v-for="t in queueStore.myTickets"
              :key="t.id"
              class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-200 bg-gray-50"
            >
              <div>
                <p class="font-medium text-gray-900">{{ t.queue_name }}</p>
                <p class="text-sm text-gray-500">Ticket {{ t.ticket_code }} &middot; Position {{ t.position }}</p>
              </div>
              <StatusBadge :status="t.status" />
            </div>
          </div>
          <div class="px-6 py-4 border-t border-gray-200 flex justify-end">
            <button
              @click="showMyTicketsModal = false"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </main>

    <AppFooter />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQueueStore } from '@/stores/queue'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { getQueueIcon, formatQueueType } from '@/components/icons/QueueIcons'

const router = useRouter()
const route = useRoute()
const queueStore = useQueueStore()

const queueId = parseInt(route.params.id)

// State
const loading = ref(false)
const error = ref(null)
const queue = ref(null)
const currentStudentId = ref(null)
const studentIdInput = ref('')
const notFound = ref(false)
const showRegistrationModal = ref(false)

// Registration form
const registrationForm = ref({
  student_id: '',
  first_name: '',
  last_name: '',
  email: '',
  student_type: 'undergraduate',
  course: 'Bachelor of Science in Information Technology',
  major: null,
  year_level: '1st_year',
  is_scholar: false,
  is_varsity: false,
  is_graduating: false,
})

const BIT_COURSE_VALUE = 'Bachelor of Industrial Technology'

const courseOptions = [
  { value: 'Bachelor of Science in Information Technology', label: 'BS Information Technology' },
  { value: 'Bachelor of Science in Hospitality Management', label: 'BS Hospitality Management' },
  { value: 'Bachelor of Science in Business Administration', label: 'BS Business Administration' },
  { value: BIT_COURSE_VALUE, label: 'Bachelor of Industrial Technology (BIT)' },
]

const majorOptions = [
  { value: 'BIT Computer Technology', label: 'BIT Computer Technology' },
  { value: 'Food Processing Technology', label: 'Food Processing Technology' },
]

const isBitCourse = computed(() => registrationForm.value.course === BIT_COURSE_VALUE)

const onCourseChange = () => {
  if (!isBitCourse.value) {
    registrationForm.value.major = null
  }
}

const yearLevelOptions = [
  { value: '1st_year', label: '1st Year' },
  { value: '2nd_year', label: '2nd Year' },
  { value: '3rd_year', label: '3rd Year' },
  { value: '4th_year', label: '4th Year' },
  { value: '5th_year', label: '5th Year' },
  { value: 'graduate', label: 'Graduate' },
]

// Computed
const hasActiveTicket = computed(() => {
  return queueStore.myTicket && !['completed', 'cancelled', 'no_show'].includes(queueStore.myTicket.status)
})

const myTicket = computed(() => queueStore.myTicket)

// Navigation
const goBack = () => router.back()
const goToQueues = () => router.push('/queues')

// Fetch queue data
const fetchQueue = async () => {
  loading.value = true
  error.value = null
  try {
    await queueStore.fetchQueueById(queueId)
    queue.value = queueStore.currentQueue
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load queue details'
  } finally {
    loading.value = false
  }
}

// Search or register student
const searchOrRegisterStudent = async () => {
  if (!studentIdInput.value.trim()) return

  loading.value = true
  notFound.value = false
  error.value = null

  try {
    await queueStore.searchStudent(studentIdInput.value.trim())
    currentStudentId.value = queueStore.currentStudent?.id
    if (!queueStore.currentStudent) {
      notFound.value = true
      registrationForm.value.student_id = studentIdInput.value.trim()
    } else {
      await checkExistingTicket()
    }
  } catch (err) {
    notFound.value = true
    registrationForm.value.student_id = studentIdInput.value.trim()
  } finally {
    loading.value = false
  }
}

// If this student already has an active ticket in this specific queue,
// pick it back up instead of offering to take a duplicate one
const checkExistingTicket = async () => {
  if (!currentStudentId.value) return
  try {
    await queueStore.fetchMyTicket(currentStudentId.value, queueId)
    if (queueStore.myTicket) {
      queueStore.startPollingMyTicket(currentStudentId.value, queueId)
    }
  } catch (err) {
    // no active ticket here yet - that's fine, they can take one
  }
}

// Take a ticket
const takeTicket = async () => {
  if (!currentStudentId.value) return

  loading.value = true
  error.value = null

  try {
    await queueStore.takeTicket(queueId, currentStudentId.value)
    queueStore.startPollingMyTicket(currentStudentId.value, queueId)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to take ticket'
  } finally {
    loading.value = false
  }
}

// Refresh the current ticket's position/wait time
const refreshTicket = async () => {
  if (!currentStudentId.value) return
  loading.value = true
  try {
    await queueStore.fetchMyTicket(currentStudentId.value, queueId)
  } catch (err) {
    // ignore - polling will retry
  } finally {
    loading.value = false
  }
}

// Go take a ticket in another queue - the student is already known
// (queueStore.currentStudent persists across client-side navigation), so
// the next queue page picks them up automatically without re-searching
const takeAnotherTicket = () => {
  router.push('/queues')
}

// My Tickets: all active tickets this student holds, across every queue
const showMyTicketsModal = ref(false)
const viewAllMyTickets = async () => {
  if (!currentStudentId.value) return
  await queueStore.fetchMyTickets(currentStudentId.value)
  showMyTicketsModal.value = true
}

// Cancel ticket
const cancelTicket = async () => {
  if (!myTicket.value) return

  loading.value = true
  error.value = null

  try {
    await queueStore.cancelTicket(myTicket.value.id)
    queueStore.stopPolling()
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to cancel ticket'
  } finally {
    loading.value = false
  }
}

// Register new student
const registerStudent = async () => {
  if (!registrationForm.value.first_name || !registrationForm.value.last_name || !registrationForm.value.email) {
    return
  }
  if (isBitCourse.value && !registrationForm.value.major) {
    error.value = 'Please select a major'
    return
  }

  loading.value = true
  error.value = null
  showRegistrationModal.value = false

  try {
    await queueStore.registerStudent(registrationForm.value)
    currentStudentId.value = queueStore.currentStudent?.id
    notFound.value = false
    await queueStore.takeTicket(queueId, queueStore.currentStudent.id)
    queueStore.startPollingMyTicket(queueStore.currentStudent.id, queueId)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to register student'
    showRegistrationModal.value = true
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchQueue()
  // Returning from another queue in the same session (e.g. "Take Another
  // Ticket") - the student is already known, no need to search again
  if (queueStore.currentStudent) {
    currentStudentId.value = queueStore.currentStudent.id
    await checkExistingTicket()
  }
})

onUnmounted(() => {
  queueStore.stopPolling()
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
