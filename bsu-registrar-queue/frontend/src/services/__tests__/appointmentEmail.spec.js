import { describe, expect, it } from 'vitest'
import { maskEmail, reminderBadge, studentEmailHint } from '../appointmentEmail'

describe('maskEmail', () => {
  it('matches the backend masking rule', () => {
    expect(maskEmail('juan.delacruz@gmail.com')).toBe('j***@gmail.com')
    expect(maskEmail('ab@bulsu.edu.ph')).toBe('a***@bulsu.edu.ph')
    expect(maskEmail('x@yahoo.com')).toBe('*@yahoo.com')
    expect(maskEmail('not-an-email')).toBe('***')
  })
})

describe('studentEmailHint', () => {
  it('prefers the server-masked address and masks a full one', () => {
    expect(studentEmailHint({ email_masked: 'm***@gmail.com' })).toBe('m***@gmail.com')
    expect(studentEmailHint({ email: 'maria@gmail.com' })).toBe('m***@gmail.com')
    expect(studentEmailHint(null)).toBe('')
  })
})

describe('reminderBadge', () => {
  it('labels each reminder status', () => {
    expect(reminderBadge('sent').label).toBe('Sent')
    expect(reminderBadge('pending').label).toBe('Pending')
    expect(reminderBadge('failed').label).toBe('Failed')
    expect(reminderBadge('not_applicable').label).toBe('—')
  })
})
