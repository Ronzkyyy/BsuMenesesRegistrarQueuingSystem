// Canonical list of document types offered under the Request Documents
// service - shared by the kiosk registration wizard and the appointment
// booking form so both stay in sync.
//
// The Registrar produces and prints the Transcript of Records, Certificate of
// Registration and Certificate of Grades. The rest originate elsewhere, and
// what the office issues is a certified true copy - the labels say so, so a
// student knows what they are actually queueing for.
//
// `value` is stored verbatim as the ticket/appointment `document_type`, so it
// must stay stable and match the backend's DocumentType enum values: only the
// labels are wording. Changing a value would orphan every historical record
// already filed under the old one.
export const DOCUMENT_TYPES = [
  { value: 'TOR', label: 'Transcript of Records (TOR)' },
  { value: 'COR', label: 'Certificate of Registration (COR)' },
  { value: 'COG', label: 'Certificate of Grades (COG)' },
  { value: 'Diploma', label: 'Certified True Copy - Diploma' },
  { value: 'Good Moral', label: 'Certified True Copy - Good Moral Certificate' },
  { value: 'Graduation Form', label: 'Certified True Copy - Graduation Form' },
  { value: 'Form 137', label: 'Certified True Copy - Form 137' },
]
