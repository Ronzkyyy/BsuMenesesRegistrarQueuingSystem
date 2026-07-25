// Canonical list of student-facing services offered at the kiosk. Several
// services share one underlying queue (see queueType) - this is the single
// source of truth for that mapping, used by both the student registration
// wizard and admin Queue Management.
import {
  ClearanceIcon,
  DocumentIcon,
  EnrollmentIcon,
  ScholarshipIcon,
  OthersIcon,
  AddDropIcon,
  GeneralInquiryIcon,
  PetitionIcon,
} from '@/components/icons/QueueIcons'

export const SERVICES = [
  { key: 'clearance', label: 'Clearance', description: 'Academic clearance processing for graduating or transferring students.', icon: ClearanceIcon, queueType: 'clearance', defaultPurpose: 'Clearance' },
  { key: 'request_documents', label: 'Request Documents', description: 'Request official documents such as COR, COG, TOR, Diploma, and more.', icon: DocumentIcon, queueType: 'document_request', defaultPurpose: '' },
  { key: 'adding_dropping', label: 'Adding & Dropping', description: 'Process for adding or dropping subjects.', icon: AddDropIcon, queueType: 'enrollment', defaultPurpose: 'Adding & Dropping' },
  { key: 'enrollment', label: 'Enrollment', description: 'Enrollment assistance and subject verification.', icon: EnrollmentIcon, queueType: 'enrollment', defaultPurpose: 'Enrollment' },
  { key: 'general_inquiry', label: 'General Inquiry', description: 'Ask questions about academic concerns and services.', icon: GeneralInquiryIcon, queueType: 'others', defaultPurpose: 'General Inquiry' },
  { key: 'scholarship', label: 'Scholarship', description: 'Inquiries about scholarships and requirements.', icon: ScholarshipIcon, queueType: 'scholarship', defaultPurpose: 'Scholarship Requirement' },
  { key: 'petition_class', label: 'Petition Class', description: 'File a petition for class consideration.', icon: PetitionIcon, queueType: 'enrollment', defaultPurpose: 'Petition Class' },
  { key: 'others', label: 'Others', description: 'Other concerns not listed. Please specify your purpose.', icon: OthersIcon, queueType: 'others', defaultPurpose: '' },
]

export function getServicesForQueueType(queueType) {
  return SERVICES.filter((s) => s.queueType === queueType)
}
