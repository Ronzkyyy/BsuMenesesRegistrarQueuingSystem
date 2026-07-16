# Login Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the login form embedded in `AdminView.vue` with a standalone `/login` page (styled after the reference video screenshot, recolored to BSU branding) that includes a portal selector (Admin / Counter) validated against the user's role.

**Architecture:** A new Vue route/view (`LoginView.vue`) collects username/password/portal and calls an updated Pinia store action, which posts to an updated FastAPI `/api/auth/login` endpoint that now validates the requested portal against the authenticated user's role before issuing a JWT. A Vue Router navigation guard protects `/admin`, redirecting unauthenticated visitors to `/login`.

**Tech Stack:** FastAPI (Python), SQLAlchemy 2.0, Pydantic v2, Vue 3 (Vite), Pinia, Vue Router, Tailwind CSS, Axios.

## Global Constraints

- Portal dropdown has exactly two options: **Admin**, **Counter** (no "Display" option — Display board stays public/no-auth).
- `portal="admin"` requires `user.role == UserRole.ADMIN`; mismatch → `403` with detail `"This account does not have Admin portal access."`
- `portal="counter"` is allowed for any authenticated role (Admin, Registrar, Staff) — no restriction.
- `portal` is optional on the login request (omitted → no portal validation), for backward compatibility.
- Both "Admin" and "Counter" portal selections redirect to the existing unified `/admin` route on success (dashboard split is out of scope for this plan).
- Use existing BSU brand colors (`bsu.primary` #be185d, `bsu.gold` #f59e0b, defined in `frontend/tailwind.config.js`) and the real logos at `frontend/src/assets/BSUlogo.png` / `frontend/src/assets/MENESESlogo.png` — not a generic icon.
- No automated test framework is configured for this project (backend or frontend). Verification is manual, against the real running dev stack (`dev.ps1`), per project convention — do not introduce Vitest/pytest as part of this plan.
- Seeded dev accounts (created by `backend/seed.py` via `dev.ps1`): `admin/admin123` (Admin), `registrar/registrar123` (Registrar), `staff/staff123` (Staff).

---

### Task 1: Backend — portal-aware login validation

**Files:**
- Modify: `bsu-registrar-queue/backend/app/api/auth.py`

**Interfaces:**
- Produces: `POST /api/auth/login` now accepts an additional optional form field `portal: str | None` (values `"admin"` or `"counter"`, anything else treated as no-restriction). Response shape (`Token`) is unchanged. New failure mode: `403` when `portal="admin"` and the user's role isn't `UserRole.ADMIN`.

- [ ] **Step 1: Add the `Form` import**

In `bsu-registrar-queue/backend/app/api/auth.py`, change line 4 from:

```python
from fastapi import APIRouter, Depends, HTTPException, status
```

to:

```python
from fastapi import APIRouter, Depends, HTTPException, status, Form
```

- [ ] **Step 2: Add the `portal` parameter and validation to `login()`**

Replace the existing `login` function (lines 25–52):

```python
@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
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

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
```

with:

```python
@router.post("/login", response_model=Token)
def login(
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

- [ ] **Step 3: Start the backend**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or, if already set up, just start the backend window it opens). Wait until the terminal shows `Uvicorn running on http://0.0.0.0:8000` (or `127.0.0.1:8000`).

- [ ] **Step 4: Verify — admin logging into Admin portal succeeds**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123&portal=admin"
```

Expected: `200`

- [ ] **Step 5: Verify — staff attempting Admin portal is rejected**

Run:

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=staff&password=staff123&portal=admin" -w "\nHTTP %{http_code}\n"
```

Expected output includes `"detail":"This account does not have Admin portal access."` and `HTTP 403`.

- [ ] **Step 6: Verify — staff logging into Counter portal succeeds**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=staff&password=staff123&portal=counter"
```

Expected: `200`

- [ ] **Step 7: Verify — admin can also log into Counter portal**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123&portal=counter"
```

Expected: `200`

- [ ] **Step 8: Verify — omitted portal still works (backward compatible)**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

Expected: `200`

- [ ] **Step 9: Commit**

```bash
git add bsu-registrar-queue/backend/app/api/auth.py
git commit -m "feat(auth): validate requested portal against user role on login"
```

(Skip this step if the project directory is not yet a git repository.)

---

### Task 2: Frontend — standalone `/login` page with portal selector

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js:81-101` (login action)
- Create: `bsu-registrar-queue/frontend/src/views/LoginView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/views/AdminView.vue`

**Interfaces:**
- Consumes: Task 1's `POST /api/auth/login` (now accepts `portal` form field, returns `403` on portal/role mismatch).
- Produces: route `/login` (name `login`) rendering `LoginView.vue`; `useQueueStore().login(username, password, portal)` (new 3rd optional param); `/admin` route now carries `meta: { requiresAuth: true }` enforced by a global `router.beforeEach` guard.

- [ ] **Step 1: Add `portal` parameter to the store's `login` action**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, replace the `login` action (lines 81–101):

```js
    async login(username, password) {
      this.loading = true
      this.error = null
      try {
        const form = new URLSearchParams()
        form.append('username', username)
        form.append('password', password)
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

```js
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

- [ ] **Step 2: Create `LoginView.vue`**

Create `bsu-registrar-queue/frontend/src/views/LoginView.vue`:

```vue
<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center relative overflow-hidden px-4">
    <div class="absolute -top-16 -left-16 w-72 h-72 bg-bsu-primary/10 rounded-full blur-3xl"></div>
    <div class="absolute top-1/3 -right-16 w-80 h-80 bg-bsu-gold/10 rounded-full blur-3xl"></div>

    <div class="relative z-10 w-full max-w-md bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
      <div class="p-8">
        <div class="flex flex-col items-center text-center mb-6">
          <div class="flex items-center space-x-2 mb-4">
            <img :src="BSUlogo" alt="BSU Logo" class="w-16 h-16 object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="w-12 h-12 object-contain" />
          </div>
          <h1 class="text-2xl font-bold text-bsu-primary">BSU Registrar Queue System</h1>
          <p class="mt-1 text-sm text-gray-500">Enter your credentials to continue</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label for="username" class="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              id="username"
              v-model="form.username"
              type="text"
              required
              autocomplete="username"
              class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
              placeholder="Enter your username"
            />
          </div>

          <div>
            <label for="password" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <div class="relative">
              <input
                id="password"
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                required
                autocomplete="current-password"
                class="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                placeholder="Enter your password"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
              >
                <svg v-if="showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                </svg>
                <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
            </div>
          </div>

          <div>
            <label for="portal" class="block text-sm font-medium text-gray-700 mb-1">Select Portal</label>
            <select
              id="portal"
              v-model="form.portal"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
            >
              <option value="" disabled>Choose a portal</option>
              <option value="admin">Admin</option>
              <option value="counter">Counter</option>
            </select>
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-2 px-4 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            <span v-if="!loading">Login</span>
            <span v-else>Logging in...</span>
          </button>
        </form>

        <div v-if="loginError" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-700">{{ loginError }}</p>
        </div>

        <div class="mt-6 flex items-center justify-center space-x-4 text-sm">
          <router-link to="/" class="text-gray-500 hover:underline">Back to Home</router-link>
          <span class="text-gray-300">|</span>
          <router-link to="/display" class="text-bsu-primary hover:underline">View Display Board</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQueueStore } from '@/stores/queue'
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

const router = useRouter()
const queueStore = useQueueStore()

const form = ref({
  username: '',
  password: '',
  portal: '',
})

const showPassword = ref(false)
const loading = ref(false)
const loginError = ref('')

const handleLogin = async () => {
  loading.value = true
  loginError.value = ''
  try {
    await queueStore.login(form.value.username, form.value.password, form.value.portal)
    router.push('/admin')
  } catch (err) {
    loginError.value = err.response?.data?.detail || 'Login failed. Please check your credentials.'
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 3: Add the `/login` route, `requiresAuth` meta, and navigation guard**

Replace the full contents of `bsu-registrar-queue/frontend/src/router/index.js`:

```js
import { createRouter, createWebHistory } from 'vue-router'
import { useQueueStore } from '../stores/queue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue')
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue')
    },
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
    {
      path: '/queues/:id',
      name: 'queue-detail',
      component: () => import('../views/QueueDetailView.vue')
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/display',
      name: 'display-index',
      component: () => import('../views/DisplayIndexView.vue')
    },
    {
      path: '/display/:id',
      name: 'display-board',
      component: () => import('../views/DisplayBoardView.vue')
    }
  ]
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const queueStore = useQueueStore()
    if (!queueStore.isAuthenticated) {
      return { name: 'login' }
    }
  }
})

export default router
```

- [ ] **Step 4: Remove the embedded login form from `AdminView.vue`**

In `bsu-registrar-queue/frontend/src/views/AdminView.vue`, replace lines 19–76 (the login-form block plus the start of the dashboard block):

```html
      <!-- Login Form (if not authenticated) -->
      <div v-if="!queueStore.isAuthenticated" class="max-w-md mx-auto">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 p-6">
            <h2 class="text-2xl font-bold text-gray-900">Staff Login</h2>
            <p class="mt-1 text-gray-600">Access the registrar dashboard</p>
          </div>
          <div class="p-6">
            <form @submit.prevent="handleLogin" class="space-y-4">
              <div>
                <label for="username" class="block text-sm font-medium text-gray-700 mb-1">
                  Username
                </label>
                <input
                  id="username"
                  v-model="loginForm.username"
                  type="text"
                  required
                  autocomplete="username"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                  placeholder="Enter your username"
                />
              </div>

              <div>
                <label for="password" class="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <input
                  id="password"
                  v-model="loginForm.password"
                  type="password"
                  required
                  autocomplete="current-password"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-bsu-primary focus:border-bsu-primary"
                  placeholder="Enter your password"
                />
              </div>

              <button
                type="submit"
                :disabled="loading"
                class="w-full py-2 px-4 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
              >
                <span v-if="!loading">Login</span>
                <span v-else>Logging in...</span>
              </button>
            </form>

            <div v-if="loginError" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p class="text-sm text-red-700">{{ loginError }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Dashboard Content (if authenticated) -->
      <div v-else>
```

with:

```html
      <!-- Dashboard Content -->
      <div>
```

- [ ] **Step 5: Remove now-unused login state and handler from `AdminView.vue`'s script**

Remove the `loginError` ref (originally line 452):

```js
const loginError = ref('')
```

Remove the login form ref block (originally lines 472–477):

```js
// Login form
const loginForm = ref({
  username: '',
  password: '',
})

```

Remove the `handleLogin` function (originally lines 496–510):

```js
// Login handler
const handleLogin = async () => {
  loading.value = true
  loginError.value = ''

  try {
    await queueStore.login(loginForm.value.username, loginForm.value.password)
    await fetchDashboardData()
  } catch (err) {
    loginError.value = err.response?.data?.detail || 'Login failed. Please check your credentials.'
  } finally {
    loading.value = false
  }
}

```

- [ ] **Step 6: Add router-based redirect on logout and on invalid/expired session**

Change the import line (originally line 441):

```js
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
```

to:

```js
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQueueStore } from '@/stores/queue'
```

Change (originally line 448):

```js
const queueStore = useQueueStore()
```

to:

```js
const queueStore = useQueueStore()
const router = useRouter()
```

Change the `logout` function (originally lines 511–517):

```js
const logout = () => {
  queueStore.logout()
  queues.value = []
  selectedQueueId.value = null
  queueDisplay.value = []
  servingTicket.value = null
}
```

to:

```js
const logout = () => {
  queueStore.logout()
  queues.value = []
  selectedQueueId.value = null
  queueDisplay.value = []
  servingTicket.value = null
  router.push('/login')
}
```

Change the `onMounted` catch block (originally lines 685–694):

```js
onMounted(async () => {
  if (queueStore.isAuthenticated) {
    try {
      await queueStore.fetchCurrentUser()
      await fetchDashboardData()
    } catch (err) {
      // Token expired or invalid - force re-login
      queueStore.logout()
    }
  }
```

to:

```js
onMounted(async () => {
  if (queueStore.isAuthenticated) {
    try {
      await queueStore.fetchCurrentUser()
      await fetchDashboardData()
    } catch (err) {
      // Token expired or invalid - force re-login
      queueStore.logout()
      router.push('/login')
    }
  }
```

- [ ] **Step 7: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1`. Wait for both "Backend: http://localhost:8000" and "Frontend: http://localhost:5173" to print.

- [ ] **Step 8: Verify — guard redirects unauthenticated visitors**

In a browser, with no prior session (or after clearing `localStorage`), navigate to `http://localhost:5173/admin`.

Expected: browser lands on `/login`, showing the new card UI (BSU/Meneses logos, title, Username/Password/Select Portal fields, Back to Home / View Display Board links).

- [ ] **Step 9: Verify — Admin logs into Admin portal**

On `/login`, enter `admin` / `admin123`, select portal **Admin**, submit.

Expected: redirected to `/admin`, dashboard loads (stats cards, Queue Management section visible), "Logged in as: ..." shown in the header with a Logout button.

- [ ] **Step 10: Verify — Staff is rejected from Admin portal**

Log out (click Logout, confirm it lands back on `/login`). On `/login`, enter `staff` / `staff123`, select portal **Admin**, submit.

Expected: stays on `/login`, inline red error box reads "This account does not have Admin portal access."

- [ ] **Step 11: Verify — Staff logs into Counter portal**

On `/login`, enter `staff` / `staff123`, select portal **Counter**, submit.

Expected: redirected to `/admin`, dashboard loads.

- [ ] **Step 12: Verify — bad credentials still show inline error**

Log out. On `/login`, enter `staff` / `wrongpassword`, select any portal, submit.

Expected: stays on `/login`, inline red error box reads "Incorrect username or password" (or the existing 401 detail message).

- [ ] **Step 13: Verify — show/hide password toggle and footer links**

On `/login`, type a password, click the eye icon to confirm it toggles between masked/plain text. Click "Back to Home" (lands on `/`) and, separately, "View Display Board" (lands on `/display`).

- [ ] **Step 14: Commit**

```bash
git add bsu-registrar-queue/frontend/src/stores/queue.js \
        bsu-registrar-queue/frontend/src/views/LoginView.vue \
        bsu-registrar-queue/frontend/src/router/index.js \
        bsu-registrar-queue/frontend/src/views/AdminView.vue
git commit -m "feat(frontend): add standalone /login page with portal selector and auth guard"
```

(Skip this step if the project directory is not yet a git repository.)
