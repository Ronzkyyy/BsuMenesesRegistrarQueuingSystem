// Canonical list of student-facing services offered at the kiosk. Several
// services share one underlying queue (see queueType) - this is the single
// source of truth for that mapping, used by both the student registration
// wizard and admin Queue Management.
import {
  ClearanceIcon,
  DocumentIcon,
  EnrollmentIcon,
  AddDropIcon,
  PetitionIcon,
} from '@/components/icons/QueueIcons'

export const SERVICES = [
  { key: 'clearance', label: 'Clearance', description: 'Academic clearance processing for graduating or transferring students.', icon: ClearanceIcon, queueType: 'clearance' },
  { key: 'request_documents', label: 'Request Documents', description: 'Request official documents such as COR, COG, TOR, Diploma, and more.', icon: DocumentIcon, queueType: 'document_request' },
  { key: 'adding_dropping', label: 'Adding & Dropping', description: 'Process for adding or dropping subjects.', icon: AddDropIcon, queueType: 'adding_dropping' },
  { key: 'enrollment', label: 'Enrollment', description: 'Enrollment assistance and subject verification.', icon: EnrollmentIcon, queueType: 'enrollment' },
  { key: 'petition_class', label: 'Petition Class', description: 'File a petition for class consideration.', icon: PetitionIcon, queueType: 'petition_class' },
]

export function getServicesForQueueType(queueType) {
  return SERVICES.filter((s) => s.queueType === queueType)
}
