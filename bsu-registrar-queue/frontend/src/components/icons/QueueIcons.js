// Shared queue-type icon components, keyed by queue_type value.
// Built with render functions (not the `template:` string option) because
// Vite's default Vue build is runtime-only and can't compile string templates.
import { h } from 'vue'

function strokeIcon(pathD) {
  return {
    render() {
      return h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
        h('path', {
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round',
          'stroke-width': '1.5',
          d: pathD,
        }),
      ])
    },
  }
}

export const EnrollmentIcon = strokeIcon(
  'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253'
)

export const DocumentIcon = strokeIcon(
  'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z'
)

export const ClearanceIcon = strokeIcon(
  'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
)

export const ScholarshipIcon = strokeIcon(
  'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.759 1.117a6.062 6.062 0 012.759 3.883 5.988 5.988 0 01-1.117 5.443 6.062 6.062 0 01-2.759 3.883c-.679.715-1.648 1.117-2.759 1.117s-2.08-.402-2.759-1.117a6.062 6.062 0 01-2.759-3.883 5.988 5.988 0 011.117-5.443 6.062 6.062 0 012.759-3.883C9.92 8.402 10.89 8 12 8z'
)

export const OthersIcon = strokeIcon(
  'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z'
)

export const AddDropIcon = strokeIcon(
  'M8 7h12m0 0l-4-4m4 4l-4 4M16 17H4m0 0l4 4m-4-4l4-4'
)

export const GeneralInquiryIcon = strokeIcon(
  'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z'
)

export const PetitionIcon = strokeIcon(
  'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z'
)

const ICONS_BY_TYPE = {
  enrollment: EnrollmentIcon,
  document_request: DocumentIcon,
  clearance: ClearanceIcon,
  scholarship: ScholarshipIcon,
  others: OthersIcon,
  adding_dropping: AddDropIcon,
  petition_class: PetitionIcon,
  other_concerns: OthersIcon,
}

const LABELS_BY_TYPE = {
  enrollment: 'Enrollment',
  document_request: 'Document Request',
  clearance: 'Clearance',
  scholarship: 'Scholarship',
  others: 'Others',
  adding_dropping: 'Adding & Dropping',
  petition_class: 'Petition Class',
  other_concerns: 'Others',
}

export function getQueueIcon(type) {
  return ICONS_BY_TYPE[type] || OthersIcon
}

export function formatQueueType(type) {
  return LABELS_BY_TYPE[type] || type
}
