// Shared self-registration form data for the two public flows that can
// register a new student on the spot - the kiosk ticket wizard (QueuesView)
// and the appointment booking form (AppointmentsView). One source of truth
// so a course/major/year-level addition doesn't have to be made twice.
export const BIT_COURSE_VALUE = 'Bachelor of Industrial Technology'

export const courseOptions = [
  { value: 'Bachelor of Science in Information Technology', label: 'BS Information Technology' },
  { value: 'Bachelor of Science in Hospitality Management', label: 'BS Hospitality Management' },
  { value: 'Bachelor of Science in Business Administration', label: 'BS Business Administration' },
  { value: 'Bachelor of Science in Computer Engineering', label: 'BS Computer Engineering' },
  { value: BIT_COURSE_VALUE, label: 'Bachelor of Industrial Technology (BIT)' },
]

export const majorOptions = [
  { value: 'BIT Computer Technology', label: 'BIT Computer Technology' },
  { value: 'Food Processing Technology', label: 'Food Processing Technology' },
]

export const yearLevelOptions = [
  { value: '1st_year', label: '1st Year' },
  { value: '2nd_year', label: '2nd Year' },
  { value: '3rd_year', label: '3rd Year' },
  { value: '4th_year', label: '4th Year' },
  { value: '5th_year', label: '5th Year' },
  { value: 'graduate', label: 'Graduate' },
]

export const emptyRegistrationForm = () => ({
  student_id: '',
  first_name: '',
  last_name: '',
  email: '',
  student_type: 'undergraduate',
  course: 'Bachelor of Science in Information Technology',
  major: null,
  year_level: '1st_year',
  // No is_scholar/is_varsity/is_graduating here - those drive queue priority
  // and can only be set by staff (Student Management), never self-declared
  // at a public form. The backend rejects them on this endpoint too.
})
