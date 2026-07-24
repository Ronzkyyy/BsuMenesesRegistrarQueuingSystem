# Student Registration Redesign — Design Spec

**Date:** 2026-07-24
**Status:** Approved by user, ready for implementation planning

## Background

The user provided a reference mockup (`interface proposal.jpg`, 4 screenshots: Select a Service → Provide Information → Confirm Information → Queue Number Generated) and asked for the student-facing registration flow to be redesigned to match it visually (white background, centered rounded card, light-pink/maroon theme, matching the Admin Login page's look) and to replace the current single flat list of services with 8 clickable service cards: Clearance, Request Documents, Adding & Dropping, Enrollment, General Inquiry, Scholarship, Petition Class, Others.

Two real constraints shaped this design, discovered while reconciling the mockup against the current codebase:

1. **8 UI categories, 5 real backend queues.** The backend only has 5 `QueueDBType` values (Enrollment, Document Request, Clearance, Scholarship, Others) and no backend changes are permitted. Several of the 8 requested service cards must therefore share an underlying queue, with the specific choice recorded in the existing free-text `purpose` field on the ticket.
2. **The mockup's Step 2 omits fields the backend actually requires for new-student registration.** The reference only shows Student Number / Full Name / Email / Purpose — but registering a *new* student today also requires Course (backend `nullable=False`) and optionally captures Year Level, Major, and the `is_scholar`/`is_varsity`/`is_graduating` priority flags, which materially affect queue priority. The mockup's example happens to depict an already-registered student, which is why those fields don't appear in it. This spec's Step 2 restores those fields for genuinely new students while keeping the mockup's simpler view for returning ones.

## Current State (before this change)

- `frontend/src/views/QueuesView.vue` (route `/queues`): a flat grid of the 5 real active queues, each a card with `getQueueIcon(queue.queue_type)`/`formatQueueType`, live stats (tickets issued, capacity, slot time), and a "Join Queue" button that navigates to `/queues/:id`.
- `frontend/src/views/QueueDetailView.vue` (route `/queues/:id`): queue info card + either (a) an active-ticket status view (position, estimated wait, status badge, priority, Cancel/Refresh/Take-Another/View-All-My-Tickets buttons) or (b) a "Take a Ticket" flow — search by 10-digit Student Number, and if not found, a "Register New Student" modal (First Name, Last Name, Email, Course, Year Level, Major (if BIT), Scholar/Varsity/Graduating checkboxes) — followed by a "Take Ticket" button. Also hosts a "My Tickets" modal (all active tickets across every queue).
- `frontend/src/views/HomeView.vue` also renders its own grid of active queue cards, each linking directly to `/queues/${queue.id}` — a homepage shortcut into the same detail page.
- `frontend/src/views/LoginView.vue` is the visual reference for the new look: `bg-gray-50` page background with two large blurred decorative circles (`bg-bsu-primary/10`, `bg-bsu-gold/10`), a centered white `rounded-2xl` card (`shadow-lg border border-gray-100`), BSU + Meneses logos, `text-bsu-primary` heading, `bsu-primary`/`bsu-gold` accent colors throughout.
- `frontend/src/components/icons/QueueIcons.js` exports 5 stroke-icon components (Enrollment, Document, Clearance, Scholarship, Others) keyed by `queue_type`, built via a shared `strokeIcon(pathD)` render-function helper (needed because Vite's runtime-only Vue build can't compile string templates).
- Backend: `TicketBase.purpose: Optional[str] = None` (Pydantic), `TicketDB.purpose = Column(Text)` (no length constraint at the DB level — any frontend character limit is a UI-only guard, not backend-enforced). `StudentBase` requires `course` (not nullable) and validates `major` is set only when `course` is Bachelor of Industrial Technology. Ticket priority is computed from `is_graduating`/`is_scholar`/`is_varsity` on the student record.
- No automated test framework is configured for this project; verification is manual against the real running dev stack, per every prior feature in this project's history.

## Scope

Redesign the student-facing "pick a service and take a ticket" flow into a single 4-step wizard component matching the reference mockup's visual style and step structure, replacing `QueuesView.vue`'s content in place (same route, `/queues`) and retiring `QueueDetailView.vue` and its `/queues/:id` route entirely. All 8 requested service cards are presented; each maps to one of the 5 real queues per the table below. No backend, route (other than removing `/queues/:id`), or API-call changes beyond what's needed to keep existing store actions working from the new component. All current functionality (returning-student detection, priority-flag registration, active-ticket status/cancel/refresh, take-another-ticket, view-all-my-tickets) is preserved, just re-skinned and re-arranged into the new step flow.

### Service → queue → purpose mapping

| Service card | Backend queue (`queue_type`) | Purpose text seeded into Step 2 |
|---|---|---|
| Clearance | Clearance | "Clearance" |
| Request Documents | Document Request | The chosen document type's label (e.g. "COR") |
| Adding & Dropping | Enrollment | "Adding & Dropping" |
| Enrollment | Enrollment | "Enrollment" |
| Petition Class | Enrollment | "Petition Class" |
| General Inquiry | Others | "General Inquiry" |
| Scholarship | Scholarship | "Scholarship Requirement" |
| Others | Others | The student's own typed-in reason (required, no default) |

Document Type options for Request Documents (a dropdown, revealed inline under the card once selected): COR, COG, TOR, Diploma, Good Moral, Graduation Form, Form 137.

## Design

### Visual shell

Same recipe as `LoginView.vue`: `min-h-screen bg-gray-50 flex items-center justify-center relative overflow-hidden`, two blurred decorative circles (`bg-bsu-primary/10`, `bg-bsu-gold/10`), a centered white card (`bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden`) — sized `max-w-4xl` instead of Login's `max-w-md` to comfortably fit the 8-card grid and the Step 2 form. BSU + Meneses logos and a `STEP N` badge (small `bg-bsu-primary text-white` pill, matching the mockup) sit above the `text-bsu-primary` heading on every step. `bsu-gold` is used for secondary accents (e.g. the "Up Next"-style highlight already used elsewhere in this project).

### Step 1: Select a Service

An 8-card grid (`grid-cols-2 md:grid-cols-4`, matching the mockup's 2-row layout), each card showing an icon, service name, and one-line description (static copy, not queue-sourced, since several cards share a queue). Clicking a card selects it (checkmark badge, matching mockup) and:
- If **Request Documents**: reveals a document-type `<select>` dropdown inline beneath the card grid. Must choose one before the "Next" button is enabled.
- If **Others**: reveals a required `<textarea>` inline beneath the card grid ("Please specify your purpose"). Must not be empty before "Next" is enabled.
- Every other card: "Next" is enabled immediately on selection.

New icon components are added to `QueueIcons.js`-style files for Adding & Dropping (swap arrows), General Inquiry (question-mark bubble), and Petition Class (pencil/edit) — built with the same `strokeIcon` helper pattern as the existing 5 icons, since Adding & Dropping/Enrollment/Petition Class all reuse the Enrollment queue but need visually distinct cards. Clearance, Request Documents, Enrollment, Scholarship, and Others reuse the existing `ClearanceIcon`, `DocumentIcon`, `EnrollmentIcon`, `ScholarshipIcon`, `OthersIcon`.

### Step 2: Provide Information

A summary bar at the top (matching the mockup) shows the selected service name and, if applicable, the chosen document type.

- **Student Number** input (10-digit, same validation as today). On blur/lookup (reusing the existing `searchStudent` store action):
  - **If found:** Full Name and Email display read-only, pre-filled from the existing record. No course/year/priority fields shown (already on file). If this student already has an active ticket in the mapped queue, skip directly to the Step-4-equivalent status view instead of continuing the wizard (preserves today's "don't double-register" behavior).
  - **If not found:** Full Name (as two inputs, First Name / Last Name, per the existing `registerStudent` action's actual parameters — the mockup's single "Full Name" field is a display simplification for the already-registered case shown there) + Email + Course + Year Level + Major (only when Course is BIT) + the three priority checkboxes (Scholar, Varsity, Graduating) all appear, exactly matching today's "Register New Student" modal fields, just inlined into this step instead of a popup.
- **Purpose** textarea (200-character counter, matching the mockup), pre-filled per the mapping table above (or carried over verbatim from Step 1's document-type choice / Others textarea), remaining freely editable. Required (non-empty) only when the service is Others; optional otherwise.
- Back / Next buttons (matching mockup styling).

### Step 3: Confirm Information

A modal overlay (matching the mockup exactly): checkmark icon, "Confirm Your Registration," a review list (Service, Document Type if applicable, Student Number, Student Name, Purpose), a note ("Once confirmed, a queue number will automatically be generated"), Back / "Confirm & Get Queue Number" buttons. Confirming calls the existing `registerStudent` action (only for new students) followed by the existing `takeTicket` action — identical backend calls to today's flow, just triggered from this modal instead of directly from a "Take Ticket" button.

### Step 4: Queue Number Generated

Matches the mockup: large ticket code (reusing the existing `ticket_code` field, e.g. `E-024`), a details panel (Service, Document Type, Student Number, Student Name, Purpose, Estimated Wait, Date & Time), "View My Queue" and "Return to Home" buttons. "View My Queue" leads to the existing active-ticket status view (today's Cancel Ticket / Refresh / Take Another Ticket / View All My Tickets), restyled to match the new visual shell but functionally unchanged — this is where `startPollingMyTicket` keeps running exactly as it does today.

### Routing changes

- `frontend/src/views/QueuesView.vue` is rewritten in place to host the full step-driven wizard described above (still mounted at the existing `/queues` route — no route path changes for it).
- `frontend/src/views/QueueDetailView.vue` is deleted; the `/queues/:id` route entry is removed from `frontend/src/router/index.js`.
- `frontend/src/views/HomeView.vue`'s per-queue card links change from `` `/queues/${queue.id}` `` to a flat `/queues` (since a specific real queue ID no longer maps 1:1 to a single service card — several cards share a queue — there is no well-defined specific destination to deep-link to). The cards themselves (icon, name, live stats) are otherwise unchanged.

### Error Handling

Every existing error path (student search failure, registration validation failure, ticket-taking failure, queue-at-capacity, queue-paused/closed) surfaces the same way it does today — inline red error boxes, using the same store action error messages — just re-styled to match the new visual shell. No new error states are introduced; the wizard doesn't allow "Next" past Step 1 until its inline requirements (document type / Others reason) are satisfied, per the existing project convention of disabling submit buttons rather than showing after-the-fact validation errors.

### Out of scope (deferred)

- Any backend, database, or API change of any kind.
- Any change to the `/queues/:id` route's *purpose* beyond deletion — no redirect is added, since nothing outside this app is expected to have that URL bookmarked (a student-facing dev tool).
- Changing HomeView.vue's card content/stats/layout beyond the link-target fix described above.
- A "Contact Number" field (not supported by the backend `Student` model; dropped per user decision during brainstorming).
- Any change to ticket priority calculation, queue capacity logic, or the `purpose` field's storage (still a plain `Text` column, still optional at the schema level — "required for Others" is a frontend-only UX rule, not a new backend constraint).

## Testing / Verification Plan

No automated test framework is configured for this project. Verification is manual, against the real running dev stack:

1. Load `/queues` fresh — confirm the new Login-page-style visual shell (background circles, centered white card, logos) and all 8 service cards render with correct icons/labels.
2. Select each of the 3 queue-sharing cards (Adding & Dropping, Enrollment, Petition Class) in turn and confirm Step 2's summary bar shows the correct service name each time, and that a ticket taken via each one lands in the real Enrollment queue with the correct `purpose` text.
3. Select Request Documents, confirm the document-type dropdown appears and blocks "Next" until a choice is made; complete the flow and confirm the resulting ticket's `purpose` matches the chosen document type.
4. Select Others, confirm the required textarea appears and blocks "Next" until non-empty; complete the flow and confirm the ticket's `purpose` matches what was typed.
5. Enter a Student Number that does not exist — confirm the full new-student fields (Course, Year Level, Major-if-BIT, priority checkboxes) appear in Step 2, and that submitting successfully creates the student with the correct priority flags reflected in the resulting ticket's priority.
6. Enter a Student Number that already exists and has no active ticket — confirm Full Name/Email show read-only and none of the new-student fields appear.
7. Enter a Student Number that already has an active ticket in the mapped queue — confirm the flow jumps straight to the active-ticket status view instead of re-registering.
8. From the Step 4 success screen, click "View My Queue" and confirm Cancel/Refresh/Take Another Ticket/View All My Tickets all still work exactly as they do on the current `master` branch.
9. From the homepage, click one of the individual queue cards and confirm it lands on the redesigned `/queues` wizard (Step 1) rather than a 404.
