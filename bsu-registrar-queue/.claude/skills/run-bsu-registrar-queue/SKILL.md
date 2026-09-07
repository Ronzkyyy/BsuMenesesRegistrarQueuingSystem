---
name: run-bsu-registrar-queue
description: Build, run, and drive the BSU Registrar Queue System (FastAPI backend + Vue/Vite frontend). Use when asked to start the app, log in, take a screenshot of a page (Home, Login, admin Dashboard, Queue Management, public Queues ticket flow, Display Board), or verify a UI/API change end-to-end.
---

Full-stack app: FastAPI backend on :8000 + Vue 3/Vite frontend on :5173.
**`backend/.env`'s `DATABASE_URL` points at a remote Supabase Postgres that also backs
Render production** — a stale `backend/bsu_queue.db` file is still on disk but is not
what the app reads. Treat anything you write through the running app as production data;
to work against throwaway data, point the backend at the disposable `bsu_queue_test`
database instead (see "Isolated database" below).
Drive it with the Playwright REPL at `.claude/skills/run-bsu-registrar-queue/driver.mjs` —
same command style as `chromium-cli` (`nav`, `click`, `fill`, `screenshot`, …), piped in
via a heredoc. All paths below are relative to `bsu-registrar-queue/` (this skill's parent
project dir), not the repo root.

This is a Windows dev environment (PowerShell primary, Git Bash available) — commands
below use Git Bash syntax and Windows venv paths (`.venv/Scripts/python.exe`).

## Prerequisites

Already satisfied in this checkout — `backend/.venv` and `frontend/node_modules` exist,
`backend/.env` is present and its database is seeded. On a fresh
checkout, `./dev.ps1` from the repo root creates all of this (venv, `.env`, seeded DB,
`npm install`) idempotently — see that script if bootstrapping from scratch.

The driver itself needs its own `node_modules` (Playwright), installed once:

```bash
cd .claude/skills/run-bsu-registrar-queue
npm install
```

## Build / Run (agent path)

**Check first — these are very often already running** (started via `./dev.ps1` in
separate windows, or a prior agent session):

```bash
netstat -ano | grep -E ':8000|:5173'
```

If not running, start them (from `bsu-registrar-queue/`):

```bash
cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 &
cd frontend && npm run dev -- --port 5173 &
```

Do **not** kill an already-listening 8000/5173 unless you started it yourself this
session — it's frequently the user's own live dev session with real accumulated data
(ticket counters, timestamps), not a disposable fixture.

Then drive it:

```bash
cd .claude/skills/run-bsu-registrar-queue
node driver.mjs <<'EOF'
nav http://localhost:5173/
wait-for text=WELCOME
screenshot home
nav http://localhost:5173/login
wait-for #username
fill #username admin
fill #password admin123
select #portal admin
click button[type="submit"]
wait-for text=Dashboard
screenshot admin-dashboard
console
quit
EOF
```

Screenshots land in `.claude/skills/run-bsu-registrar-queue/screenshots/<name>.png`.
`console` prints any `pageerror`/`console.error` collected so far as a JSON array —
run it after each navigation you care about; `[]` means clean.

| command | what it does |
|---|---|
| `nav <url>` | navigate, waits for network-idle |
| `wait-for <selector>` | Playwright selector, incl. `text=...` |
| `fill <selector> <value...>` | rest of line is the value (spaces OK) |
| `select <selector> <value>` | `<select>` option value |
| `click <selector...>` | rest of line is the selector (spaces OK, e.g. `button:has-text("Login")`) |
| `hover <selector...>` | move the mouse onto it and leave it there — screenshot right after to capture `:hover` state |
| `press <key>` | keyboard key, e.g. `Enter` |
| `sleep <ms>` | fixed wait, avoid unless nothing else fits |
| `screenshot [name]` | full-page-off viewport screenshot |
| `console` | dump collected console errors as JSON |
| `quit` | close browser, exit |

Known accounts (seeded, and confirmed still valid in the live local DB as of
2026-08-14): `admin`/`admin123` (portal `admin`), `registrar`/`registrar123`,
`staff`/`staff123`.

Routes worth knowing: `/` (home), `/login`, `/queues` (public — take-a-ticket flow,
no auth), `/admin` (dashboard, requires auth → redirects to `/login`),
`/admin/queues`, `/admin/counter`, `/admin/students`, `/admin/media`, `/admin/users`
(admin-only), `/display`, `/display/:id`.

### Isolated database (when you need to write test data)

`bsu_queue_test` on the same Postgres server is disposable (pytest provisions and
migrates it). Point the backend at it by setting `DATABASE_URL` **in the process
environment** — `app/core/database.py` builds its engine from `settings` at import
time, so mutating `os.environ` inside a script that already imported the app is too
late and silently writes to production instead:

```bash
cd backend
DB=$(PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -c "
from urllib.parse import urlparse, urlunparse
from app.core.config import settings
p=urlparse(settings.DATABASE_URL); print(urlunparse(p._replace(path='/bsu_queue_test')))")
DATABASE_URL="$DB" ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 &
```

Any seeding script should assert its target before writing:
`assert "bsu_queue_test" in settings.DATABASE_URL`.

### Direct backend check (no browser)

For backend-only changes, hitting the API directly is faster than driving the UI:

```bash
node -e "fetch('http://127.0.0.1:8000/api/queues/active').then(r=>r.json()).then(j=>console.log(JSON.stringify(j,null,2)))"
```

## Run (human path)

From the repo root: `./dev.ps1` (PowerShell) — opens backend and frontend each in
their own window, seeding/installing anything missing first. Ctrl-C in each window
to stop.

## Test

No test suite is configured for either side (confirmed — no `test_*.py`/`*.spec.js`
files outside `node_modules`/`.venv`). Verification is driving the running app.

## Gotchas

- **`chromium.launch()` fails with "Executable doesn't exist ... chrome-headless-shell.exe"**
  on this machine — the cached Playwright browser build doesn't match the installed
  Playwright version. `driver.mjs` launches with `channel: 'chrome'` (system Chrome)
  instead, which works without needing `npx playwright install`.
- **Port 8000/5173 already `LISTENING`** is the common case, not an error — see "Check
  first" above. `netstat -ano | grep 8000` then, if you must find the owning process,
  `tasklist /FI "PID eq <pid>"` (Windows has no `lsof`; a bare `kill <pid>` via Git
  Bash often can't signal a native Windows process either — closing the owning
  terminal window is more reliable than trying to kill it from Bash).
- **`backend/.env` is permission-denied to the `Read` tool** in this harness (secrets
  guard) — that's expected, not a missing-file bug. Uvicorn still reads it fine.
- Login POSTs to the real remote DB — the dashboard's counters (Users, Queues,
  Waiting, etc.) reflect actual current state, not fixture zeros-by-default; don't be
  surprised if the numbers differ from a screenshot taken at another time.

## Troubleshooting

- **`ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`**:
  something (usually the user's own `dev.ps1` window) already has 8000. Don't relaunch
  — target the existing instance.
- **`wait-for` times out on `/admin` routes**: you're not authenticated — the router
  guard (`frontend/src/router/index.js`) redirects `requiresAuth` routes to `/login`.
  Run the login sequence above first; the driver keeps one browser context per run so
  the session persists across subsequent `nav` commands in the same heredoc.