// Canonical list of document types offered under the Document Request
// service - shared by the kiosk registration wizard and the appointment
// booking form so both stay in sync.
//
// The Registrar produces and prints only the Transcript of Records. Every
// other document here originates elsewhere, and what the office issues is a
// certified true copy of it - the labels say so, so a student knows what
// they are actually queueing for.
//
// `value` is stored verbatim as the ticket/appointment `purpose`, so it must
// stay stable: only the labels are wording. Changing a value would orphan
// every historical record already filed under the old one.
export const DOCUMENT_TYPES = [
  { value: 'TOR', label: 'Transcript of Records (TOR)' },
  { value: 'COR', label: 'Certified True Copy - Certificate of Registration (COR)' },
  { value: 'COG', label: 'Certified True Copy - Certificate of Grades (COG)' },
  { value: 'Diploma', label: 'Certified True Copy - Diploma' },
  { value: 'Good Moral', label: 'Certified True Copy - Good Moral Certificate' },
  { value: 'Graduation Form', label: 'Certified True Copy - Graduation Form' },
  { value: 'Form 137', label: 'Certified True Copy - Form 137' },
]
