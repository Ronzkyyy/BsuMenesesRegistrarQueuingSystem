<template>
  <div class="min-h-screen bg-bsu-surface flex flex-col">
    <AppHeader subtitle="Registrar Staff Dashboard">
      <template #actions>
        <span class="hidden md:block text-sm text-gray-500">
          Logged in as: <span class="font-medium text-bsu-ink">{{ queueStore.currentUser?.full_name || queueStore.currentUser?.username || 'Staff' }}</span>
        </span>
        <button
          v-if="queueStore.currentUser?.role === 'admin'"
          @click="openChangePasswordModal"
          class="btn btn-sm btn-secondary"
        >
          Change Password
        </button>
        <button
          @click="logout"
          class="btn btn-sm bg-red-50 text-red-600 hover:bg-red-100 focus:ring-red-500"
        >
          Logout
        </button>
      </template>
    </AppHeader>

    <div class="flex-1 flex max-w-7xl mx-auto w-full">
      <aside class="w-60 flex-shrink-0 py-6 px-3 hidden sm:block">
        <nav class="space-y-1.5">
          <router-link
            to="/admin"
            class="block px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
            :class="route.path === '/admin' ? 'bg-bsu-primary text-white shadow-sm' : 'text-gray-600 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark'"
          >
            Dashboard
          </router-link>
          <router-link
            to="/admin/queues"
            class="block px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
            :class="route.path === '/admin/queues' ? 'bg-bsu-primary text-white shadow-sm' : 'text-gray-600 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark'"
          >
            Queue Management
          </router-link>
          <router-link
            to="/admin/counter"
            class="block px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
            :class="route.path === '/admin/counter' ? 'bg-bsu-primary text-white shadow-sm' : 'text-gray-600 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark'"
          >
            Counter
          </router-link>
          <router-link
            to="/admin/students"
            class="block px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
            :class="route.path === '/admin/students' ? 'bg-bsu-primary text-white shadow-sm' : 'text-gray-600 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark'"
          >
            Students
          </router-link>
          <router-link
            v-if="['admin', 'registrar'].includes(queueStore.currentUser?.role)"
            to="/admin/media"
            class="block px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
            :class="route.path === '/admin/media' ? 'bg-bsu-primary text-white shadow-sm' : 'text-gray-600 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark'"
          >
            Media & Announcements
          </router-link>
          <router-link
            v-if="queueStore.currentUser?.role === 'admin'"
            to="/admin/users"
            class="block px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
            :class="route.path === '/admin/users' ? 'bg-bsu-primary text-white shadow-sm' : 'text-gray-600 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark'"
          >
            User Management
          </router-link>
        </nav>
      </aside>

      <main class="flex-1 px-4 sm:px-6 lg:px-8 py-8 min-w-0">
        <router-view />
      </main>
    </div>

    <AppFooter />

    <!-- Change Password Modal -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div v-if="showChangePasswordModal" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50 p-4">
      <Transition
        appear
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
      <div v-if="showChangePasswordModal" class="bg-white rounded-2xl shadow-soft-lg max-w-sm w-full">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">Change Password</h3>
        </div>
        <form @submit.prevent="submitChangePassword">
          <div class="px-6 py-4 space-y-4">
            <div>
              <label for="change-pw-current" class="block text-sm font-medium text-gray-700 mb-1.5">Current Password</label>
              <input
                id="change-pw-current"
                v-model="passwordForm.current_password"
                type="password"
                autocomplete="current-password"
                required
                class="field"
              />
            </div>
            <div>
              <label for="change-pw-new" class="block text-sm font-medium text-gray-700 mb-1.5">New Password</label>
              <input
                id="change-pw-new"
                v-model="passwordForm.new_password"
                type="password"
                autocomplete="new-password"
                minlength="8"
                required
                class="field"
                placeholder="At least 8 characters"
              />
            </div>
            <div>
              <label for="change-pw-confirm" class="block text-sm font-medium text-gray-700 mb-1.5">Confirm New Password</label>
              <input
                id="change-pw-confirm"
                v-model="passwordForm.confirm_password"
                type="password"
                autocomplete="new-password"
                minlength="8"
                required
                class="field"
              />
            </div>

            <div v-if="passwordError" class="p-3 bg-red-50 border border-red-100 rounded-xl">
              <p class="text-sm text-red-700">{{ passwordError }}</p>
            </div>
            <div v-if="passwordSuccess" class="p-3 bg-green-50 border border-green-100 rounded-xl">
              <p class="text-sm text-green-700">Password changed successfully.</p>
            </div>
          </div>

          <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
            <button
              type="button"
              @click="showChangePasswordModal = false"
              class="btn-secondary btn-md"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="passwordLoading"
              class="btn-primary btn-md"
            >
              <span v-if="!passwordLoading">Update Password</span>
              <span v-else>Updating…</span>
            </button>
          </div>
        </form>
      </div>
      </Transition>
    </div>
    </Transition>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueueStore } from '@/stores/queue'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'

const queueStore = useQueueStore()
const router = useRouter()
const route = useRoute()

const logout = () => {
  queueStore.logout()
  router.push('/login')
}

const showChangePasswordModal = ref(false)
const passwordLoading = ref(false)
const passwordError = ref('')
const passwordSuccess = ref(false)
const emptyPasswordForm = () => ({ current_password: '', new_password: '', confirm_password: '' })
const passwordForm = ref(emptyPasswordForm())

const openChangePasswordModal = () => {
  passwordForm.value = emptyPasswordForm()
  passwordError.value = ''
  passwordSuccess.value = false
  showChangePasswordModal.value = true
}

const submitChangePassword = async () => {
  passwordError.value = ''
  passwordSuccess.value = false

  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    passwordError.value = 'New password and confirmation do not match.'
    return
  }
  if (passwordForm.value.new_password.length < 8) {
    passwordError.value = 'New password must be at least 8 characters.'
    return
  }

  passwordLoading.value = true
  try {
    await queueStore.changePassword(passwordForm.value.current_password, passwordForm.value.new_password)
    passwordSuccess.value = true
    passwordForm.value = emptyPasswordForm()
    setTimeout(() => {
      showChangePasswordModal.value = false
      passwordSuccess.value = false
    }, 1200)
  } catch (err) {
    const detail = err.response?.data?.detail
    passwordError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to change password'
  } finally {
    passwordLoading.value = false
  }
}

onMounted(async () => {
  try {
    await queueStore.fetchCurrentUser()
  } catch (err) {
    queueStore.logout()
    router.push('/login')
  }
})
</script>
