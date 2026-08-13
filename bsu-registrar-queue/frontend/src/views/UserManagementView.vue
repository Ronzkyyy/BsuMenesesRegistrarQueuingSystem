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

    <div class="panel overflow-hidden">
      <table class="min-w-full divide-y divide-gray-100">
        <thead class="bg-bsu-surface">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Username</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Full Name</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
            <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
            <th class="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="user in queueStore.users" :key="user.id" class="table-row-hover">
            <td class="px-6 py-4 text-sm font-medium text-bsu-ink">{{ user.username }}</td>
            <td class="px-6 py-4 text-sm text-gray-600">{{ user.full_name }}</td>
            <td class="px-6 py-4 text-sm text-gray-600 capitalize">{{ user.role }}</td>
            <td class="px-6 py-4">
              <StatusBadge :status="user.is_active ? 'active' : 'inactive'" />
            </td>
            <td class="px-6 py-4 text-right">
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
            <td colspan="5" class="px-6 py-8 text-center text-gray-500">No staff accounts found.</td>
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'

const queueStore = useQueueStore()

const listError = ref('')
const createError = ref('')
const actionLoading = ref(false)
const showCreateModal = ref(false)

const newUserForm = ref({
  username: '',
  full_name: '',
  role: 'staff',
  password: '',
})

const openCreateModal = () => {
  createError.value = ''
  newUserForm.value = { username: '', full_name: '', role: 'staff', password: '' }
  showCreateModal.value = true
}

const createUser = async () => {
  if (!newUserForm.value.username || !newUserForm.value.full_name || !newUserForm.value.password) return

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
    await queueStore.createUser(newUserForm.value)
    showCreateModal.value = false
  } catch (err) {
    const detail = err.response?.data?.detail
    createError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to create user'
  } finally {
    actionLoading.value = false
  }
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
