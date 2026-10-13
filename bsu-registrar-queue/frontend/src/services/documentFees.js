// Fee display for the Request Documents checklist. The API sends fees as
// decimal strings ("50.00") or null - null means "no fee listed", "0.00"
// means free. Totals are summed in centavos so they never pick up float
// rounding noise.

const peso = new Intl.NumberFormat('en-PH', {
  style: 'currency',
  currency: 'PHP',
  minimumFractionDigits: 2,
})

const toCentavos = (fee) => Math.round(Number(fee) * 100)

export function formatPeso(amount) {
  return peso.format(Number(amount))
}

// One document's fee label: "₱50.00", "Free", or '' when none is listed.
export function formatFee(fee) {
  if (fee === null || fee === undefined || fee === '') return ''
  return toCentavos(fee) === 0 ? 'Free' : formatPeso(fee)
}

// Summary of a set of documents (catalog entries or a ticket's requested
// documents - both carry `fee`).
//   total       - sum of listed fees in pesos, or null if none lists a fee
//   hasUnlisted - some document has no fee listed, so the total is partial
export function feeSummary(documents) {
  const listed = documents.filter(d => d.fee !== null && d.fee !== undefined && d.fee !== '')
  const centavos = listed.reduce((sum, d) => sum + toCentavos(d.fee), 0)
  return {
    count: documents.length,
    total: listed.length ? centavos / 100 : null,
    hasUnlisted: listed.length < documents.length,
  }
}

// "Total ₱80.00", "Total of listed fees ₱80.00", or '' when nothing is priced.
export function totalLabel(documents) {
  const { total, hasUnlisted } = feeSummary(documents)
  if (total === null) return ''
  return `${hasUnlisted ? 'Total of listed fees' : 'Total'} ${formatPeso(total)}`
}

// "TOR, COG, Good Moral" - compact list for summaries and tables.
export function shortNames(documents) {
  return documents.map(d => d.short_name).join(', ')
}
