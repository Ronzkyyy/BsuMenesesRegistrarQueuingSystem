<template>
  <div>
    <div class="mb-8 flex items-center justify-between">
      <div>
        <h2 class="text-3xl font-bold text-bsu-ink">User Management</h2>
        <p class="mt-2 text-gray-500">Manage registrar staff accounts</p>
      </div>
      <button
        @click="openCreateModal"
        class="btn-primary btn-md"
      >
        <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Create User
      </button>
    </div>

    <div v-if="listError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ listError }}</p>
    </div>

    <div v-if="notice" class="bg-green-50 border border-green-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-green-800">{{ notice }}</p>
    </div>

    <div class="panel overflow-hidden">
      <table class="min-w-full divide-y divide-gray-100">
        <thead class="bg-bsu-surface">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Username</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Full Name</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Email</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
            <th class="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="user in queueStore.users" :key="user.id" class="table-row-hover">
            <td class="px-6 py-4 text-sm font-medium text-bsu-ink">{{ user.username }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ user.full_name }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">
              <div v-if="user.email" class="flex flex-col items-start gap-1">
                <span class="break-all">{{ user.email }}</span>
                <span
                  :class="[
                    'inline-flex items-center px-2 py-0.5 rounded-lg text-[11px] font-semibold uppercase tracking-wide',
                    user.email_verified_at ? 'bg-green-50 text-green-700' : 'bg-bsu-gold/20 text-bsu-gold-dark',
                  ]"
                >
                  {{ user.email_verified_at ? 'Confirmed' : 'Unconfirmed' }}
                </span>
              </div>
              <span
                v-else
                class="inline-flex items-center px-2 py-0.5 rounded-lg text-[11px] font-semibold uppercase tracking-wide bg-red-50 text-red-600"
              >
                Missing
              </span>
            </td>
            <td class="px-6 py-4 text-sm text-gray-600 capitalize">{{ user.role }}</td>
            <td class="px-6 py-4">
              <StatusBadge :status="user.is_active ? 'active' : 'inactive'" />
            </td>
            <td class="px-6 py-4 text-right space-x-2 whitespace-nowrap">
              <button
                @click="openEmailModal(user)"
                :disabled="actionLoading"
                class="btn-secondary btn-sm"
              >
                {{ user.email ? 'Edit Email' : 'Add Email' }}
              </button>
              <button
                v-if="user.email && !user.email_verified_at"
                @click="resendVerification(user)"
                :disabled="actionLoading"
                class="btn-secondary btn-sm"
              >
                Resend Link
              </button>
              <button
                v-if="user.id !== queueStore.currentUser?.id"
                @click="confirmReset(user)"
                :disabled="actionLoading"
                class="btn-secondary btn-sm"
              >
                Reset Password
              </button>
              <button
                v-if="user.is_active"
                @click="deactivate(user.id)"
                :disabled="actionLoading"
                class="btn-danger btn-sm"
              >
                Deactivate
              </button>
              <button
                v-else
                @click="activate(user.id)"
                :disabled="actionLoading"
                class="btn-success btn-sm"
              >
                Activate
              </button>
            </td>
          </tr>

          <tr v-if="queueStore.users.length === 0">
            <td colspan="6" class="px-6 py-8 text-center text-gray-500">No staff accounts found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div v-if="showCreateModal" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50">
      <Transition
        appear
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">Create User</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
            <input
              v-model="newUserForm.username"
              type="text"
              class="field"
              placeholder="e.g., jsantos"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
            <input
              v-model="newUserForm.full_name"
              type="text"
              class="field"
              placeholder="e.g., Juan Santos"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
            <input
              v-model="newUserForm.email"
              type="email"
              maxlength="254"
              class="field"
              placeholder="e.g., jsantos@example.com"
            />
            <p class="mt-1 text-xs text-gray-500">They'll get a link to confirm it. Password reset emails go here.</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Role</label>
            <select
              v-model="newUserForm.role"
              class="field"
            >
              <option value="admin">Admin</option>
              <option value="registrar">Registrar</option>
              <option value="staff">Staff</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
            <input
              v-model="newUserForm.password"
              type="password"
              class="field"
              placeholder="At least 8 characters"
            />
          </div>

          <div v-if="createError" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ createError }}</p>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
          <button
            @click="showCreateModal = false"
            class="btn-secondary btn-md"
          >
            Cancel
          </button>
          <button
            @click="createUser"
            :disabled="actionLoading"
            class="btn-primary btn-md"
          >
            Create
          </button>
        </div>
      </div>
      </Transition>
    </div>
    </Transition>

    <!-- Add / edit an account's email -->
    <div v-if="emailModal.open" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-md w-full">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">
            {{ emailModal.user?.email ? 'Edit Email' : 'Add Email' }} - {{ emailModal.user?.username }}
          </h3>
        </div>
        <form @submit.prevent="saveEmail" class="px-6 py-4 space-y-4">
          <div>
            <label for="edit-email" class="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
            <input
              id="edit-email"
              v-model="emailModal.email"
              type="email"
              required
              maxlength="254"
              class="field"
            />
            <p class="mt-1 text-xs text-gray-500">
              A new address must be confirmed from the link we send to it before password reset emails go there.
            </p>
          </div>
          <div v-if="emailModal.error" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ emailModal.error }}</p>
          </div>
          <div class="flex justify-end space-x-3 pt-2">
            <button type="button" @click="emailModal.open = false" class="btn-secondary btn-md">Cancel</button>
            <button type="submit" :disabled="actionLoading" class="btn-primary btn-md">Save</button>
          </div>
        </form>
      </div>
    </div>

    <ConfirmDialog
      v-model="resetConfirm.open"
      title="Reset password?"
      :message="`${resetConfirm.user?.username} will get a temporary password and must choose a new one at their next login. Their current password stops working immediately.`"
      confirm-label="Reset Password"
      variant="danger"
      :loading="actionLoading"
      @confirm="resetPassword"
    />

    <!-- Temporary password - shown once, never stored -->
    <div v-if="resetResult" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-[70] p-4">
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-sm w-full">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">Temporary Password</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <p class="text-sm text-gray-600">
            Give this to <span class="font-medium text-bsu-ink">{{ resetResult.username }}</span> in person.
            It is shown only once - they will be asked to replace it when they log in.
          </p>
          <div class="flex items-center gap-2">
            <code class="flex-1 px-3 py-2 bg-bsu-surface rounded-xl text-lg font-mono tracking-wider text-bsu-ink text-center select-all">
              {{ resetResult.temporary_password }}
            </code>
            <button @click="copyTemp" class="btn-secondary btn-sm">{{ copied ? 'Copied' : 'Copy' }}</button>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end">
          <button @click="closeResetResult" class="btn-primary btn-md">Done</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const queueStore = useQueueStore()

const listError = ref('')
const notice = ref('')
const createError = ref('')
const actionLoading = ref(false)
const showCreateModal = ref(false)

const newUserForm = ref({
  username: '',
  full_name: '',
  role: 'staff',
  password: '',
  email: '',
})

const openCreateModal = () => {
  createError.value = ''
  newUserForm.value = { username: '', full_name: '', role: 'staff', password: '', email: '' }
  showCreateModal.value = true
}

const createUser = async () => {
  if (!newUserForm.value.username || !newUserForm.value.full_name || !newUserForm.value.password) return
  if (!newUserForm.value.email.trim()) {
    createError.value = 'Email is required.'
    return
  }

  if (newUserForm.value.username.length < 3) {
    createError.value = 'Username must be at least 3 characters.'
    return
  }
  if (newUserForm.value.password.length < 8) {
    createError.value = 'Password must be at least 8 characters.'
    return
  }

  actionLoading.value = true
  createError.value = ''
  try {
    const created = await queueStore.createUser({ ...newUserForm.value, email: newUserForm.value.email.trim() })
    showCreateModal.value = false
    notice.value = `Account created. A confirmation link was sent to ${created.email}.`
  } catch (err) {
    const detail = err.response?.data?.detail
    createError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to create user'
  } finally {
    actionLoading.value = false
  }
}

const emailModal = ref({ open: false, user: null, email: '', error: '' })

const openEmailModal = (user) => {
  notice.value = ''
  emailModal.value = { open: true, user, email: user.email || '', error: '' }
}

const saveEmail = async () => {
  const { user, email } = emailModal.value
  actionLoading.value = true
  emailModal.value.error = ''
  try {
    const updated = await queueStore.setUserEmail(user.id, email.trim())
    emailModal.value.open = false
    notice.value = updated.email === user.email
      ? 'Email unchanged.'
      : `Email saved. A confirmation link was sent to ${updated.email}.`
  } catch (err) {
    emailModal.value.error = err.response?.data?.detail || 'Failed to save email'
  } finally {
    actionLoading.value = false
  }
}

const resendVerification = async (user) => {
  actionLoading.value = true
  listError.value = ''
  notice.value = ''
  try {
    notice.value = await queueStore.resendUserVerification(user.id)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to resend the confirmation link'
  } finally {
    actionLoading.value = false
  }
}

const resetConfirm = ref({ open: false, user: null })
const resetResult = ref(null)
const copied = ref(false)

const confirmReset = (user) => {
  resetConfirm.value = { open: true, user }
}

const resetPassword = async () => {
  actionLoading.value = true
  listError.value = ''
  try {
    resetResult.value = await queueStore.resetUserPassword(resetConfirm.value.user.id)
    copied.value = false
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to reset password'
  } finally {
    actionLoading.value = false
    resetConfirm.value = { open: false, user: null }
  }
}

const copyTemp = async () => {
  try {
    await navigator.clipboard.writeText(resetResult.value.temporary_password)
    copied.value = true
  } catch {
    // Clipboard blocked (e.g. plain http) - the code is select-all, copy by hand.
  }
}

const closeResetResult = () => {
  resetResult.value = null
  copied.value = false
}

const activate = async (userId) => {
  actionLoading.value = true
  listError.value = ''
  try {
    await queueStore.activateUser(userId)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to activate user'
  } finally {
    actionLoading.value = false
  }
}

const deactivate = async (userId) => {
  actionLoading.value = true
  listError.value = ''
  try {
    await queueStore.deactivateUser(userId)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to deactivate user'
  } finally {
    actionLoading.value = false
  }
}

onMounted(async () => {
  try {
    await queueStore.fetchUsers()
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to load users'
  }
})
</script>
