import { describe, expect, it } from 'vitest'
import { buildErrorCsv, csvCell } from '../studentImportCsv'

describe('csvCell', () => {
  it('guards formula-like cells', () => {
    for (const v of ['=SUM(A1)', '+1', '-1', '@x', '\tx', '\rx']) {
      expect(csvCell(v).startsWith("'") || csvCell(v).startsWith(`"'`)).toBe(true)
    }
    expect(csvCell('Juan')).toBe('Juan')
  })

  it('quotes commas, quotes and newlines', () => {
    expect(csvCell('Dela Cruz, Jr.')).toBe('"Dela Cruz, Jr."')
    expect(csvCell('say "hi"')).toBe('"say ""hi"""')
    expect(csvCell('a\nb')).toBe('"a\nb"')
  })
})

describe('buildErrorCsv', () => {
  it('keeps the original columns and adds Row and Error', () => {
    const csv = buildErrorCsv(['Student Number', 'First Name'], [
      { row: 5, column: 'Student Number', message: 'Must be exactly 10 digits.',
        values: { 'Student Number': '123', 'First Name': '=HYPERLINK("x")' } },
    ])
    const lines = csv.replace(/^﻿/, '').split('\r\n')
    expect(lines[0]).toBe('Student Number,First Name,Row,Error')
    expect(lines[1]).toBe(`123,"'=HYPERLINK(""x"")",5,Student Number: Must be exactly 10 digits.`)
    expect(csv.startsWith('﻿')).toBe(true)
  })
})
