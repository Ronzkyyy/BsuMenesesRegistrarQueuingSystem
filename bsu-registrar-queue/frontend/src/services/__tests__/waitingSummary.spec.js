import { describe, expect, it } from 'vitest'
import { summarizeWaiting } from '../waitingSummary.js'

describe('summarizeWaiting', () => {
  it('sums waiting_count across all queues into total', () => {
    const overview = [
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 2 },
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 3 },
    ]

    const result = summarizeWaiting(overview)

    expect(result.total).toBe(5)
  })

  it('excludes queues with zero waiting_count from byQueue', () => {
    const overview = [
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 0 },
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 1 },
    ]

    const result = summarizeWaiting(overview)

    expect(result.byQueue).toEqual([
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 1 },
    ])
  })

  it('sorts byQueue with the busiest queue first', () => {
    const overview = [
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 1 },
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 4 },
      { queue_id: 3, queue_name: 'Document Request', waiting_count: 2 },
    ]

    const result = summarizeWaiting(overview)

    expect(result.byQueue.map((q) => q.queue_id)).toEqual([2, 3, 1])
  })

  it('returns total 0 and an empty byQueue for an empty overview', () => {
    const result = summarizeWaiting([])

    expect(result).toEqual({ total: 0, byQueue: [] })
  })

  it('ignores extra fields on each overview entry (only picks queue_id/queue_name/waiting_count)', () => {
    const overview = [
      {
        queue_id: 1, queue_name: 'Clearance', queue_type: 'clearance',
        serving_ticket_codes: ['C-001'], next_ticket_code: 'C-002',
        waiting_count: 1,
      },
    ]

    const result = summarizeWaiting(overview)

    expect(result.byQueue).toEqual([
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 1 },
    ])
  })
})
