# httpOnly Cookie Auth — Design

## Problem

Staff auth currently issues a JWT in the `POST /api/auth/login` JSON response body, which the frontend stores in `localStorage` and re-attaches to every request as an `Authorization: Bearer` header. `localStorage` is readable by any JavaScript running on the page — if this app (or a dependency) ever develops an XSS vulnerability, the attacker's injected script can read the token directly and impersonate the logged-in staff member for the token's full lifetime. A security audit of this codebase (2026-08-22) found no current XSS vector, but flagged this as a standing risk worth closing rather than waiting on. Moving the token into an httpOnly cookie makes it unreadable to any JavaScript, page script or injected, closing that class of attack outright.

## Decision

Keep the JWT itself unchanged (same `create_access_token`/`decode_access_token`, same HS256 algorithm, same 30-minute expiry) — only its *transport* changes. `POST /api/auth/login` sets it via `Set-Cookie` with `httponly=True; secure=True; samesite=Strict` instead of returning it in the response body; the backend reads it back from the cookie instead of an `Authorization` header; `POST /api/auth/logout` actually clears it server-side. `SameSite=Strict` is the CSRF defense — no double-submit token — since the app is deployed same-origin (confirmed) and is a JSON API with no legitimate cross-site request pattern to accommodate.

### Why SameSite=Strict alone, not a double-submit CSRF token

- **httpOnly cookie + double-submit CSRF token**: stronger in the abstract (defends even if `SameSite` enforcement were somehow bypassed, or a future deployment moves off same-origin), but adds real complexity — a second cookie, a frontend interceptor to echo it as a header, backend verification middleware — for a threat model this app doesn't have today.
- **httpOnly cookie + SameSite=Strict (chosen)**: for a same-origin, JSON-only API with no state-changing `GET` endpoints, `SameSite=Strict` alone means a cross-site page cannot get the cookie attached to any request it makes, full stop. This is not a partial mitigation for this app's shape — it's complete for the threat it defends against. If the deployment topology ever changes (cross-subdomain, embedded third-party context), this decision should be revisited.

### Why the login response returns `User` instead of a token

The handler already loads the full `User` row to build the token; returning it directly lets the frontend set `currentUser` immediately, eliminating the separate `fetchCurrentUser()` call the current flow makes right after login. The `access_token` is never present in any response body after this change — cookie-only, everywhere.

### Why the router's `requiresAuth` guard calls `/auth/me` instead of checking a client-readable flag

An httpOnly cookie can't be read by frontend JS, so `isAuthenticated` can no longer be `!!token`. The router already resolves `currentUser` lazily via `fetchCurrentUser()` for the `requiresAdmin`/`requiresRegistrarOrAdmin` guards (calling `/auth/me` if `currentUser` isn't already loaded) — extending the same pattern to the top-level `requiresAuth` guard is not a new concept, just consistency. The alternative (a second, non-httpOnly "logged in" flag cookie purely for instant client-side UX) was considered and rejected: it's an extra moving part to keep in sync for a staff-only internal tool where an extra `/auth/me` round-trip on cold page load is not a meaningful UX cost.

## Data Flow

**Login:**
1. `POST /api/auth/login` (unchanged request shape — `OAuth2PasswordRequestForm`) validates credentials as today.
2. On success, sets `Set-Cookie: registrar_token=<jwt>; HttpOnly; Secure; SameSite=Strict; Max-Age=1800; Path=/` and returns the `User` body (no token in it).
3. Frontend's `login()` action sets `currentUser` from the response directly. No separate `/auth/me` call needed.

**Authenticated request:**
4. Browser attaches `registrar_token` automatically (same-origin, cookie present) — no frontend code involved. `get_current_user` reads `request.cookies.get("registrar_token")`, 401s if missing/invalid, otherwise proceeds exactly as today (decode → look up user → return).

**Route navigation:**
5. `router.beforeEach` for `requiresAuth`: if `currentUser` isn't loaded, call `fetchCurrentUser()` (hits `/auth/me`); 401 → redirect to `/login`. Same pattern already used by the role-specific guards.

**Logout:**
6. `POST /api/auth/logout` clears the cookie via `Set-Cookie: registrar_token=; Max-Age=0`. Frontend's `logout()` action calls this endpoint (currently a no-op call, effectively becomes meaningful) and clears `currentUser`.

## Files Touched

**Backend:**
- `app/core/security.py` — replace `oauth2_scheme`/`OAuth2PasswordBearer` dependency in `get_current_user` with a cookie-reading dependency. `create_access_token`/`decode_access_token` unchanged.
- `app/api/auth.py` — `login` sets the cookie via `Response.set_cookie(...)` and returns `User`; `logout` clears it via `Response.delete_cookie(...)`.
- `app/models/user.py` — remove the now-unused `Token` response model (`TokenData` stays — `decode_access_token` still returns it internally).

**Frontend:**
- `src/stores/queue.js` — `api` axios instance gets `withCredentials: true`; delete the `Authorization` request interceptor and all `localStorage`/`TOKEN_KEY` code; `login()` sets `currentUser` from the response directly instead of calling `fetchCurrentUser()`; `isAuthenticated` getter becomes `!!state.currentUser`.
- `src/router/index.js` — `requiresAuth` branch gains the same lazy `fetchCurrentUser()` resolution the other two branches already have.
- `src/views/QueueManagementView.vue` — the one direct `axios.patch(...)` call that manually reads `localStorage` and sets its own `Authorization` header gets `withCredentials: true` and drops that manual logic.

## Edge Cases & Failure Modes

- **Expired cookie** (past `Max-Age`, or JWT `exp` elapsed) → browser stops sending it / `decode_access_token` returns `None` either way → `get_current_user` 401s exactly as an invalid/missing Bearer token does today → router guard redirects to `/login`. No behavior change from today's expiry handling, only the transport differs.
- **Cookie present but JWT invalid/tampered** → same 401 path as today's invalid-Bearer-token case.
- **Logout with no active session** → `delete_cookie` on an already-absent cookie is a no-op; endpoint still returns success, matching today's behavior.
- **Direct API testing via `/docs`** — `OAuth2PasswordBearer` currently also drives the Swagger "Authorize" button; losing it means `/docs` (DEBUG-only, off in prod) no longer offers one-click auth for manual testing. Acceptable: `/docs` is a dev convenience, not a production surface, and cookie-based auth can still be exercised by logging in through the actual frontend.
- **Any other direct API caller** (a script, Postman, a future mobile client) — previously just needed to hold and forward a Bearer token; now needs cookie jar support. Worth noting as a real trade-off, not just a frontend implementation detail — this API is no longer trivially scriptable with a bare token. No such caller exists in this codebase today.

## Testing

No existing automated test touches HTTP-level auth: the 36 pytest tests are service-layer only (call `QueueService`/`TicketService`/etc. directly against a DB session, never through `core/security.py` or the FastAPI request/response cycle), and the 15 Vitest tests mock `axios` entirely, so neither suite exercises real cookie behavior. This change needs to be verified live against the running stack:

1. **Login sets the cookie**: log in via the real frontend, confirm the browser holds an httpOnly `registrar_token` cookie (DevTools → Application → Cookies) and that it is *not* readable via `document.cookie` in the console.
2. **No token in the response body**: confirm the login network response body contains user info, not an `access_token` field.
3. **Authenticated requests work**: navigate to an admin page, confirm data loads (proves the cookie round-trips correctly on subsequent requests).
4. **Role guards still work**: log in as `staff`, confirm `/admin/users` (admin-only) redirects away; log in as `admin`, confirm it doesn't.
5. **Logout clears the cookie**: log out, confirm the cookie is gone from DevTools and a subsequent admin-page visit redirects to `/login`.
6. **Expiry**: force an expired/invalid cookie (e.g. edit it in DevTools) and confirm a protected request 401s and the app redirects to login rather than hanging or erroring uncaught.
7. **The QueueManagementView booking-settings save** (the one call site that manually handled its own auth header) still works end-to-end after being switched to `withCredentials`.
8. **Existing suites still green**: `pytest` (36/36) and `npm test` (15/15) — expected to pass unchanged since neither touches this transport layer, but must be re-confirmed after the edit.

## Risks & Irreversible Steps

- Purely additive/reversible from a data perspective — no migration, no schema change. Fully revertible by reverting the commit.
- The interactive `/docs` Swagger auth flow loses its one-click "Authorize" button (see Edge Cases) — a minor devex regression, DEBUG-only.
- Any future non-browser API consumer (a script, a mobile app, an integration) will need cookie-jar handling instead of a bare Bearer token. Worth documenting in `CLAUDE.md` if such a consumer is ever added.
- `SameSite=Strict` requires the deployment to stay same-origin (confirmed as the plan) — if that ever changes, this decision must be revisited before shipping, not after.

## Rollout Plan

1. Backend: cookie-based `login`/`logout`/`get_current_user`, remove unused `Token` models.
2. Frontend: store, router guard, and the one stray direct-axios call site.
3. Live verification against the real running stack per the Testing section above (no automated coverage for this layer exists yet).
4. Re-run `pytest` and `npm test` to confirm no regression in existing coverage.

## Out of Scope

- A double-submit CSRF token (rejected — see Decision).
- Refresh-token infrastructure / short-lived in-memory access token (a larger, more rigorous pattern than what was asked for; noted as a possible future iteration if the threat model changes).
- Any change to JWT creation, validation, algorithm, or expiry semantics.
- Automated test coverage for the cookie transport layer itself (HTTP-level auth tests) — flagged as a gap, not something this change is building out.
