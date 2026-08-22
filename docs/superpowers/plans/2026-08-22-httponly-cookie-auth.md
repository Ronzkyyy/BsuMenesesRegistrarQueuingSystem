# httpOnly Cookie Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move staff auth off `localStorage` (JS-readable, a standing XSS-exposure risk) onto an httpOnly, `SameSite=Strict` cookie, without changing the JWT itself.

**Architecture:** The JWT's creation/validation logic (`core/security.py`'s `create_access_token`/`decode_access_token`) is untouched. Only transport changes: `POST /api/auth/login` sets the JWT via `Set-Cookie` instead of returning it in the response body; `get_current_user` reads it from the cookie instead of an `Authorization` header; the frontend drops all token handling and relies on the browser to send the cookie automatically (`withCredentials: true`).

**Tech Stack:** FastAPI (`Response.set_cookie`/`delete_cookie`), Vue 3 + Pinia + axios (`withCredentials`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-22-httponly-cookie-auth-design.md`

## Global Constraints

- Cookie name: `registrar_token`.
- Cookie attributes: `httponly=True, secure=True, samesite="strict", max_age=1800, path="/"` (1800s = 30 minutes, matching `ACCESS_TOKEN_EXPIRE_MINUTES`/the existing hardcoded 30-minute login expiry).
- No CSRF token, no refresh-token flow — `SameSite=Strict` is the complete CSRF defense for this same-origin, JSON-only API (see spec's Decision section).
- `access_token` must never appear in any response body after this change.
- All file paths below are relative to the repo root (`thesis project/`), i.e. prefixed with `bsu-registrar-queue/`.
- No automated test framework covers HTTP-level auth (pytest is service-layer only, Vitest mocks axios) — this plan's verification is against the real running stack, per this project's standing convention (see `docs/superpowers/plans/2026-08-03-student-list-pagination.md` and later plans for the established pattern).

---

### Task 1: Backend — cookie-based login/logout/get_current_user

**Files:**
- Modify: `bsu-registrar-queue/backend/app/core/security.py`
- Modify: `bsu-registrar-queue/backend/app/api/auth.py`
- Modify: `bsu-registrar-queue/backend/app/models/user.py`

**Interfaces:**
- Consumes: existing `create_access_token`, `decode_access_token`, `TokenData` (all unchanged), `UserDB`, `User` model.
- Produces: `get_current_user` now depends on a cookie-reading dependency instead of `oauth2_scheme`/`Authorization` header. `POST /auth/login` sets the `registrar_token` cookie and returns `User` (not `Token`). `POST /auth/logout` clears the cookie. Task 2's frontend store consumes this via `withCredentials: true` — no header logic needed on the client side at all.

- [ ] **Step 1: Remove the `Token` response model (keep `TokenData`)**

In `bsu-registrar-queue/backend/app/models/user.py`, remove this class (do NOT remove `TokenData` below it — `decode_access_token` in `core/security.py` still returns it):

```python
class Token(BaseModel):
    access_token: str
    token_type: str
```

- [ ] **Step 2: Replace the Bearer-header dependency with a cookie-reading one**

In `bsu-registrar-queue/backend/app/core/security.py`, change the imports:

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from ..db_models import UserDB
from ..models.user import User, TokenData


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
```

to:

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from ..db_models import UserDB
from ..models.user import User, TokenData


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
COOKIE_NAME = "registrar_token"


def get_token_from_cookie(request: Request) -> str:
    """Extract the JWT from the httpOnly session cookie, 401 if absent."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return token
```

Then change `get_current_user`'s signature from:

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
```

to:

```python
async def get_current_user(
    token: str = Depends(get_token_from_cookie),
    db: Session = Depends(get_db)
) -> User:
```

The rest of `get_current_user`'s body is unchanged (`decode_access_token(token)`, look up `UserDB`, return `User`).

- [ ] **Step 3: Update `core/__init__.py`'s export of `oauth2_scheme`**

`bsu-registrar-queue/backend/app/core/__init__.py` imports and re-exports `oauth2_scheme` from `security.py` (confirmed via `grep -rn "oauth2_scheme" app/` before writing this plan — it appears at `app/core/__init__.py:10` and `:22`, in addition to `security.py`). Since `oauth2_scheme` no longer exists, remove both references: the import line containing `oauth2_scheme,` and the `"oauth2_scheme",` entry in `__all__`.

- [ ] **Step 4: Set the cookie on login, return `User` instead of `Token`**

In `bsu-registrar-queue/backend/app/api/auth.py`, change the imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
```

to:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Form
```

and:

```python
from ..models.user import Token, TokenData, User, UserCreate, PasswordChange, UserRole as UserRoleModel
```

to:

```python
from ..models.user import User, UserCreate, PasswordChange, UserRole as UserRoleModel
from ..core.security import COOKIE_NAME
```

(add this alongside the existing `from ..core.security import (...)` block already present, or as its own line right after it).

Replace the `login` function:

```python
@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    portal: str | None = Form(None),
    db: Session = Depends(get_db)
):
    """Staff login endpoint - returns JWT token"""
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    if portal == "admin" and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account does not have Admin portal access."
        )

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
```

with:

```python
@router.post("/login", response_model=User)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    portal: str | None = Form(None),
    db: Session = Depends(get_db)
):
    """Staff login endpoint - sets an httpOnly session cookie"""
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    if portal == "admin" and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account does not have Admin portal access."
        )

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=1800,
        path="/",
    )

    return User(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=UserRoleModel(user.role.value),
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
```

Replace the `logout` function:

```python
@router.post("/logout")
def logout():
    """Staff logout endpoint (client-side token removal)"""
    return {"message": "Successfully logged out"}
```

with:

```python
@router.post("/logout")
def logout(response: Response):
    """Staff logout endpoint - clears the session cookie"""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Successfully logged out"}
```

- [ ] **Step 5: Start the backend and verify against the real database**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
uvicorn app.main:app --port 8000
```

Expected: starts with no import errors (this catches any leftover `Token`/`oauth2_scheme` reference immediately, since FastAPI imports the whole router tree at startup).

In a second terminal:

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
python -c "
import http.cookiejar, json, urllib.request, urllib.parse

BASE = 'http://localhost:8000/api'
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# Login - body should be User, not a token
login_data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request(f'{BASE}/auth/login', data=login_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
resp = opener.open(req, timeout=5)
body = json.loads(resp.read())
assert 'access_token' not in body, f'access_token leaked into response body: {body}'
assert body['username'] == 'admin', f'expected User body, got {body}'
print('OK - login response has no access_token, returns User:', body['username'])

cookie_names = [c.name for c in jar]
assert 'registrar_token' in cookie_names, f'cookie not set, jar has: {cookie_names}'
cookie = next(c for c in jar if c.name == 'registrar_token')
assert cookie.get_nonstandard_attr('HttpOnly') is not False  # http.cookiejar exposes HttpOnly via _rest on some versions; presence in jar + no client-JS access is the real guarantee, verified in Task 4's browser check
print('OK - registrar_token cookie set, expires in', cookie.expires)

# Authenticated request using the cookie jar (no manual header)
req = urllib.request.Request(f'{BASE}/auth/me')
resp = opener.open(req, timeout=5)
me = json.loads(resp.read())
assert me['username'] == 'admin'
print('OK - /auth/me works via cookie, no Authorization header sent')

# Logout clears it
req = urllib.request.Request(f'{BASE}/auth/logout', method='POST')
opener.open(req, timeout=5)
cookie_names_after = [c.name for c in jar if c.name == 'registrar_token']
print('OK - cookie jar after logout:', cookie_names_after or '(cleared)')

# A request without the cookie must 401
req = urllib.request.Request(f'{BASE}/auth/me')
try:
    urllib.request.urlopen(req, timeout=5)
    raise AssertionError('expected 401 for unauthenticated /auth/me')
except urllib.error.HTTPError as e:
    assert e.code == 401
    print('OK - unauthenticated request correctly rejected with 401')

# A tampered/garbage cookie value must 401 cleanly too, not hang or 500
tamper_req = urllib.request.Request(f'{BASE}/auth/me', headers={'Cookie': 'registrar_token=not-a-real-jwt'})
try:
    urllib.request.urlopen(tamper_req, timeout=5)
    raise AssertionError('expected 401 for a tampered cookie value')
except urllib.error.HTTPError as e:
    assert e.code == 401
    print('OK - tampered cookie value correctly rejected with 401, not a 500 or hang')
"
```

Expected: every `OK` line prints, no `AssertionError`, no traceback.

- [ ] **Step 6: Run the existing backend test suite**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
python -m pytest
```

Expected: `36 passed` — this task doesn't touch anything the service-layer tests exercise, so this is a regression check, not new coverage.

- [ ] **Step 7: Commit**

```bash
git add bsu-registrar-queue/backend/app/core/security.py bsu-registrar-queue/backend/app/core/__init__.py bsu-registrar-queue/backend/app/api/auth.py bsu-registrar-queue/backend/app/models/user.py
git commit -m "feat(auth): move JWT transport from Authorization header to httpOnly cookie"
```

---

### Task 2: Frontend — Pinia store (queue.js)

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js`

**Interfaces:**
- Consumes: Task 1's cookie-based backend (no request-side changes needed beyond `withCredentials: true` — the browser handles the cookie automatically).
- Produces: `isAuthenticated` getter now reflects `!!state.currentUser` (was `!!state.token`). `login(username, password, portal)` still returns the response data, but that data is now the `User` object, and `currentUser` is set directly instead of via a follow-up `fetchCurrentUser()` call. `logout()` remains synchronous from the caller's perspective but now also fires the backend call to clear the cookie. Task 3's router guard consumes `isAuthenticated` and `fetchCurrentUser()` (both already exist, only their internals changed).

- [ ] **Step 1: Add `withCredentials` and remove the token interceptor**

Replace:

```javascript
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

const TOKEN_KEY = 'registrar_token'

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

with:

```javascript
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  withCredentials: true,
})
```

- [ ] **Step 2: Drop the `token` state field**

Replace:

```javascript
    // Auth
    token: localStorage.getItem(TOKEN_KEY) || null,
    currentUser: null,
```

with:

```javascript
    // Auth
    currentUser: null,
```

- [ ] **Step 3: Update `isAuthenticated`**

Replace:

```javascript
    // Auth getters
    isAuthenticated: (state) => !!state.token,
```

with:

```javascript
    // Auth getters
    isAuthenticated: (state) => !!state.currentUser,
```

- [ ] **Step 4: Update `login` to set `currentUser` directly and `logout` to call the backend**

Replace:

```javascript
    async login(username, password, portal = null) {
      this.loading = true
      this.error = null
      try {
        const form = new URLSearchParams()
        form.append('username', username)
        form.append('password', password)
        if (portal) form.append('portal', portal)
        const response = await api.post('/auth/login', form, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
        this.token = response.data.access_token
        localStorage.setItem(TOKEN_KEY, this.token)
        await this.fetchCurrentUser()
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Invalid username or password'
        throw err
      } finally {
        this.loading = false
      }
    },
```

with:

```javascript
    async login(username, password, portal = null) {
      this.loading = true
      this.error = null
      try {
        const form = new URLSearchParams()
        form.append('username', username)
        form.append('password', password)
        if (portal) form.append('portal', portal)
        const response = await api.post('/auth/login', form, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
        this.currentUser = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Invalid username or password'
        throw err
      } finally {
        this.loading = false
      }
    },
```

Replace:

```javascript
    logout() {
      this.token = null
      this.currentUser = null
      localStorage.removeItem(TOKEN_KEY)
      this.stopPolling()
    },
```

with:

```javascript
    async logout() {
      try {
        await api.post('/auth/logout')
      } catch (err) {
        // Cookie may already be expired/cleared - not a reason to block local cleanup.
      }
      this.currentUser = null
      this.stopPolling()
    },
```

`fetchCurrentUser()` (right below `login` in the file) is unchanged - it already does `const response = await api.get('/auth/me'); this.currentUser = response.data` and is still used by the router guards in Task 3.

- [ ] **Step 5: Check for any other caller of `logout()` expecting it to be synchronous**

```bash
cd bsu-registrar-queue/frontend
grep -rn "\.logout()" src/
```

Expected: any call site (e.g. a "Logout" button's click handler) either already does `await store.logout()` / is itself `async`, or just fires-and-forgets without depending on synchronous completion. If a call site does depend on synchronous behavior (e.g. immediately checks `isAuthenticated` on the next line), add `await` there - `isAuthenticated` now depends on `currentUser`, which `logout()` still clears synchronously before the awaited network call in the code above only if you reorder it; as written, `currentUser = null` happens **after** the `await api.post(...)`, so a caller relying on immediate synchronous clearing needs `await store.logout()`. Check the actual call sites found above and add `await` to any that aren't already using it.

- [ ] **Step 6: Run the existing frontend test suite**

```bash
cd bsu-registrar-queue/frontend
npm test
```

Expected: some of the existing `login`/`logout` tests in `src/stores/__tests__/queue.spec.js` will now FAIL, because they assert on the old `token`/`localStorage` behavior (e.g. `expect(store.token).toBe('tok-1')`, `expect(localStorage.getItem('registrar_token')).toBe('tok-1')`). This is expected at this point in the task - fix them in the next step.

- [ ] **Step 7: Update the existing auth tests to match the new behavior**

In `bsu-registrar-queue/frontend/src/stores/__tests__/queue.spec.js`, replace the `login` describe block's two tests:

```javascript
  it('login stores the token and fetches the current user', async () => {
    mockApi.post.mockReturnValueOnce(ok({ access_token: 'tok-1' }))
    mockApi.get.mockReturnValueOnce(ok({ id: 1, username: 'admin' }))
    const store = useQueueStore()

    const result = await store.login('admin', 'admin123', 'admin')

    expect(mockApi.post).toHaveBeenCalledWith(
      '/auth/login',
      expect.any(URLSearchParams),
      expect.objectContaining({ headers: expect.any(Object) })
    )
    expect(store.token).toBe('tok-1')
    expect(localStorage.getItem('registrar_token')).toBe('tok-1')
    expect(store.currentUser).toEqual({ id: 1, username: 'admin' })
    expect(result.access_token).toBe('tok-1')
    expect(store.loading).toBe(false)
  })

  it('login surfaces the server error message and rethrows', async () => {
    mockApi.post.mockReturnValueOnce(fail('Invalid credentials'))
    const store = useQueueStore()

    await expect(store.login('admin', 'wrong')).rejects.toThrow()

    expect(store.error).toBe('Invalid credentials')
    expect(store.token).toBeNull()
    expect(store.loading).toBe(false)
  })
```

with:

```javascript
  it('login sets currentUser from the response body (no token in it)', async () => {
    mockApi.post.mockReturnValueOnce(ok({ id: 1, username: 'admin' }))
    const store = useQueueStore()

    const result = await store.login('admin', 'admin123', 'admin')

    expect(mockApi.post).toHaveBeenCalledWith(
      '/auth/login',
      expect.any(URLSearchParams),
      expect.objectContaining({ headers: expect.any(Object) })
    )
    expect(store.currentUser).toEqual({ id: 1, username: 'admin' })
    expect(result).toEqual({ id: 1, username: 'admin' })
    expect(store.loading).toBe(false)
  })

  it('login surfaces the server error message and rethrows', async () => {
    mockApi.post.mockReturnValueOnce(fail('Invalid credentials'))
    const store = useQueueStore()

    await expect(store.login('admin', 'wrong')).rejects.toThrow()

    expect(store.error).toBe('Invalid credentials')
    expect(store.currentUser).toBeNull()
    expect(store.loading).toBe(false)
  })
```

And replace the `logout` test:

```javascript
  it('logout clears token, user, and persisted storage', () => {
    const store = useQueueStore()
    store.token = 'tok-1'
    store.currentUser = { id: 1 }
    localStorage.setItem('registrar_token', 'tok-1')

    store.logout()

    expect(store.token).toBeNull()
    expect(store.currentUser).toBeNull()
    expect(localStorage.getItem('registrar_token')).toBeNull()
  })
```

with:

```javascript
  it('logout calls the backend and clears currentUser', async () => {
    mockApi.post.mockReturnValueOnce(ok({ message: 'Successfully logged out' }))
    const store = useQueueStore()
    store.currentUser = { id: 1 }

    await store.logout()

    expect(mockApi.post).toHaveBeenCalledWith('/auth/logout')
    expect(store.currentUser).toBeNull()
  })
```

Also update the `isAuthenticated` getter test:

```javascript
  it('isAuthenticated reflects whether a token is present', () => {
    const store = useQueueStore()
    expect(store.isAuthenticated).toBe(false)
    store.token = 'abc123'
    expect(store.isAuthenticated).toBe(true)
  })
```

to:

```javascript
  it('isAuthenticated reflects whether currentUser is loaded', () => {
    const store = useQueueStore()
    expect(store.isAuthenticated).toBe(false)
    store.currentUser = { id: 1, username: 'admin' }
    expect(store.isAuthenticated).toBe(true)
  })
```

- [ ] **Step 8: Run the frontend test suite again**

```bash
cd bsu-registrar-queue/frontend
npm test
```

Expected: `15 passed` (same count as before - two tests were replaced 1:1, not added/removed).

- [ ] **Step 9: Commit**

```bash
git add bsu-registrar-queue/frontend/src/stores/queue.js bsu-registrar-queue/frontend/src/stores/__tests__/queue.spec.js
git commit -m "feat(auth): update Pinia store for cookie-based auth"
```

---

### Task 3: Frontend — router guard and the stray direct-axios call

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/views/QueueManagementView.vue`

**Interfaces:**
- Consumes: Task 2's `isAuthenticated` getter and `fetchCurrentUser()` action (both already exist; only their semantics changed).
- Produces: nothing new consumed by later tasks - Task 4 verifies this end-to-end in the browser.

- [ ] **Step 1: Make the `requiresAuth` guard resolve auth the same way the role guards already do**

In `bsu-registrar-queue/frontend/src/router/index.js`, replace:

```javascript
router.beforeEach(async (to) => {
  const queueStore = useQueueStore()

  if (to.meta.requiresAuth && !queueStore.isAuthenticated) {
    return { name: 'login' }
  }
```

with:

```javascript
router.beforeEach(async (to) => {
  const queueStore = useQueueStore()

  if (to.meta.requiresAuth && !queueStore.isAuthenticated) {
    try {
      await queueStore.fetchCurrentUser()
    } catch (err) {
      return { name: 'login' }
    }
  }
```

(The rest of the guard - `requiresAdmin`/`requiresRegistrarOrAdmin` blocks - is unchanged; they already call `fetchCurrentUser()` the same way when `currentUser` isn't loaded.)

- [ ] **Step 2: Fix the one direct-axios call that bypassed the store**

In `bsu-registrar-queue/frontend/src/views/QueueManagementView.vue`, replace:

```javascript
// Booking settings is a one-off admin action with no other frontend
// consumer, so it calls the API directly rather than adding a rarely-used
// store action - reuses the store's auth token the same way the store's own
// axios instance does.
const api_patchBookingSettings = (queueId, payload) => {
  const token = localStorage.getItem('registrar_token')
  return axios.patch(`/api/queues/${queueId}/booking-settings`, payload, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
}
```

with:

```javascript
// Booking settings is a one-off admin action with no other frontend
// consumer, so it calls the API directly rather than adding a rarely-used
// store action - the session cookie rides along automatically via
// withCredentials, same as every other request.
const api_patchBookingSettings = (queueId, payload) => {
  return axios.patch(`/api/queues/${queueId}/booking-settings`, payload, {
    withCredentials: true,
  })
}
```

- [ ] **Step 3: Confirm no other file reads `registrar_token` from `localStorage`**

```bash
cd bsu-registrar-queue/frontend
grep -rn "registrar_token\|TOKEN_KEY" src/
```

Expected: no matches outside `src/stores/__tests__/queue.spec.js` (which no longer references it either, after Task 2 - if it still does, that's a leftover from Task 2 Step 7 to clean up). If any other `.vue`/`.js` file matches, it's an undocumented call site this plan didn't account for - stop and read that file before proceeding, since it means there's a fourth place needing the same fix as Step 2.

- [ ] **Step 4: Build the frontend to catch any syntax/reference errors**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: builds successfully, no errors. (This doesn't run in dev/watch mode, so it's a fast way to catch a typo or bad import before manual browser testing.)

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/frontend/src/router/index.js bsu-registrar-queue/frontend/src/views/QueueManagementView.vue
git commit -m "feat(auth): resolve auth via /auth/me in router guard, fix stray direct-axios call"
```

---

### Task 4: End-to-end verification against the real running stack

**Files:** none (verification only)

**Interfaces:**
- Consumes: the entire feature built in Tasks 1-3.
- Produces: nothing new - confirms the feature works end-to-end in a real browser before being considered done, per the spec's Testing section (this exact layer has no automated coverage).

- [ ] **Step 1: Start the full stack and drive it with the project's Playwright skill**

Follow `.claude/skills/run-bsu-registrar-queue/SKILL.md` to start backend (`:8000`) and frontend (`:5173`) if not already running (check first - see that skill's "check first" guidance before starting anything).

- [ ] **Step 2: Verify login sets an httpOnly cookie, not a readable one**

```bash
cd .claude/skills/run-bsu-registrar-queue
node driver.mjs <<'EOF'
nav http://localhost:5173/login
wait-for #username
fill #username admin
fill #password admin123
select #portal admin
click button[type="submit"]
wait-for text=Dashboard
screenshot logged-in
console
EOF
```

Expected: `console` prints `[]` (no errors), and login lands on the Dashboard (proves the cookie round-tripped correctly through the CORS-with-credentials + SameSite=Strict + same-origin dev-proxy setup).

- [ ] **Step 3: Confirm the cookie is genuinely httpOnly (unreadable by page JS)**

The driver doesn't expose a raw JS-eval command, so check this via the browser's own devtools instead: open `http://localhost:5173/login`, log in as `admin`/`admin123`/portal `admin`, then open DevTools → Application (Chrome) or Storage (Firefox) → Cookies → `http://localhost:5173`. Confirm:
- A cookie named `registrar_token` is present, with `HttpOnly` checked and `SameSite` = `Strict`.
- In the DevTools Console, `document.cookie` does **not** include `registrar_token` (it may be empty or list only non-httpOnly cookies, if any).

- [ ] **Step 4: Verify role-gated pages still redirect correctly**

```bash
cd .claude/skills/run-bsu-registrar-queue
node driver.mjs <<'EOF'
nav http://localhost:5173/login
wait-for #username
fill #username staff
fill #password staff123
click button[type="submit"]
wait-for text=Dashboard
nav http://localhost:5173/admin/users
sleep 800
screenshot staff-blocked-from-users
console
EOF
```

Expected: the `staff` account (not admin) gets redirected away from `/admin/users` (per the existing `requiresAdmin` guard) - screenshot should show the Dashboard, not the User Management page. This confirms `fetchCurrentUser()` via cookie correctly populates `currentUser.role` and the guard still enforces it.

- [ ] **Step 5: Verify logout actually clears the cookie server-side**

```bash
cd .claude/skills/run-bsu-registrar-queue
node driver.mjs <<'EOF'
nav http://localhost:5173/login
wait-for #username
fill #username admin
fill #password admin123
select #portal admin
click button[type="submit"]
wait-for text=Dashboard
click button:has-text("Logout")
sleep 500
nav http://localhost:5173/admin
sleep 800
screenshot after-logout-redirect
console
EOF
```

Expected: screenshot shows the `/login` page (the guard's `fetchCurrentUser()` call 401s since the cookie is gone, redirecting to login), not the admin dashboard.

- [ ] **Step 6: Verify the QueueManagementView booking-settings save still works**

```bash
cd .claude/skills/run-bsu-registrar-queue
node driver.mjs <<'EOF'
nav http://localhost:5173/login
wait-for #username
fill #username admin
fill #password admin123
select #portal admin
click button[type="submit"]
wait-for text=Dashboard
nav http://localhost:5173/admin/queues
wait-for text=Document Request
click div:has-text("Clearance") >> button:has-text("Manage Booking")
sleep 500
click button:has-text("Save")
sleep 1500
screenshot booking-settings-save-still-works
console
EOF
```

Expected: no console errors, modal closes without error (confirms the fixed `api_patchBookingSettings` call from Task 3 Step 2 works with `withCredentials` instead of the old manual header).

- [ ] **Step 7: Clean up screenshots**

```bash
rm -rf .claude/skills/run-bsu-registrar-queue/screenshots
```

- [ ] **Step 8: Re-run both automated test suites one final time**

```bash
cd bsu-registrar-queue/backend && source .venv/Scripts/activate && python -m pytest
cd ../frontend && npm test
```

Expected: `36 passed` (backend), `15 passed` (frontend).

- [ ] **Step 9: Final commit (docs only, if any notes were added during verification)**

If everything passed with no code changes needed beyond Tasks 1-3, there is nothing to commit for this task. If manual verification surfaced a bug, fix it as part of the relevant earlier task (re-open that task, fix, re-verify, commit there) rather than bolting a fix onto this task.
