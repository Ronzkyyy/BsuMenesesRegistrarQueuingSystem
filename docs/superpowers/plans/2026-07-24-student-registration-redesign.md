# Student Registration Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the student-facing "pick a service and take a ticket" flow with a 4-step wizard matching the reference mockup's visual style (Login-page look: white background, centered rounded card, light-pink/maroon theme) and 8-service-card selection, while preserving every existing backend call and student-facing feature.

**Architecture:** `frontend/src/views/QueuesView.vue` is completely rewritten in place as a single step-driven wizard component (Select Service → Provide Information → Confirm modal → Queue Number Generated), reusing existing Pinia store actions unchanged (`searchStudent`, `registerStudent`, `takeTicket`, `fetchMyTicket`, `startPollingMyTicket`, `cancelTicket`, `fetchMyTickets`, `stopPolling`). `frontend/src/views/QueueDetailView.vue` and its `/queues/:id` route are removed, since several of the 8 service cards map onto the same underlying queue and a queue ID alone can no longer identify which card the student picked. `frontend/src/views/HomeView.vue`'s queue-card links are updated to point at the new single entry point.

**Tech Stack:** Vue 3 (Composition API), Pinia, Vue Router, Tailwind CSS, date-fns.

## Global Constraints

- No backend, database, or API changes of any kind. Every store action call in this plan uses an existing, unmodified action with its existing signature.
- 8 service cards, each mapped to one of the 5 real queues (`queue_type` values), with the specific choice recorded in the ticket's existing `purpose` text field:
  - Clearance → `clearance`, purpose defaults to "Clearance"
  - Request Documents → `document_request`, purpose = chosen document type (COR, COG, TOR, Diploma, Good Moral, Graduation Form, Form 137)
  - Adding & Dropping → `enrollment`, purpose defaults to "Adding & Dropping"
  - Enrollment → `enrollment`, purpose defaults to "Enrollment"
  - Petition Class → `enrollment`, purpose defaults to "Petition Class"
  - General Inquiry → `others`, purpose defaults to "General Inquiry"
  - Scholarship → `scholarship`, purpose defaults to "Scholarship Requirement"
  - Others → `others`, purpose = the student's own required typed-in text (no default)
- Visual shell matches `LoginView.vue`: `bg-gray-50` page with two blurred decorative circles, a centered white `rounded-2xl shadow-lg border border-gray-100` card, BSU + Meneses logos, `text-bsu-primary` headings — sized `max-w-4xl` instead of Login's `max-w-md`. No `AppHeader`/`AppFooter` (neither appears on the Login page); a small "← Back to Home" text link takes their place for navigation, matching Login's own bottom-of-card link pattern.
- All existing student-facing functionality must keep working: returning-student auto-recognition (skip re-entering name/email), new-student registration with Course/Year Level/Major/priority-checkboxes (unchanged fields, still required exactly as today), active-ticket detection (skip straight to ticket status instead of re-registering), Cancel Ticket, Refresh, Take Another Ticket, View All My Tickets.
- No automated test framework is configured for this project; verification is manual against the real running dev stack.
- Seeded dev students for testing: `2024000567` (Ana Reyes, no priority flags), `2021000001` (Juan Dela Cruz, `is_graduating`), `2022000045` (Maria Santos, `is_scholar`).

---

### Task 1: Three new service icons

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/components/icons/QueueIcons.js`

**Interfaces:**
- Produces: `AddDropIcon`, `GeneralInquiryIcon`, `PetitionIcon` — exported components, same shape as the existing `ClearanceIcon`/`DocumentIcon`/`EnrollmentIcon`/`ScholarshipIcon`/`OthersIcon` (built via the existing `strokeIcon(pathD)` helper).

- [ ] **Step 1: Add the three new icon components**

In `bsu-registrar-queue/frontend/src/components/icons/QueueIcons.js`, change:

```js
export const OthersIcon = strokeIcon(
  'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z'
)

const ICONS_BY_TYPE = {
```

to:

```js
export const OthersIcon = strokeIcon(
  'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z'
)

export const AddDropIcon = strokeIcon(
  'M8 7h12m0 0l-4-4m4 4l-4 4M16 17H4m0 0l4 4m-4-4l4-4'
)

export const GeneralInquiryIcon = strokeIcon(
  'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z'
)

export const PetitionIcon = strokeIcon(
  'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z'
)

const ICONS_BY_TYPE = {
```

- [ ] **Step 2: Start the frontend and verify it builds**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: builds with no errors.

- [ ] **Step 3: Commit**

```bash
git add bsu-registrar-queue/frontend/src/components/icons/QueueIcons.js
git commit -m "feat(registration): add Adding & Dropping, General Inquiry, and Petition Class icons"
```

---

### Task 2: The 4-step registration wizard

**Files:**
- Modify (complete rewrite): `bsu-registrar-queue/frontend/src/views/QueuesView.vue`

**Interfaces:**
- Consumes: `AddDropIcon`, `GeneralInquiryIcon`, `PetitionIcon` (Task 1), plus the existing `ClearanceIcon`, `DocumentIcon`, `EnrollmentIcon`, `ScholarshipIcon`, `OthersIcon`. Existing, unmodified Pinia store actions: `queueStore.fetchActiveQueues()`, `queueStore.searchStudent(studentId)`, `queueStore.registerStudent(studentData)`, `queueStore.takeTicket(queueId, studentId, purpose)`, `queueStore.fetchMyTicket(studentId, queueId)`, `queueStore.startPollingMyTicket(studentId, queueId)`, `queueStore.stopPolling()`, `queueStore.cancelTicket(ticketId)`, `queueStore.fetchMyTickets(studentId)`. Existing state: `queueStore.activeQueues`, `queueStore.currentStudent`, `queueStore.myTicket`, `queueStore.myTickets`.
- Produces: this task's file is the sole consumer of everything above; no other task depends on new exports from it.

- [ ] **Step 1: Replace the entire contents of `QueuesView.vue`**

Replace the entire contents of `bsu-registrar-queue/frontend/src/views/QueuesView.vue` with:

```vue
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
    await queueStore.fetchMyTicket(queueStore.currentStudent.id, selectedQueueId.value)
    if (queueStore.myTicket && !['completed', 'cancelled', 'no_show'].includes(queueStore.myTicket.status)) {
      queueStore.startPollingMyTicket(queueStore.currentStudent.id, selectedQueueId.value)
      showMyQueueStatus.value = true
    }
  } catch (err) {
    // no active ticket in this queue yet - continue with registration
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
    studentFound.value = false
    studentLookedUp.value = true
    registrationForm.value.student_id = studentNumberInput.value.trim()
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
    if (!studentFound.value) {
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
  try {
    await queueStore.fetchMyTicket(queueStore.currentStudent.id, selectedQueueId.value)
  } catch (err) {
    // ignore - polling retries
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
```

- [ ] **Step 2: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend if already running).

- [ ] **Step 3: Verify — full wizard flow for a new student, a service that maps 1:1 to a queue**

Open `/queues`. Confirm the new visual shell (blurred background circles, centered white card, logos, `STEP 1: Select a Service` badge). Click "Clearance." Confirm the checkmark badge appears and "Next" becomes enabled. Click Next. Enter a student number that does not exist yet (e.g. `9999999999`). Confirm the new-student fields (First Name, Last Name, Email, Course, Year Level, Scholar/Varsity/Graduating checkboxes) appear, and the Purpose field is pre-filled with "Clearance". Fill in the required fields, **check the "Graduating Student" checkbox**, and click Next. Confirm the modal shows a correct summary and click "Confirm & Get Queue Number." Confirm Step 4 shows a real ticket code (e.g. `C-00N`), the correct service/purpose/date. Log in as `admin`/`admin123`, open Queue Management, and confirm this ticket shows priority **Urgent** (matching `is_graduating` → urgent priority) — this confirms the priority checkboxes still reach the backend correctly through the new inline fields. Back on the student side, click "View My Queue" and confirm the same ticket appears with Cancel/Refresh available.

- [ ] **Step 4: Verify — a queue-sharing service (Enrollment/Adding & Dropping/Petition Class) and Request Documents' document-type requirement**

Go back to `/queues` (via "Take Another Ticket" or a fresh page load). Select "Adding & Dropping," confirm Next is enabled immediately (no sub-fields), and complete the flow with a **different** student number than before — confirm the resulting ticket's `purpose` is "Adding & Dropping" and that it appears in the real Enrollment queue (check via `/admin/queues` as an admin, or via `/display/:id` for the Enrollment queue's display board). Repeat quickly for "Enrollment" and "Petition Class" with two more distinct student numbers, confirming each produces the correct default purpose text while landing in the same real queue. Then select "Request Documents" — confirm "Next" is disabled until a document type is chosen from the dropdown, and that completing the flow produces a ticket whose `purpose` matches the chosen document type.

- [ ] **Step 5: Verify — Others requires a reason, and returning-student auto-recognition**

Select "Others," confirm "Next" is disabled until you type something in the revealed textarea; complete the flow and confirm the ticket's `purpose` matches what you typed. Then start the wizard again, pick any service, and enter a student number you've already used in this test session (e.g. one of the ones from Steps 3-4) — confirm their Full Name and Email display read-only with no new-student fields shown, and that Purpose is still editable.

- [ ] **Step 6: Verify — existing active ticket is detected instead of re-registering**

While a student still has a `waiting` ticket from an earlier step (don't complete/cancel it), start the wizard again, pick the **same** service that ticket belongs to, and enter that same student's number — confirm the wizard skips straight to the ticket-status view (Cancel/Refresh) instead of showing Step 2's form.

- [ ] **Step 7: Verify — "Take Another Ticket" and "View All My Tickets" from the ticket-status view**

From the ticket-status view reached in Step 6, click "Take Another Ticket" — confirm it returns to Step 1 with no service selected, and that entering Step 2 again for a *different* service auto-recognizes the same student (Full Name/Email pre-filled read-only) without needing to type their student number again. Complete that second registration, then from its resulting ticket-status view click "View All My Tickets" — confirm the modal lists both of this student's active tickets (the one from Step 6 and the new one), each with the correct queue name, ticket code, and status.

- [ ] **Step 8: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/QueuesView.vue
git commit -m "feat(registration): redesign student registration as a 4-step wizard"
```

---

### Task 3: Retire `/queues/:id` and fix the homepage links

**Files:**
- Delete: `bsu-registrar-queue/frontend/src/views/QueueDetailView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/views/HomeView.vue`

**Interfaces:**
- Consumes: nothing from Tasks 1-2 beyond the fact that `/queues` (Task 2) is now the sole entry point for taking a ticket.

- [ ] **Step 1: Remove the `/queues/:id` route**

In `bsu-registrar-queue/frontend/src/router/index.js`, change:

```js
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
    {
      path: '/queues/:id',
      name: 'queue-detail',
      component: () => import('../views/QueueDetailView.vue')
    },
```

to:

```js
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
```

- [ ] **Step 2: Delete `QueueDetailView.vue`**

```bash
rm bsu-registrar-queue/frontend/src/views/QueueDetailView.vue
```

- [ ] **Step 3: Point HomeView.vue's queue cards at `/queues` instead of a specific queue ID**

In `bsu-registrar-queue/frontend/src/views/HomeView.vue`, change:

```html
        <router-link
          v-for="queue in queues"
          :key="queue.id"
          :to="`/queues/${queue.id}`"
          class="group relative bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-xl hover:border-bsu-primary/20 transition-all duration-300 overflow-hidden"
        >
```

to:

```html
        <router-link
          v-for="queue in queues"
          :key="queue.id"
          to="/queues"
          class="group relative bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-xl hover:border-bsu-primary/20 transition-all duration-300 overflow-hidden"
        >
```

- [ ] **Step 4: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend if already running).

- [ ] **Step 5: Verify — no dead links, no build errors**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: builds with no errors (confirms nothing still imports the deleted `QueueDetailView.vue`). Then in a browser: load `/`, confirm the homepage's queue cards still render with their existing stats, and clicking any of them lands on the redesigned `/queues` wizard's Step 1 — not a 404. Manually navigate to a stale `/queues/1` URL and confirm Vue Router's behavior is a clean "not found" outcome rather than a broken component (there is no explicit 404 route in this app today, so this should fall through however the router already handles an unmatched path — just confirm it doesn't crash the app).

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/frontend/src/router/index.js bsu-registrar-queue/frontend/src/views/HomeView.vue
git rm bsu-registrar-queue/frontend/src/views/QueueDetailView.vue
git commit -m "refactor(registration): retire the standalone queue-detail page and route"
```
