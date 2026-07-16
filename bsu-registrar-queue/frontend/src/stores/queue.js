/**
 * Queue store for Vue.js (using Pinia)
 * Handles all API interactions for queues, tickets, and students
 */
import { defineStore } from 'pinia'
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

const TOKEN_KEY = 'registrar_token'

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const useQueueStore = defineStore('queue', {
  state: () => ({
    // Queues
    queues: [],
    activeQueues: [],
    currentQueue: null,
    queueStats: null,

    // Tickets
    myTicket: null,
    myTickets: [],
    queueTickets: [],
    queueDisplay: [],
    servingTicket: null,
    nowServingOverview: [],

    // Students
    currentStudent: null,
    students: [],
    studentStats: null,

    // Auth
    token: localStorage.getItem(TOKEN_KEY) || null,
    currentUser: null,

    // Dashboard
    dashboardSummary: null,

    // Users
    users: [],

    // UI State
    loading: false,
    error: null,
    pollingInterval: null,
  }),

  getters: {
    // Queue getters
    getQueueById: (state) => (id) => state.queues.find(q => q.id === id),
    getActiveQueueById: (state) => (id) => state.activeQueues.find(q => q.id === id),

    // Ticket getters
    hasActiveTicket: (state) => !!state.myTicket,
    ticketPosition: (state) => state.myTicket?.position ?? 0,
    estimatedWaitTime: (state) => state.myTicket?.estimated_wait_time_minutes ?? 0,

    // Auth getters
    isAuthenticated: (state) => !!state.token,

    // Student getters
    isStudentRegistered: (state) => !!state.currentStudent,
    studentFullName: (state) => state.currentStudent
      ? `${state.currentStudent.first_name} ${state.currentStudent.last_name}`
      : '',
    studentPriorityFlags: (state) => state.currentStudent ? {
      is_scholar: state.currentStudent.is_scholar,
      is_varsity: state.currentStudent.is_varsity,
      is_graduating: state.currentStudent.is_graduating,
    } : {},
  },

  actions: {
    // ============ AUTH ACTIONS ============

    async login(username, password, portal = null) {
      this.loading = true
      this.error = null
      try {
        const form = new URLSearchParams()
        form.append('username', username)
        form.append('password', password)
        if (portal) form.append('portal', portal)
        const response = await api.post('/auth/login', form, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
        this.token = response.data.access_token
        localStorage.setItem(TOKEN_KEY, this.token)
        await this.fetchCurrentUser()
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Invalid username or password'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchCurrentUser() {
      try {
        const response = await api.get('/auth/me')
        this.currentUser = response.data
        return response.data
      } catch (err) {
        this.currentUser = null
        throw err
      }
    },

    logout() {
      this.token = null
      this.currentUser = null
      localStorage.removeItem(TOKEN_KEY)
      this.stopPolling()
    },

    // ============ DASHBOARD ACTIONS ============

    async fetchDashboardSummary() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/queues/dashboard-summary')
        this.dashboardSummary = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch dashboard summary'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ USER MANAGEMENT ACTIONS ============

    async fetchUsers() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/auth/users')
        this.users = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch users'
        throw err
      } finally {
        this.loading = false
      }
    },

    async createUser(userData) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/auth/register', userData)
        this.users.push(response.data)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to create user'
        throw err
      } finally {
        this.loading = false
      }
    },

    async activateUser(userId) {
      this.loading = true
      this.error = null
      try {
        await api.patch(`/auth/users/${userId}/activate`)
        const idx = this.users.findIndex(u => u.id === userId)
        if (idx !== -1) this.users[idx].is_active = true
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to activate user'
        throw err
      } finally {
        this.loading = false
      }
    },

    async deactivateUser(userId) {
      this.loading = true
      this.error = null
      try {
        await api.patch(`/auth/users/${userId}/deactivate`)
        const idx = this.users.findIndex(u => u.id === userId)
        if (idx !== -1) this.users[idx].is_active = false
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to deactivate user'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ QUEUE ACTIONS ============

    async fetchQueues() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/queues')
        this.queues = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch queues'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchActiveQueues() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/queues/active')
        this.activeQueues = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch active queues'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchQueueById(queueId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get(`/queues/${queueId}`)
        this.currentQueue = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch queue'
        throw err
      } finally {
        this.loading = false
      }
    },

    async createQueue(queueData) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/queues', queueData)
        this.queues.push(response.data)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to create queue'
        throw err
      } finally {
        this.loading = false
      }
    },

    async updateQueueStatus(queueId, status) {
      this.loading = true
      this.error = null
      try {
        const response = await api.patch(`/queues/${queueId}/status`, status)
        const index = this.queues.findIndex(q => q.id === queueId)
        if (index !== -1) this.queues[index] = response.data
        if (this.currentQueue?.id === queueId) this.currentQueue = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to update queue status'
        throw err
      } finally {
        this.loading = false
      }
    },

    async pauseQueue(queueId) {
      return this.updateQueueStatus(queueId, 'paused')
    },

    async resumeQueue(queueId) {
      return this.updateQueueStatus(queueId, 'active')
    },

    async closeQueue(queueId) {
      return this.updateQueueStatus(queueId, 'closed')
    },

    async fetchQueueStats(queueId) {
      try {
        const response = await api.get(`/queues/${queueId}/stats`)
        this.queueStats = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch queue stats'
        throw err
      }
    },

    async deleteQueue(queueId) {
      this.loading = true
      this.error = null
      try {
        await api.delete(`/queues/${queueId}`)
        this.queues = this.queues.filter(q => q.id !== queueId)
        if (this.currentQueue?.id === queueId) this.currentQueue = null
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to delete queue'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ TICKET ACTIONS ============

    async takeTicket(queueId, studentId, purpose = '') {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/tickets', {
          queue_id: queueId,
          student_id: studentId,
          purpose,
        })
        this.myTicket = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to take ticket'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchMyTicket(studentId, queueId = null) {
      this.loading = true
      this.error = null
      try {
        const params = { student_id: studentId }
        if (queueId) params.queue_id = queueId
        const response = await api.get('/tickets/my-ticket', { params })
        this.myTicket = response.data
        return response.data
      } catch (err) {
        if (err.response?.status !== 404) {
          this.error = err.response?.data?.detail || 'Failed to fetch ticket'
        }
        this.myTicket = null
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchMyTickets(studentId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/tickets/my-tickets', { params: { student_id: studentId } })
        this.myTickets = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch tickets'
        throw err
      } finally {
        this.loading = false
      }
    },

    async cancelTicket(ticketId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/${ticketId}/cancel`)
        this.myTicket = null
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to cancel ticket'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchQueueTickets(queueId, status = null) {
      this.loading = true
      this.error = null
      try {
        const params = status ? { status } : {}
        const response = await api.get(`/tickets/queue/${queueId}`, { params })
        this.queueTickets = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch queue tickets'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchQueueDisplay(queueId) {
      try {
        const response = await api.get(`/tickets/queue/${queueId}/display`)
        this.queueDisplay = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch queue display'
        throw err
      }
    },

    async fetchNowServingOverview() {
      try {
        const response = await api.get('/tickets/now-serving-overview')
        this.nowServingOverview = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch now-serving overview'
        throw err
      }
    },

    async serveNextTicket(queueId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/queue/${queueId}/next`)
        this.servingTicket = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'No waiting tickets'
        throw err
      } finally {
        this.loading = false
      }
    },

    async serveTicket(ticketId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/${ticketId}/serve`)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to serve ticket'
        throw err
      } finally {
        this.loading = false
      }
    },

    async completeTicket(ticketId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/${ticketId}/complete`)
        // Update local state
        if (this.myTicket?.id === ticketId) {
          this.myTicket = response.data
        }
        const idx = this.queueTickets.findIndex(t => t.id === ticketId)
        if (idx !== -1) this.queueTickets[idx] = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to complete ticket'
        throw err
      } finally {
        this.loading = false
      }
    },

    async markNoShow(ticketId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/${ticketId}/no-show`)
        const idx = this.queueTickets.findIndex(t => t.id === ticketId)
        if (idx !== -1) this.queueTickets[idx] = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to mark no-show'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ STUDENT ACTIONS ============

    async searchStudent(studentId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/students/search', { params: { student_id: studentId } })
        this.currentStudent = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Student not found'
        this.currentStudent = null
        throw err
      } finally {
        this.loading = false
      }
    },

    async registerStudent(studentData) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/students', studentData)
        this.currentStudent = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to register student'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchStudentById(studentId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get(`/students/${studentId}`)
        this.currentStudent = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch student'
        throw err
      } finally {
        this.loading = false
      }
    },

    async searchStudents(query = '', course = null, yearLevel = null, skip = 0, limit = 50) {
      this.loading = true
      this.error = null
      try {
        const params = { query, skip, limit }
        if (course) params.course = course
        if (yearLevel) params.year_level = yearLevel
        const response = await api.get('/students', { params })
        this.students = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to search students'
        throw err
      } finally {
        this.loading = false
      }
    },

    async updateStudent(studentId, studentData) {
      this.loading = true
      this.error = null
      try {
        const response = await api.patch(`/students/${studentId}`, studentData)
        if (this.currentStudent?.id === studentId) {
          this.currentStudent = response.data
        }
        const idx = this.students.findIndex(s => s.id === studentId)
        if (idx !== -1) this.students[idx] = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to update student'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchStudentStats() {
      try {
        const response = await api.get('/students/stats/summary')
        this.studentStats = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch student stats'
        throw err
      }
    },

    // ============ POLLING ACTIONS ============

    startPollingMyTicket(studentId, queueId = null, interval = 10000) {
      this.stopPolling()
      this.pollingInterval = setInterval(() => {
        this.fetchMyTicket(studentId, queueId).catch(() => {})
      }, interval)
      // Initial fetch
      this.fetchMyTicket(studentId, queueId).catch(() => {})
    },

    startPollingQueueDisplay(queueId, interval = 5000) {
      this.stopPolling()
      this.pollingInterval = setInterval(() => {
        this.fetchQueueDisplay(queueId).catch(() => {})
      }, interval)
      this.fetchQueueDisplay(queueId).catch(() => {})
    },

    startPollingNowServingOverview(interval = 4000) {
      this.stopPolling()
      this.pollingInterval = setInterval(() => {
        this.fetchNowServingOverview().catch(() => {})
      }, interval)
      this.fetchNowServingOverview().catch(() => {})
    },

    startPollingQueueTickets(queueId, interval = 10000) {
      this.stopPolling()
      this.pollingInterval = setInterval(() => {
        this.fetchQueueTickets(queueId).catch(() => {})
      }, interval)
      this.fetchQueueTickets(queueId).catch(() => {})
    },

    stopPolling() {
      if (this.pollingInterval) {
        clearInterval(this.pollingInterval)
        this.pollingInterval = null
      }
    },

    // ============ UTILITY ACTIONS ============

    clearError() {
      this.error = null
    },

    clearCurrentStudent() {
      this.currentStudent = null
    },

    clearMyTicket() {
      this.myTicket = null
    },

    reset() {
      this.queues = []
      this.activeQueues = []
      this.currentQueue = null
      this.queueStats = null
      this.myTicket = null
      this.queueTickets = []
      this.queueDisplay = []
      this.servingTicket = null
      this.currentStudent = null
      this.students = []
      this.studentStats = null
      this.loading = false
      this.error = null
      this.stopPolling()
    },
  },
})