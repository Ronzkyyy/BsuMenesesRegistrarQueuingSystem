# Landing Page Redesign

## Context

The student-facing home page (`frontend/src/views/HomeView.vue`) currently shows a plain hero
banner (solid `bg-bsu-primary` header, dark heading text, "Browse All Services" button) followed
by a grid of queue-service cards fetched from the API.

The user supplied a finished reference mockup (`~/Downloads/studentLandingPage.gif`) showing a
full-screen hero: a pink-to-orange gradient header bar with the BSU and Meneses Campus logos and
"BSU MENESES CAMPUS" text, and below it a softly blurred, zoomed-in photo of the campus arch as a
background, with a soft white overlay, centered gradient "WELCOME TO THE / REGISTRAR QUEUING
SYSTEM" text, and a white pill "BROWSE →" button.

No raw (uncomposited) photo of the arch exists in the repo or Downloads — only the finished
mockup image, which already has the header/text/button composited onto it. Per user decision,
the arch photo will be cropped out of that mockup image rather than sourced separately.

## Goals

- Replace `HomeView.vue`'s hero + card grid with a single full-screen hero matching the reference
  mockup's composition and palette.
- Reuse the existing `bsu-primary` / `bsu-gold` Tailwind tokens (`tailwind.config.js`) for the
  gradient, rather than introducing new arbitrary colors.
- Keep the change scoped to the home page — other pages using `AppHeader` (`LoginView`,
  `QueuesView`, admin pages) must render unchanged.

## Non-goals

- No changes to `/queues` (still the destination for "BROWSE →" and still lists services).
- No changes to backend, API, or data models.
- No attempt to source a different/higher-res arch photo — the crop from the mockup gif is the
  agreed source image.

## Design

### Asset extraction

One-off script (Pillow, installed via `pip install --user pillow` for this task only — not added
to `backend/requirements.txt`) crops `studentLandingPage.gif` to just the arch-photo region
(below the ~90px gradient header bar visible in the mockup) and saves it as
`frontend/src/assets/archBackground.png`. This is a build-time asset, not a runtime dependency.

### `AppHeader.vue`

Add a `gradient` boolean prop, default `false`:
- `false` (current/all other pages): `bg-bsu-primary` — unchanged.
- `true` (Home only): `bg-gradient-to-r from-bsu-primary to-bsu-gold`.

Logo markup, "BSU Meneses Campus" text, and layout are unchanged in both cases — the reference
mockup's header layout already matches the current component (logos + name left-aligned).

### `HomeView.vue`

Rewritten to a single full-screen section — no queue-cards grid, no `AppFooter`:

- `<AppHeader gradient subtitle="Registrar Queue Management System" />` at the top.
- Below it, a section filling the remaining viewport height (`min-h-[calc(100vh-<header-height>)]`
  or equivalent), containing:
  - `archBackground.png` as an `<img>`, absolutely positioned to cover the section
    (`object-cover`), scaled up (`scale-110`) and softly blurred (`blur-sm`) — zoom hides the
    blurred edges while keeping the red arch clearly recognizable.
  - A `bg-white/40` overlay layer above the image for text readability.
  - Centered (both axes) content, above the overlay:
    - "WELCOME TO THE" — smaller bold line.
    - "REGISTRAR QUEUING SYSTEM" — larger bold line.
    - Both lines use `bg-gradient-to-r from-bsu-primary to-bsu-gold bg-clip-text text-transparent`.
    - Below the text, a white pill button: `rounded-full bg-white text-bsu-primary font-bold
      shadow-lg hover:shadow-xl`, label "BROWSE →" (arrow as existing inline SVG), `router-link`
      to `/queues`.

The queue-fetching logic (`useQueueStore`, `getQueueIcon`, `formatQueueType`, loading/error
states) is removed from `HomeView.vue` entirely since the card grid is gone — that logic already
exists independently in `QueuesView.vue`.

### Out of scope / unaffected

- `AppFooter.vue` — unchanged, just no longer rendered on `HomeView`.
- `QueuesView.vue`, `LoginView.vue`, admin views — unchanged.

## Testing

- Manual: `npm run dev`, visit `/`, confirm gradient header, blurred arch background, centered
  gradient text, white Browse button, and that clicking Browse navigates to `/queues`.
- Confirm `/login` and `/queues` headers are still the solid `bg-bsu-primary` (regression check
  on the new `gradient` prop's default).
