// "Rows with errors" download for the student import. Built in the browser
// from the import report, meant to be opened in Excel - so any cell Excel
// would treat as a formula (= + - @ tab CR) gets a leading ' (CSV injection
// guard), and cells with commas/quotes/newlines are quoted.

const FORMULA_START = /^[=+\-@\t\r]/

export function csvCell(value) {
  let text = value == null ? '' : String(value)
  if (FORMULA_START.test(text)) text = `'${text}`
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function buildErrorCsv(columns, problems) {
  const header = [...columns, 'Row', 'Error']
  const lines = [header.map(csvCell).join(',')]
  for (const p of problems) {
    const cells = columns.map((c) => p.values?.[c] ?? '')
    lines.push([...cells, p.row, `${p.column}: ${p.message}`].map(csvCell).join(','))
  }
  // BOM so Excel opens UTF-8 names (ñ, é) correctly.
  return '\uFEFF' + lines.join('\r\n')
}
