// Appointment-email display helpers.

// Same rule as the backend's app/services/email_mask.py: enough for a
// student to recognise their address and spot a typo in the domain.
export function maskEmail(email) {
  const at = (email || '').indexOf('@')
  if (at < 0) return '***'
  const local = email.slice(0, at)
  const domain = email.slice(at + 1)
  return local.length <= 1 ? `*@${domain}` : `${local[0]}***@${domain}`
}

// The address to show a student: the public lookup sends only
// `email_masked`; a just-registered student's own record has `email`.
export function studentEmailHint(student) {
  if (!student) return ''
  return student.email_masked || (student.email ? maskEmail(student.email) : '')
}

// Badge for the morning reminder's reminder_status.
const BADGES = {
  sent: { label: 'Sent', classes: 'bg-green-50 text-green-700' },
  pending: { label: 'Pending', classes: 'bg-bsu-gold/20 text-bsu-gold-dark' },
  failed: { label: 'Failed', classes: 'bg-red-50 text-red-700' },
}

export function reminderBadge(status) {
  return BADGES[status] || { label: '—', classes: 'text-gray-400' }
}
