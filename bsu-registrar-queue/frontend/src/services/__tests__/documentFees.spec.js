import { describe, expect, it } from 'vitest'
import { feeSummary, formatFee, shortNames, totalLabel } from '../documentFees'

describe('formatFee', () => {
  it('formats a listed fee in pesos', () => {
    expect(formatFee('50.00')).toBe('₱50.00')
    expect(formatFee('1250.5')).toBe('₱1,250.50')
  })

  it('shows Free for zero and nothing for an unlisted fee', () => {
    expect(formatFee('0.00')).toBe('Free')
    expect(formatFee(null)).toBe('')
    expect(formatFee(undefined)).toBe('')
  })
})

describe('feeSummary / totalLabel', () => {
  it('sums listed fees without float noise', () => {
    const docs = [{ fee: '0.10' }, { fee: '0.20' }]
    expect(feeSummary(docs).total).toBe(0.3)
    expect(totalLabel(docs)).toBe('Total ₱0.30')
  })

  it('marks a partial total when some fees are not listed', () => {
    const docs = [{ fee: '50.00' }, { fee: null }, { fee: '30.00' }]
    expect(feeSummary(docs)).toEqual({ count: 3, total: 80, hasUnlisted: true })
    expect(totalLabel(docs)).toBe('Total of listed fees ₱80.00')
  })

  it('has no total when nothing is priced', () => {
    expect(feeSummary([{ fee: null }]).total).toBeNull()
    expect(totalLabel([{ fee: null }])).toBe('')
    expect(totalLabel([])).toBe('')
  })

  it('counts a free document as priced', () => {
    expect(totalLabel([{ fee: '0.00' }])).toBe('Total ₱0.00')
  })
})

describe('shortNames', () => {
  it('joins short names in the given order', () => {
    expect(shortNames([{ short_name: 'TOR' }, { short_name: 'COG' }])).toBe('TOR, COG')
  })
})
