// Derives the staff waiting-ticket notification's badge/dropdown data from
// the now-serving-overview response (GET /api/tickets/now-serving-overview,
// already public and already polled elsewhere) - one place that decides
// "how many are waiting, and where" so the component stays pure display.
export function summarizeWaiting(overview) {
  const byQueue = overview
    .filter((q) => q.waiting_count > 0)
    .map((q) => ({
      queue_id: q.queue_id,
      queue_name: q.queue_name,
      waiting_count: q.waiting_count,
    }))
    .sort((a, b) => b.waiting_count - a.waiting_count)

  const total = overview.reduce((sum, q) => sum + (q.waiting_count || 0), 0)

  return { total, byQueue }
}
