import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// queue.js creates its own private `axios.create()` instance internally
// (never exported), so the only way to intercept its HTTP calls is to mock
// the `axios` module itself. vi.mock is hoisted above imports, so the mock
// instance has to be built with vi.hoisted() to be visible inside the
// hoisted factory.
const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: { request: { use: vi.fn() } },
  },
}))

vi.mock('axios', () => ({
  default: { create: vi.fn(() => mockApi) },
}))

const { useQueueStore } = await import('../queue.js')

function ok(data) {
  return Promise.resolve({ data })
}

function fail(detail) {
  const err = new Error(detail)
  err.response = { data: { detail } }
  return Promise.reject(err)
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  localStorage.clear()
})

describe('getters', () => {
  it('hasActiveTicket reflects whether myTicket is set', () => {
    const store = useQueueStore()
    expect(store.hasActiveTicket).toBe(false)
    store.myTicket = { id: 1 }
    expect(store.hasActiveTicket).toBe(true)
  })

  it('isAuthenticated reflects whether a token is present', () => {
    const store = useQueueStore()
    expect(store.isAuthenticated).toBe(false)
    store.token = 'abc123'
    expect(store.isAuthenticated).toBe(true)
  })

  it('studentFullName combines first/last name, empty when no student', () => {
    const store = useQueueStore()
    expect(store.studentFullName).toBe('')
    store.currentStudent = { first_name: 'Ana', last_name: 'Reyes' }
    expect(store.studentFullName).toBe('Ana Reyes')
  })

  it('getQueueById finds a queue from the loaded list', () => {
    const store = useQueueStore()
    store.queues = [{ id: 1, name: 'A' }, { id: 2, name: 'B' }]
    expect(store.getQueueById(2)?.name).toBe('B')
    expect(store.getQueueById(99)).toBeUndefined()
  })
})

describe('auth actions', () => {
  it('login stores the token and fetches the current user', async () => {
    mockApi.post.mockReturnValueOnce(ok({ access_token: 'tok-1' }))
    mockApi.get.mockReturnValueOnce(ok({ id: 1, username: 'admin' }))
    const store = useQueueStore()

    const result = await store.login('admin', 'admin123', 'admin')

    expect(mockApi.post).toHaveBeenCalledWith(
      '/auth/login',
      expect.any(URLSearchParams),
      expect.objectContaining({ headers: expect.any(Object) })
    )
    expect(store.token).toBe('tok-1')
    expect(localStorage.getItem('registrar_token')).toBe('tok-1')
    expect(store.currentUser).toEqual({ id: 1, username: 'admin' })
    expect(result.access_token).toBe('tok-1')
    expect(store.loading).toBe(false)
  })

  it('login surfaces the server error message and rethrows', async () => {
    mockApi.post.mockReturnValueOnce(fail('Invalid credentials'))
    const store = useQueueStore()

    await expect(store.login('admin', 'wrong')).rejects.toThrow()

    expect(store.error).toBe('Invalid credentials')
    expect(store.token).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('logout clears token, user, and persisted storage', () => {
    const store = useQueueStore()
    store.token = 'tok-1'
    store.currentUser = { id: 1 }
    localStorage.setItem('registrar_token', 'tok-1')

    store.logout()

    expect(store.token).toBeNull()
    expect(store.currentUser).toBeNull()
    expect(localStorage.getItem('registrar_token')).toBeNull()
  })
})

describe('queue actions', () => {
  it('fetchQueues loads the queue list', async () => {
    const queues = [{ id: 1, name: 'Clearance' }]
    mockApi.get.mockReturnValueOnce(ok(queues))
    const store = useQueueStore()

    const result = await store.fetchQueues()

    expect(mockApi.get).toHaveBeenCalledWith('/queues')
    expect(store.queues).toEqual(queues)
    expect(result).toEqual(queues)
  })

  it('fetchQueues surfaces an error and resets loading', async () => {
    mockApi.get.mockReturnValueOnce(fail('Failed to fetch queues'))
    const store = useQueueStore()

    await expect(store.fetchQueues()).rejects.toThrow()

    expect(store.error).toBe('Failed to fetch queues')
    expect(store.loading).toBe(false)
  })

  it('createQueue appends the new queue to local state', async () => {
    const created = { id: 5, name: 'New Queue' }
    mockApi.post.mockReturnValueOnce(ok(created))
    const store = useQueueStore()
    store.queues = [{ id: 1, name: 'Existing' }]

    await store.createQueue({ name: 'New Queue' })

    expect(store.queues).toEqual([{ id: 1, name: 'Existing' }, created])
  })

  it('closeQueue sends the new status as a query param, not a request body', async () => {
    // The backend declares `status` as a plain (non-Body) parameter, which
    // FastAPI binds as a required query param - sending it as the request
    // body 422s with "Field required" and the button silently does nothing.
    mockApi.patch.mockReturnValueOnce(ok({ id: 3, status: 'closed' }))
    const store = useQueueStore()

    await store.closeQueue(3)

    expect(mockApi.patch).toHaveBeenCalledWith(
      '/queues/3/status',
      null,
      { params: { status: 'closed' } }
    )
  })
})

describe('ticket actions', () => {
  it('takeTicket posts the right payload and stores the result', async () => {
    const ticket = { id: 10, ticket_code: 'C-001' }
    mockApi.post.mockReturnValueOnce(ok(ticket))
    const store = useQueueStore()

    await store.takeTicket(3, 7, 'Clearance')

    expect(mockApi.post).toHaveBeenCalledWith('/tickets', {
      queue_id: 3,
      student_id: 7,
      purpose: 'Clearance',
    })
    expect(store.myTicket).toEqual(ticket)
  })
})

describe('appointment actions', () => {
  it('fetchAppointmentAvailability sends queue_id/appointment_date as query params', async () => {
    const slots = [{ slot_start_time: '08:00:00' }]
    mockApi.get.mockReturnValueOnce(ok(slots))
    const store = useQueueStore()

    await store.fetchAppointmentAvailability(3, '2026-08-25')

    expect(mockApi.get).toHaveBeenCalledWith('/appointments/availability', {
      params: { queue_id: 3, appointment_date: '2026-08-25' },
    })
    expect(store.appointmentAvailability).toEqual(slots)
  })

  it('lookupAppointment clears myAppointment on failure, unlike the usual pattern', async () => {
    const store = useQueueStore()
    store.myAppointment = { id: 1, reference_code: 'APT-000001' }
    mockApi.get.mockReturnValueOnce(fail('Appointment not found'))

    await expect(store.lookupAppointment('2021000001', 'APT-BAD')).rejects.toThrow()

    expect(store.error).toBe('Appointment not found')
    expect(store.myAppointment).toBeNull()
  })
})

describe('student actions', () => {
  it('searchStudents splits the paginated response into students/studentsTotal', async () => {
    mockApi.get.mockReturnValueOnce(ok({ items: [{ id: 1 }, { id: 2 }], total: 2 }))
    const store = useQueueStore()

    await store.searchStudents('reyes')

    expect(mockApi.get).toHaveBeenCalledWith('/students', {
      params: { query: 'reyes', skip: 0, limit: 25 },
    })
    expect(store.students).toHaveLength(2)
    expect(store.studentsTotal).toBe(2)
  })

  it('searchStudents only includes course/year_level params when provided', async () => {
    mockApi.get.mockReturnValueOnce(ok({ items: [], total: 0 }))
    const store = useQueueStore()

    await store.searchStudents('', 'Bachelor of Science in Information Technology', '1st_year')

    expect(mockApi.get).toHaveBeenCalledWith('/students', {
      params: {
        query: '',
        skip: 0,
        limit: 25,
        course: 'Bachelor of Science in Information Technology',
        year_level: '1st_year',
      },
    })
  })
})
