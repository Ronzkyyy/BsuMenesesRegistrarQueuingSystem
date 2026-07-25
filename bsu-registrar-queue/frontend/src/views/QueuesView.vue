<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center relative overflow-hidden px-4 py-10">
    <div class="absolute -top-16 -left-16 w-72 h-72 bg-bsu-primary/10 rounded-full blur-3xl"></div>
    <div class="absolute top-1/3 -right-16 w-80 h-80 bg-bsu-gold/10 rounded-full blur-3xl"></div>

    <div class="relative z-10 w-full max-w-4xl bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
      <div class="p-8">
        <!-- Header (logos + step badge) -->
        <div class="flex flex-col items-center text-center mb-6">
          <div v-if="!showMyQueueStatus" class="inline-flex items-center px-3 py-1 rounded-full bg-bsu-primary text-white text-xs font-bold mb-3">
            STEP {{ displayedStep }}: {{ stepLabels[displayedStep] }}
          </div>
          <div class="flex items-center space-x-2 mb-3">
            <img :src="BSUlogo" alt="BSU Logo" class="w-14 h-14 object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="w-11 h-11 object-contain" />
          </div>
          <h1 class="text-2xl font-bold text-bsu-primary">BSU Registrar Queue System</h1>
          <p class="mt-1 text-sm text-gray-500">{{ headerSubtitle }}</p>
        </div>

        <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- Loading initial queues -->
        <div v-if="loadingQueues" class="flex justify-center py-12">
          <div class="animate-spin rounded-full h-10 w-10 border-4 border-bsu-primary border-t-transparent"></div>
        </div>

        <!-- Ticket status view (already has an active ticket) -->
        <div v-else-if="showMyQueueStatus">
          <div class="text-center mb-6">
            <div class="inline-flex items-center justify-center w-20 h-20 bg-bsu-primary text-white rounded-full mb-4">
              <span class="text-3xl font-bold">{{ myTicket?.ticket_code }}</span>
            </div>
            <h3 class="text-lg font-bold text-gray-900">Your Ticket Number</h3>
            <p class="text-gray-500">Queue: {{ myTicket?.queue_name }}</p>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div class="bg-gray-50 rounded-lg p-4 text-center">
              <p class="text-sm text-gray-500 mb-1">Position</p>
              <p class="text-2xl font-bold text-bsu-primary">{{ myTicket?.position || 0 }}</p>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
              <p class="text-sm text-gray-500 mb-1">Estimated Wait</p>
              <p class="text-2xl font-bold text-bsu-gold">{{ myTicket?.estimated_wait_time_minutes || 0 }} min</p>
            </div>
          </div>

          <div class="bg-gray-50 rounded-lg p-4 mb-6">
            <div class="flex items-center justify-between mb-2">
              <span class="text-gray-600 text-sm">Status</span>
              <StatusBadge :status="myTicket?.status" />
            </div>
            <div v-if="myTicket?.priority !== 'normal'" class="flex items-center justify-between">
              <span class="text-gray-600 text-sm">Priority</span>
              <span class="text-gray-900 font-medium capitalize">{{ myTicket?.priority }}</span>
            </div>
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <button
              v-if="myTicket?.status === 'waiting'"
              @click="cancelTicket"
              :disabled="loading"
              class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
            >
              Cancel Ticket
            </button>
            <button
              v-if="myTicket?.status === 'waiting'"
              @click="refreshTicket"
              :disabled="loading"
              class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          <div class="flex flex-col sm:flex-row gap-3 mt-3">
            <button
              @click="takeAnotherTicket"
              :disabled="loading"
              class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-bsu-primary text-sm font-medium rounded-md text-bsu-primary bg-white hover:bg-bsu-primary/5 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              Take Another Ticket
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

        <!-- STEP 1: Select a Service -->
        <div v-else-if="currentStep === 1">
          <p class="text-center text-gray-500 mb-6">Choose a service you want to request.</p>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <button
              v-for="service in SERVICES"
              :key="service.key"
              type="button"
              @click="selectService(service.key)"
              class="relative text-left p-4 rounded-xl border-2 transition-colors"
              :class="selectedServiceKey === service.key ? 'border-bsu-primary bg-bsu-primary/5' : 'border-gray-200 hover:border-bsu-primary/40'"
            >
              <div
                v-if="selectedServiceKey === service.key"
                class="absolute top-3 right-3 w-6 h-6 rounded-full bg-bsu-primary text-white flex items-center justify-center"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <component :is="service.icon" class="w-8 h-8 text-bsu-primary mb-3" />
              <h3 class="font-bold text-gray-900 mb-1">{{ service.label }}</h3>
              <p class="text-sm text-gray-500">{{ service.description }}</p>
            </button>
          </div>

          <div v-if="selectedServiceKey === 'request_documents'" class="mt-6">
            <label class="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
            <select
              v-model="selectedDocumentType"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
            >
              <option value="" disabled>Select a document type</option>
              <option v-for="dt in DOCUMENT_TYPES" :key="dt.value" :value="dt.value">{{ dt.label }}</option>
            </select>
          </div>

          <div v-if="selectedServiceKey === 'others'" class="mt-6">
            <label class="block text-sm font-medium text-gray-700 mb-1">Please specify your purpose</label>
            <textarea
              v-model="othersReason"
              rows="3"
              maxlength="200"
              placeholder="Describe your concern"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
            ></textarea>
          </div>

          <p v-if="selectedServiceKey && !selectedQueueId" class="text-sm text-red-600 mt-4">
            This service is currently unavailable. Please check back later.
          </p>
          <p v-if="!selectedServiceKey" class="text-sm text-gray-500 mt-6 text-center">
            Select a service above to continue.
          </p>

          <div class="flex justify-end mt-6">
            <button
              @click="goToStep2"
              :disabled="!canProceedStep1"
              class="px-6 py-2.5 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>

        <!-- STEP 2: Provide Information -->
        <div v-else-if="currentStep === 2">
          <div class="bg-bsu-primary/5 border border-bsu-primary/10 rounded-lg p-4 mb-6 flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <p class="text-xs font-medium text-bsu-primary uppercase">Selected Service</p>
              <p class="font-bold text-gray-900">{{ selectedService?.label }}</p>
            </div>
            <div v-if="selectedServiceKey === 'request_documents'">
              <p class="text-xs font-medium text-bsu-primary uppercase">Document Type</p>
              <p class="font-bold text-gray-900">{{ selectedDocumentTypeLabel }}</p>
            </div>
          </div>

          <h3 class="text-lg font-medium text-gray-900 mb-3">Student Information</h3>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Student Number</label>
              <div class="relative">
                <input
                  v-model="studentNumberInput"
                  type="text"
                  inputmode="numeric"
                  maxlength="10"
                  :disabled="studentLookedUp"
                  placeholder="Enter your 10-digit student number"
                  class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary disabled:bg-gray-100"
                  @keyup.enter="lookupStudent"
                />
                <button
                  v-if="!studentLookedUp"
                  @click="lookupStudent"
                  :disabled="loading"
                  class="absolute inset-y-0 right-0 px-4 py-2 bg-bsu-primary text-white rounded-r-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
                >
                  Check
                </button>
                <button
                  v-else
                  @click="resetStudentLookup"
                  type="button"
                  class="absolute inset-y-0 right-0 px-4 py-2 bg-gray-100 text-gray-600 rounded-r-md hover:bg-gray-200"
                >
                  Change
                </button>
              </div>
            </div>

            <template v-if="studentLookedUp && studentFound">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                  <input :value="queueStore.studentFullName" disabled class="w-full px-3 py-2 border border-gray-200 bg-gray-100 rounded-md text-gray-600" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input :value="queueStore.currentStudent?.email" disabled class="w-full px-3 py-2 border border-gray-200 bg-gray-100 rounded-md text-gray-600" />
                </div>
              </div>
            </template>

            <template v-if="studentLookedUp && !studentFound">
              <p class="text-sm text-yellow-800 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                Student not found. Please fill in the details below to register.
              </p>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                  <input v-model="registrationForm.first_name" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                  <input v-model="registrationForm.last_name" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary" />
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input v-model="registrationForm.email" type="email" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary" />
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Course</label>
                  <select v-model="registrationForm.course" @change="onCourseChange" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary">
                    <option :value="course.value" v-for="course in courseOptions" :key="course.value">{{ course.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Year Level</label>
                  <select v-model="registrationForm.year_level" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary">
                    <option :value="year.value" v-for="year in yearLevelOptions" :key="year.value">{{ year.label }}</option>
                  </select>
                </div>
              </div>
              <div v-if="isBitCourse">
                <label class="block text-sm font-medium text-gray-700 mb-1">Major</label>
                <select v-model="registrationForm.major" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary">
                  <option :value="null" disabled>Select a major</option>
                  <option :value="major.value" v-for="major in majorOptions" :key="major.value">{{ major.label }}</option>
                </select>
              </div>
              <div class="space-y-2">
                <div class="flex items-center">
                  <input id="is_scholar" type="checkbox" v-model="registrationForm.is_scholar" class="h-4 w-4 text-bsu-primary border-gray-300 rounded" />
                  <label for="is_scholar" class="ml-2 text-sm text-gray-700">Scholar</label>
                </div>
                <div class="flex items-center">
                  <input id="is_varsity" type="checkbox" v-model="registrationForm.is_varsity" class="h-4 w-4 text-bsu-primary border-gray-300 rounded" />
                  <label for="is_varsity" class="ml-2 text-sm text-gray-700">Varsity Athlete</label>
                </div>
                <div class="flex items-center">
                  <input id="is_graduating" type="checkbox" v-model="registrationForm.is_graduating" class="h-4 w-4 text-bsu-primary border-gray-300 rounded" />
                  <label for="is_graduating" class="ml-2 text-sm text-gray-700">Graduating Student</label>
                </div>
              </div>
            </template>

            <div v-if="studentLookedUp">
              <label class="block text-sm font-medium text-gray-700 mb-1">Purpose</label>
              <textarea
                v-model="purpose"
                rows="3"
                maxlength="200"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
              ></textarea>
              <p class="text-xs text-gray-400 text-right mt-1">{{ purpose.length }} / 200</p>
            </div>
          </div>

          <div class="flex justify-between mt-6">
            <button
              @click="currentStep = 1"
              class="px-6 py-2.5 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
            >
              ← Back
            </button>
            <button
              @click="openConfirmModal"
              :disabled="!canProceedStep2"
              class="px-6 py-2.5 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>

        <!-- STEP 4: Queue Number Generated -->
        <div v-else-if="currentStep === 4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
            <div class="bg-bsu-primary/5 border border-bsu-primary/10 rounded-xl p-6 text-center">
              <p class="text-xs font-medium text-bsu-primary uppercase mb-2">Your Queue Number</p>
              <p class="text-5xl font-extrabold text-bsu-primary">{{ ticketResult?.ticket_code }}</p>
            </div>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between"><span class="text-gray-500">Service</span><span class="font-medium text-gray-900">{{ selectedService?.label }}</span></div>
              <div v-if="selectedServiceKey === 'request_documents'" class="flex justify-between"><span class="text-gray-500">Document Type</span><span class="font-medium text-gray-900">{{ selectedDocumentTypeLabel }}</span></div>
              <div class="flex justify-between"><span class="text-gray-500">Student Number</span><span class="font-medium text-gray-900">{{ studentNumberInput }}</span></div>
              <div class="flex justify-between"><span class="text-gray-500">Student Name</span><span class="font-medium text-gray-900">{{ queueStore.studentFullName }}</span></div>
              <div class="flex justify-between"><span class="text-gray-500">Purpose</span><span class="font-medium text-gray-900">{{ purpose }}</span></div>
              <div class="flex justify-between"><span class="text-gray-500">Estimated Wait</span><span class="font-medium text-gray-900">{{ ticketResult?.estimated_wait_time_minutes || 0 }} min</span></div>
              <div class="flex justify-between"><span class="text-gray-500">Date & Time</span><span class="font-medium text-gray-900">{{ formattedTicketDate }}</span></div>
            </div>
          </div>

          <p class="text-center text-sm text-gray-500 mt-6">Please wait for your number to be called. Thank you!</p>

          <div class="flex flex-col sm:flex-row gap-3 mt-6">
            <button
              @click="viewMyQueueFromSuccess"
              class="flex-1 px-6 py-2.5 text-sm font-medium rounded-md border border-bsu-primary text-bsu-primary bg-white hover:bg-bsu-primary/5 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
            >
              View My Queue
            </button>
            <button
              @click="router.push('/')"
              class="flex-1 px-6 py-2.5 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
            >
              Return to Home
            </button>
          </div>
        </div>

        <div v-if="!loadingQueues && !showMyQueueStatus" class="mt-8 text-center">
          <router-link to="/" class="text-sm text-gray-500 hover:underline">← Back to Home</router-link>
        </div>
      </div>
    </div>

    <!-- STEP 3: Confirm modal -->
    <div v-if="showConfirmModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
      <div class="bg-white rounded-2xl shadow-xl max-w-md w-full">
        <div class="p-6 text-center">
          <div class="mx-auto w-12 h-12 rounded-full bg-bsu-primary/10 flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-bsu-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h3 class="text-lg font-bold text-gray-900 mb-1">Confirm Your Registration</h3>
          <p class="text-sm text-gray-500 mb-4">Please review your information before submitting.</p>

          <div class="text-left space-y-2 text-sm mb-4">
            <div class="flex justify-between"><span class="text-gray-500">Service</span><span class="font-medium text-gray-900">{{ selectedService?.label }}</span></div>
            <div v-if="selectedServiceKey === 'request_documents'" class="flex justify-between"><span class="text-gray-500">Document Type</span><span class="font-medium text-gray-900">{{ selectedDocumentTypeLabel }}</span></div>
            <div class="flex justify-between"><span class="text-gray-500">Student Number</span><span class="font-medium text-gray-900">{{ studentNumberInput }}</span></div>
            <div class="flex justify-between"><span class="text-gray-500">Student Name</span><span class="font-medium text-gray-900">{{ studentFound ? queueStore.studentFullName : `${registrationForm.first_name} ${registrationForm.last_name}` }}</span></div>
            <div class="flex justify-between"><span class="text-gray-500">Purpose</span><span class="font-medium text-gray-900">{{ purpose }}</span></div>
          </div>

          <div class="bg-bsu-primary/5 border border-bsu-primary/10 rounded-lg p-3 text-sm text-gray-700 mb-4">
            Once confirmed, a queue number will automatically be generated.
          </div>

          <div class="flex gap-3">
            <button
              @click="closeConfirmModal"
              class="flex-1 px-4 py-2 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
            >
              ← Back
            </button>
            <button
              @click="confirmRegistration"
              :disabled="loading"
              class="flex-1 px-4 py-2 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              <span v-if="!loading">Confirm & Get Queue Number</span>
              <span v-else>Processing...</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- My Tickets modal -->
    <div v-if="showMyTicketsModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full">
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'
import {
  ClearanceIcon,
  DocumentIcon,
  EnrollmentIcon,
  ScholarshipIcon,
  OthersIcon,
  AddDropIcon,
  GeneralInquiryIcon,
  PetitionIcon,
} from '@/components/icons/QueueIcons'

const router = useRouter()
const queueStore = useQueueStore()

const SERVICES = [
  { key: 'clearance', label: 'Clearance', description: 'Academic clearance processing for graduating or transferring students.', icon: ClearanceIcon, queueType: 'clearance', defaultPurpose: 'Clearance' },
  { key: 'request_documents', label: 'Request Documents', description: 'Request official documents such as COR, COG, TOR, Diploma, and more.', icon: DocumentIcon, queueType: 'document_request', defaultPurpose: '' },
  { key: 'adding_dropping', label: 'Adding & Dropping', description: 'Process for adding or dropping subjects.', icon: AddDropIcon, queueType: 'enrollment', defaultPurpose: 'Adding & Dropping' },
  { key: 'enrollment', label: 'Enrollment', description: 'Enrollment assistance and subject verification.', icon: EnrollmentIcon, queueType: 'enrollment', defaultPurpose: 'Enrollment' },
  { key: 'general_inquiry', label: 'General Inquiry', description: 'Ask questions about academic concerns and services.', icon: GeneralInquiryIcon, queueType: 'others', defaultPurpose: 'General Inquiry' },
  { key: 'scholarship', label: 'Scholarship', description: 'Inquiries about scholarships and requirements.', icon: ScholarshipIcon, queueType: 'scholarship', defaultPurpose: 'Scholarship Requirement' },
  { key: 'petition_class', label: 'Petition Class', description: 'File a petition for class consideration.', icon: PetitionIcon, queueType: 'enrollment', defaultPurpose: 'Petition Class' },
  { key: 'others', label: 'Others', description: 'Other concerns not listed. Please specify your purpose.', icon: OthersIcon, queueType: 'others', defaultPurpose: '' },
]

const DOCUMENT_TYPES = [
  { value: 'COR', label: 'Certificate of Registration (COR)' },
  { value: 'COG', label: 'Certificate of Grades (COG)' },
  { value: 'TOR', label: 'Transcript of Records (TOR)' },
  { value: 'Diploma', label: 'Diploma' },
  { value: 'Good Moral', label: 'Good Moral Certificate' },
  { value: 'Graduation Form', label: 'Graduation Form' },
  { value: 'Form 137', label: 'Form 137' },
]

const stepLabels = { 1: 'Select a Service', 2: 'Provide Information', 3: 'Confirm Information', 4: 'Queue Number Generated' }

const loadingQueues = ref(true)
const loading = ref(false)
const error = ref('')

const currentStep = ref(1)
const selectedServiceKey = ref(null)
const selectedDocumentType = ref('')
const othersReason = ref('')
const purpose = ref('')

const studentNumberInput = ref('')
const studentLookedUp = ref(false)
const studentFound = ref(false)

const showConfirmModal = ref(false)
const showMyTicketsModal = ref(false)
const showMyQueueStatus = ref(false)
const ticketResult = ref(null)

const BIT_COURSE_VALUE = 'Bachelor of Industrial Technology'
const emptyRegistrationForm = () => ({
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
const registrationForm = ref(emptyRegistrationForm())

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
const yearLevelOptions = [
  { value: '1st_year', label: '1st Year' },
  { value: '2nd_year', label: '2nd Year' },
  { value: '3rd_year', label: '3rd Year' },
  { value: '4th_year', label: '4th Year' },
  { value: '5th_year', label: '5th Year' },
  { value: 'graduate', label: 'Graduate' },
]
const isBitCourse = computed(() => registrationForm.value.course === BIT_COURSE_VALUE)
const onCourseChange = () => {
  if (!isBitCourse.value) registrationForm.value.major = null
}

const selectedService = computed(() => SERVICES.find(s => s.key === selectedServiceKey.value) || null)
const selectedQueueId = computed(() => {
  if (!selectedService.value) return null
  const match = queueStore.activeQueues.find(q => q.queue_type === selectedService.value.queueType)
  return match ? match.id : null
})
const selectedDocumentTypeLabel = computed(() => {
  const dt = DOCUMENT_TYPES.find(d => d.value === selectedDocumentType.value)
  return dt ? dt.label : selectedDocumentType.value
})
const myTicket = computed(() => queueStore.myTicket)
const displayedStep = computed(() => (showConfirmModal.value ? 3 : currentStep.value))
const formattedTicketDate = computed(() => {
  if (!ticketResult.value?.created_at) return ''
  return format(new Date(ticketResult.value.created_at), 'MMMM d, yyyy • h:mm a')
})

const headerSubtitle = computed(() => {
  if (showMyQueueStatus.value) return 'Your current queue status'
  return 'Take a ticket for a registrar service'
})

const canProceedStep1 = computed(() => {
  if (!selectedServiceKey.value) return false
  if (!selectedQueueId.value) return false
  if (selectedServiceKey.value === 'request_documents') return !!selectedDocumentType.value
  if (selectedServiceKey.value === 'others') return othersReason.value.trim().length > 0
  return true
})

const canProceedStep2 = computed(() => {
  if (!studentLookedUp.value) return false
  if (selectedServiceKey.value === 'others' && !purpose.value.trim()) return false
  if (!studentFound.value) {
    const f = registrationForm.value
    if (!f.first_name.trim() || !f.last_name.trim() || !f.email.trim()) return false
    if (isBitCourse.value && !f.major) return false
  }
  return true
})

const selectService = (key) => {
  selectedServiceKey.value = key
  selectedDocumentType.value = ''
  othersReason.value = ''
}

const checkExistingTicketForSelectedService = async () => {
  if (!queueStore.currentStudent || !selectedQueueId.value) return
  try {
    // Unscoped from any single queue - a student can only ever hold one
    // active ticket at a time, in any queue, so check across all of them.
    await queueStore.fetchMyTicket(queueStore.currentStudent.id)
    if (queueStore.myTicket && !['completed', 'cancelled', 'no_show'].includes(queueStore.myTicket.status)) {
      queueStore.startPollingMyTicket(queueStore.currentStudent.id)
      showMyQueueStatus.value = true
    }
  } catch (err) {
    if (err.response?.status !== 404) {
      error.value = err.response?.data?.detail || 'Failed to check for an existing ticket. Please try again.'
    }
    // a 404 here just means no active ticket exists yet - continue with registration
  }
}

const goToStep2 = async () => {
  const service = selectedService.value
  purpose.value = selectedServiceKey.value === 'request_documents'
    ? selectedDocumentType.value
    : selectedServiceKey.value === 'others'
      ? othersReason.value
      : service.defaultPurpose

  studentNumberInput.value = ''
  studentLookedUp.value = false
  studentFound.value = false
  registrationForm.value = emptyRegistrationForm()
  currentStep.value = 2

  if (queueStore.currentStudent) {
    studentNumberInput.value = queueStore.currentStudent.student_id
    studentFound.value = true
    studentLookedUp.value = true
    await checkExistingTicketForSelectedService()
  }
}

const lookupStudent = async () => {
  if (!studentNumberInput.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    await queueStore.searchStudent(studentNumberInput.value.trim())
    studentFound.value = true
    studentLookedUp.value = true
    await checkExistingTicketForSelectedService()
  } catch (err) {
    if (err.response?.status === 404) {
      studentFound.value = false
      studentLookedUp.value = true
      registrationForm.value.student_id = studentNumberInput.value.trim()
    } else {
      error.value = err.response?.data?.detail || 'Failed to look up student. Please try again.'
    }
  } finally {
    loading.value = false
  }
}

const resetStudentLookup = () => {
  studentLookedUp.value = false
  studentFound.value = false
  studentNumberInput.value = ''
  registrationForm.value = emptyRegistrationForm()
}

const openConfirmModal = () => {
  error.value = ''
  showConfirmModal.value = true
}

const closeConfirmModal = () => {
  showConfirmModal.value = false
}

const confirmRegistration = async () => {
  loading.value = true
  error.value = ''
  try {
    // Guard on currentStudent (not studentFound) - registerStudent already
    // sets currentStudent on success, so if takeTicket below fails and the
    // user retries, this correctly skips re-registering the same student_id
    // a second time, without touching studentFound (which drives the Step 2
    // form still visible behind this modal, so it must not change here).
    if (!queueStore.currentStudent) {
      await queueStore.registerStudent(registrationForm.value)
    }
    const ticket = await queueStore.takeTicket(selectedQueueId.value, queueStore.currentStudent.id, purpose.value)
    ticketResult.value = ticket
    queueStore.startPollingMyTicket(queueStore.currentStudent.id, selectedQueueId.value)
    showConfirmModal.value = false
    currentStep.value = 4
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to complete registration'
    showConfirmModal.value = false
  } finally {
    loading.value = false
  }
}

const viewMyQueueFromSuccess = () => {
  showMyQueueStatus.value = true
}

const takeAnotherTicket = () => {
  queueStore.stopPolling()
  showMyQueueStatus.value = false
  ticketResult.value = null
  selectedServiceKey.value = null
  selectedDocumentType.value = ''
  othersReason.value = ''
  purpose.value = ''
  currentStep.value = 1
}

const cancelTicket = async () => {
  if (!myTicket.value) return
  loading.value = true
  error.value = ''
  try {
    await queueStore.cancelTicket(myTicket.value.id)
    queueStore.stopPolling()
    takeAnotherTicket()
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to cancel ticket'
  } finally {
    loading.value = false
  }
}

const refreshTicket = async () => {
  if (!queueStore.currentStudent || !selectedQueueId.value) return
  loading.value = true
  error.value = ''
  try {
    await queueStore.fetchMyTicket(queueStore.currentStudent.id, selectedQueueId.value)
  } catch (err) {
    if (err.response?.status !== 404) {
      error.value = err.response?.data?.detail || 'Failed to refresh ticket status.'
    }
  } finally {
    loading.value = false
  }
}

const viewAllMyTickets = async () => {
  if (!queueStore.currentStudent) return
  await queueStore.fetchMyTickets(queueStore.currentStudent.id)
  showMyTicketsModal.value = true
}

onMounted(async () => {
  loadingQueues.value = true
  error.value = ''
  try {
    await queueStore.fetchActiveQueues()
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load services. Please try again.'
  } finally {
    loadingQueues.value = false
  }
})

onUnmounted(() => {
  queueStore.stopPolling()
})
</script>
