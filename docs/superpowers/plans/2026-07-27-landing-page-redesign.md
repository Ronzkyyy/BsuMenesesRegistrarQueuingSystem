# Landing Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the student-facing `HomeView.vue` (plain hero + queue-card grid) with a single full-screen hero — gradient header, blurred arch-photo background, gradient "WELCOME TO THE / REGISTRAR QUEUING SYSTEM" text, white pill "BROWSE →" button — matching the reference mockup at `~/Downloads/studentLandingPage.gif`.

**Architecture:** Crop the arch photo out of the reference mockup image (no separate raw photo exists) into a new static asset. Add an opt-in `gradient` prop to the shared `AppHeader.vue` so only the home page's header changes color; every other page keeps the current solid header. Rewrite `HomeView.vue` as a single flex column (`header` + `flex-1` hero), removing the queue-card grid and footer (per approved spec — `/queues` already lists services).

**Tech Stack:** Vue 3 `<script setup>`, Tailwind CSS (existing `bsu-primary` / `bsu-gold` tokens from `tailwind.config.js`), Vite. Asset prep uses a one-off Python/Pillow command (not an app dependency).

## Global Constraints

- Reuse existing Tailwind tokens `bsu-primary` (#be185d) and `bsu-gold` (#f59e0b) for all gradients — no new arbitrary colors.
- `AppHeader.vue`'s default (no `gradient` prop) behavior must stay pixel-identical to today — `LoginView`, `QueuesView`, and all `/admin` pages render unchanged.
- No backend, API, or data-model changes.
- No test framework is configured for the frontend (per `CLAUDE.md`) — verification is `npm run build` (catches template/syntax errors) plus manual visual checks via `npm run dev`.

---

### Task 1: Crop the arch-photo background asset

**Files:**
- Create: `bsu-registrar-queue/frontend/src/assets/archBackground.png`

**Interfaces:**
- Produces: a 960×270 PNG at `frontend/src/assets/archBackground.png` (recropped to a shorter region of the mockup that excludes the baked-in mockup text), imported by `HomeView.vue` in Task 3 as `import archBackground from '@/assets/archBackground.png'`.

- [ ] **Step 1: Install Pillow for this one-off task**

```bash
pip install --user --quiet pillow
```

- [ ] **Step 2: Crop the photo out of the reference mockup and save it**

The reference image `~/Downloads/studentLandingPage.gif` is 960×640px. Its gradient header bar occupies rows 0–95; the arch photo (sky + arch, already including the pale background the mockup uses) occupies rows 96–640. Run:

```bash
python -c "
from PIL import Image
im = Image.open(r'C:\Users\admin\Downloads\studentLandingPage.gif').convert('RGB')
cropped = im.crop((0, 96, 960, 640))
cropped.save(r'C:\Users\admin\Desktop\thesis project\bsu-registrar-queue\frontend\src\assets\archBackground.png')
print(cropped.size)
"
```

Expected output: `(960, 544)`

- [ ] **Step 3: Verify the file was written correctly**

```bash
python -c "
from PIL import Image
im = Image.open(r'C:\Users\admin\Desktop\thesis project\bsu-registrar-queue\frontend\src\assets\archBackground.png')
print(im.size, im.mode)
"
```

Expected: `(960, 544) RGB`

- [ ] **Step 4: Commit**

```bash
git add "bsu-registrar-queue/frontend/src/assets/archBackground.png"
git commit -m "$(cat <<'EOF'
feat(landing-page): add cropped arch-photo background asset

Cropped from the reference mockup (no separate raw photo exists) —
used as the blurred hero background on the home page.
EOF
)"
```

---

### Task 2: Add a `gradient` variant to `AppHeader.vue`

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/components/AppHeader.vue`

**Interfaces:**
- Produces: `AppHeader` now accepts an optional `gradient` boolean prop (default `false`). Consumed by `HomeView.vue` in Task 3 as `<AppHeader gradient ... />`.

- [ ] **Step 1: Add the prop and conditional header class**

In `bsu-registrar-queue/frontend/src/components/AppHeader.vue`, change:

```vue
<template>
  <header class="bg-bsu-primary text-white shadow-lg">
```

to:

```vue
<template>
  <header
    :class="[
      'text-white shadow-lg',
      gradient ? 'bg-gradient-to-r from-bsu-primary to-bsu-gold' : 'bg-bsu-primary',
    ]"
  >
```

And change the `<script setup>` block from:

```vue
<script setup>
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

defineProps({
  subtitle: {
    type: String,
    default: 'Registrar Queue Management System',
  },
})
</script>
```

to:

```vue
<script setup>
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

defineProps({
  subtitle: {
    type: String,
    default: 'Registrar Queue Management System',
  },
  gradient: {
    type: Boolean,
    default: false,
  },
})
</script>
```

- [ ] **Step 2: Verify the app still builds**

```bash
cd "bsu-registrar-queue/frontend" && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 3: Manually verify no regression on an existing page**

```bash
cd "bsu-registrar-queue/frontend" && npm run dev
```

Open `http://localhost:5173/display` in a browser (or use the `claude-in-chrome`/`run` tooling if available) and confirm the header is still the plain solid pink `bg-bsu-primary` bar — identical to before this change, since `DisplayIndexView` does not pass the new `gradient` prop. (`/admin/*` pages, via `AdminLayout`, are another unaffected `AppHeader` consumer.)

- [ ] **Step 4: Commit**

```bash
git add "bsu-registrar-queue/frontend/src/components/AppHeader.vue"
git commit -m "$(cat <<'EOF'
feat(landing-page): add opt-in gradient variant to AppHeader

Adds a `gradient` prop (default false) so the home page can use a
pink-to-orange header without affecting any other page.
EOF
)"
```

---

### Task 3: Rewrite `HomeView.vue` as a full-screen hero

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/views/HomeView.vue`

**Interfaces:**
- Consumes: `AppHeader` with `gradient` prop (Task 2); `frontend/src/assets/archBackground.png` (Task 1).
- Produces: `HomeView.vue` renders only the hero (no queue-card grid, no `AppFooter`, no `useQueueStore`/`QueueIcons` usage).

- [ ] **Step 1: Replace the entire contents of `HomeView.vue`**

```vue
<template>
  <div class="min-h-screen flex flex-col">
    <AppHeader gradient subtitle="Registrar Queue Management System" />

    <main class="relative flex-1 flex items-center justify-center overflow-hidden">
      <img
        :src="archBackground"
        alt=""
        class="absolute inset-0 w-full h-full object-cover scale-110 blur-sm"
      />
      <div class="absolute inset-0 bg-white/40"></div>

      <div class="relative z-10 text-center px-4">
        <p
          class="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-bsu-primary to-bsu-gold bg-clip-text text-transparent"
        >
          WELCOME TO THE
        </p>
        <h1
          class="text-4xl sm:text-6xl font-extrabold bg-gradient-to-r from-bsu-primary to-bsu-gold bg-clip-text text-transparent leading-tight"
        >
          REGISTRAR QUEUING SYSTEM
        </h1>

        <router-link
          to="/queues"
          class="mt-8 inline-flex items-center gap-2 bg-white text-bsu-primary font-bold px-8 py-3 rounded-full shadow-lg hover:shadow-xl transition-shadow"
        >
          BROWSE
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </router-link>
      </div>
    </main>
  </div>
</template>

<script setup>
import AppHeader from '@/components/AppHeader.vue'
import archBackground from '@/assets/archBackground.png'
</script>
```

This removes the `useQueueStore`, `getQueueIcon`/`formatQueueType`, `loading`/`error`/`queues` refs, the `fetchQueues`/`onMounted` logic, the card grid, the `AppFooter` import/usage, and the `<style scoped>` `.line-clamp-2` rule (all now dead code — the queue list and its icons/formatting already live in `QueuesView.vue`, which is untouched).

- [ ] **Step 2: Verify the app builds**

```bash
cd "bsu-registrar-queue/frontend" && npm run build
```

Expected: build succeeds with no errors (no leftover references to removed imports).

- [ ] **Step 3: Manually verify the hero page**

```bash
cd "bsu-registrar-queue/frontend" && npm run dev
```

Open `http://localhost:5173/` and confirm, against `~/Downloads/studentLandingPage.gif`:
- Gradient (pink→orange) header bar with both logos and "BSU Meneses Campus" text.
- The arch photo fills the rest of the viewport, visibly zoomed and softly blurred, arch still clearly recognizable, with a soft white wash over it.
- "WELCOME TO THE" / "REGISTRAR QUEUING SYSTEM" centered both horizontally and vertically, in the pink-to-orange gradient font.
- A white rounded "BROWSE →" button directly below the text.
- Clicking "BROWSE →" navigates to `/queues` and that page still lists services normally.
- No console errors in the browser dev tools.

- [ ] **Step 4: Commit**

```bash
git add "bsu-registrar-queue/frontend/src/views/HomeView.vue"
git commit -m "$(cat <<'EOF'
feat(landing-page): rewrite home page as full-screen hero

Replaces the old hero-banner + queue-card grid with a single
full-screen composition matching the approved mockup: gradient
header, blurred arch-photo background, gradient welcome text, and
a white pill Browse button routing to /queues.
EOF
)"
```

---

## Post-plan verification

- [ ] Run `npm run build` once more from `bsu-registrar-queue/frontend` to confirm the final state compiles cleanly.
- [ ] Spot-check `/login`, `/queues`, and one `/admin/*` page to confirm their headers are still solid `bg-bsu-primary` (no regression from the new `gradient` prop).
