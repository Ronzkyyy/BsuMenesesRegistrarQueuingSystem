import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// queue.js creates its own private `axios.create()` instance internally
// (never exported), so the only way to intercept its HTTP calls is to mock
// the `axios` module itself. vi.mock is hoisted above imports, so the mock
// instance has to be built with vi.hoisted() to be visible inside the
// hoisted factory.
// `interceptors.response.use` must exist on both the `api` mock and the bare
// default axios mock: queue.js registers the same response interceptor on
// both (QueueManagementView's direct-axios calls need it too), and the
// registered rejection handlers are captured here so their behavior can be
// tested directly.
const { mockApi, interceptor, axiosInterceptor } = vi.hoisted(() => {
  const interceptor = { onRejected: null }
  const axiosInterceptor = { onRejected: null }
  return {
    interceptor,
    axiosInterceptor,
    mockApi: {
      get: vi.fn(),
      post: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
      interceptors: {
        response: {
          use: vi.fn((_onFulfilled, onRejected) => {
            interceptor.onRejected = onRejected
          }),
        },
      },
    },
  }
})

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockApi),
    interceptors: {
      response: {
        use: vi.fn((_onFulfilled, onRejected) => {
          axiosInterceptor.onRejected = onRejected
        }),
      },
    },
  },
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
})

describe('getters', () => {
  it('hasActiveTicket reflects whether myTicket is set', () => {
    const store = useQueueStore()
    expect(store.hasActiveTicket).toBe(false)
    store.myTicket = { id: 1 }
    expect(store.hasActiveTicket).toBe(true)
  })

  it('isAuthenticated reflects whether currentUser is loaded', () => {
    const store = useQueueStore()
    expect(store.isAuthenticated).toBe(false)
    store.currentUser = { id: 1, username: 'admin' }
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
  it('login sets currentUser from the response body (no token in it)', async () => {
    mockApi.post.mockReturnValueOnce(ok({ id: 1, username: 'admin' }))
    const store = useQueueStore()

    const result = await store.login('admin', 'admin123', 'admin')

    expect(mockApi.post).toHaveBeenCalledWith(
      '/auth/login',
      expect.any(URLSearchParams),
      expect.objectContaining({ headers: expect.any(Object) })
    )
    expect(store.currentUser).toEqual({ id: 1, username: 'admin' })
    expect(result).toEqual({ id: 1, username: 'admin' })
    expect(store.loading).toBe(false)
  })

  it('login surfaces the server error message and rethrows', async () => {
    mockApi.post.mockReturnValueOnce(fail('Invalid credentials'))
    const store = useQueueStore()

    await expect(store.login('admin', 'wrong')).rejects.toThrow()

    expect(store.error).toBe('Invalid credentials')
    expect(store.currentUser).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('logout calls the backend and clears currentUser', async () => {
    mockApi.post.mockReturnValueOnce(ok({ message: 'Successfully logged out' }))
    const store = useQueueStore()
    store.currentUser = { id: 1 }

    await store.logout()

    expect(mockApi.post).toHaveBeenCalledWith('/auth/logout')
    expect(store.currentUser).toBeNull()
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

    await store.takeTicket(3, 7)

    expect(mockApi.post).toHaveBeenCalledWith('/tickets', {
      queue_id: 3,
      student_id: 7,
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

  it('checkInAppointment keeps error a string when a 410 returns a detail object', async () => {
    const err = new Error('gone')
    err.response = {
      status: 410,
      data: {
        detail: {
          message: 'This appointment has expired.',
          code: 'appointment_expired',
          reference_code: 'APT-000482',
        },
      },
    }
    mockApi.post.mockReturnValueOnce(Promise.reject(err))
    const store = useQueueStore()

    await expect(store.checkInAppointment({ referenceCode: 'APT-000482' })).rejects.toThrow()

    expect(store.error).toBe('This appointment has expired.')
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

describe('reports actions', () => {
  it('fetchTransactionHistory passes filters through and serializes arrays without brackets', async () => {
    const pageData = { items: [{ id: 1, kind: 'ticket' }], total: 1, skip: 0, limit: 50 }
    mockApi.get.mockReturnValueOnce(ok(pageData))
    const store = useQueueStore()

    const params = { date_from: '2026-06-01', date_to: '2026-06-30', kind: ['ticket', 'appointment'] }
    const result = await store.fetchTransactionHistory(params)

    expect(mockApi.get).toHaveBeenCalledWith('/reports/transactions', {
      params,
      paramsSerializer: { indexes: null },
    })
    expect(store.transactionHistory).toEqual(pageData)
    expect(result).toEqual(pageData)
  })

  it('fetchTransactionHistory surfaces the server error and rethrows', async () => {
    mockApi.get.mockReturnValueOnce(fail('Too many rows to export'))
    const store = useQueueStore()

    await expect(store.fetchTransactionHistory({})).rejects.toThrow()

    expect(store.error).toBe('Too many rows to export')
    expect(store.loading).toBe(false)
  })

  it('fetchTransactionCalendar sends year/month as query params', async () => {
    const cal = { year: 2026, month: 6, month_total: 3, days: [], busiest_hours: [] }
    mockApi.get.mockReturnValueOnce(ok(cal))
    const store = useQueueStore()

    await store.fetchTransactionCalendar(2026, 6)

    expect(mockApi.get).toHaveBeenCalledWith('/reports/calendar', {
      params: { year: 2026, month: 6 },
    })
    expect(store.transactionCalendar).toEqual(cal)
  })
})

describe('response interceptor', () => {
  it('is registered on the axios instance', () => {
    // Registration happens once at module import, so assert on the captured
    // handler rather than the mock's call record (beforeEach clears that).
    expect(typeof interceptor.onRejected).toBe('function')
  })

  it('humanizes a Pydantic validation-error array into one readable string', async () => {
    const err = new Error('unprocessable')
    err.response = {
      status: 422,
      data: {
        detail: [
          { loc: ['body', 'student_id'], type: 'string_pattern_mismatch' },
          { loc: ['body', 'first_name'], type: 'missing' },
        ],
      },
    }

    await expect(interceptor.onRejected(err)).rejects.toBe(err)

    expect(err.response.data.detail).toBe(
      'Please enter a valid 10-digit student number. Please provide the first name.'
    )
  })

  it('leaves a plain string detail untouched', async () => {
    const err = new Error('bad request')
    err.response = { status: 400, data: { detail: 'Queue not found' } }

    await expect(interceptor.onRejected(err)).rejects.toBe(err)

    expect(err.response.data.detail).toBe('Queue not found')
  })

  it('is also registered on the bare axios instance (for QueueManagementView\'s direct calls)', () => {
    expect(typeof axiosInterceptor.onRejected).toBe('function')
  })

  it('resyncs currentUser and rewrites the message on a stale-session 403', async () => {
    const store = useQueueStore()
    store.currentUser = { id: 1, username: 'admin', role: 'admin' }
    mockApi.get.mockReturnValueOnce(ok({ id: 2, username: 'staff1', role: 'staff' }))
    const err = new Error('forbidden')
    err.config = { url: '/queues/1/booking-settings' }
    err.response = { status: 403, data: { detail: 'Insufficient permissions' } }

    await expect(interceptor.onRejected(err)).rejects.toBe(err)

    expect(mockApi.get).toHaveBeenCalledWith('/auth/me')
    expect(store.currentUser).toEqual({ id: 2, username: 'staff1', role: 'staff' })
    expect(err.response.data.detail).toBe(
      "You're now signed in as staff1 (staff) - this doesn't have permission for that. " +
      'Log in again if you meant to continue as a different account.'
    )
  })

  it('clears currentUser and shows a session-expired message on 401 when resync also fails', async () => {
    const store = useQueueStore()
    store.currentUser = { id: 1, username: 'admin', role: 'admin' }
    mockApi.get.mockReturnValueOnce(fail('Not authenticated'))
    const err = new Error('unauthorized')
    err.config = { url: '/queues' }
    err.response = { status: 401, data: { detail: 'Not authenticated' } }

    await expect(interceptor.onRejected(err)).rejects.toBe(err)

    expect(store.currentUser).toBeNull()
    expect(err.response.data.detail).toBe('Your session has expired. Please log in again.')
  })

  it('leaves a failed login 401 untouched (not a stale session)', async () => {
    const err = new Error('bad creds')
    err.config = { url: '/auth/login' }
    err.response = { status: 401, data: { detail: 'Incorrect username or password' } }

    await expect(interceptor.onRejected(err)).rejects.toBe(err)

    expect(mockApi.get).not.toHaveBeenCalledWith('/auth/me')
    expect(err.response.data.detail).toBe('Incorrect username or password')
  })
})
