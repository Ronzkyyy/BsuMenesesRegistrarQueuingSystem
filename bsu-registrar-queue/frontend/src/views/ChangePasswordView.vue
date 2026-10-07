<template>
  <div class="min-h-screen bg-bsu-surface flex items-center justify-center px-4 py-10">
    <div class="relative z-10 w-full max-w-md bg-white rounded-2xl shadow-soft-lg border border-gray-100 overflow-hidden">
      <div class="p-8">
        <div class="flex flex-col items-center text-center mb-6">
          <div class="flex items-center space-x-2 mb-4">
            <img :src="BSUlogo" alt="BSU Logo" class="h-12 w-auto object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="h-12 w-auto object-contain" />
          </div>
          <h1 class="text-2xl font-bold text-bsu-ink">Set a New Password</h1>
          <p class="mt-1 text-sm text-gray-500">
            An administrator reset the password for
            <span class="font-medium text-bsu-ink">{{ queueStore.currentUser?.username }}</span>.
            Choose your own password to continue.
          </p>
        </div>

        <form @submit.prevent="submit" class="space-y-4">
          <div>
            <label for="temp-password" class="block text-sm font-medium text-gray-700 mb-1.5">Temporary Password</label>
            <input
              id="temp-password"
              v-model="form.current_password"
              type="password"
              required
              autocomplete="current-password"
              class="field"
              placeholder="The password the admin gave you"
            />
          </div>
          <div>
            <label for="new-password" class="block text-sm font-medium text-gray-700 mb-1.5">New Password</label>
            <input
              id="new-password"
              v-model="form.new_password"
              type="password"
              required
              minlength="8"
              maxlength="72"
              autocomplete="new-password"
              class="field"
              placeholder="At least 8 characters"
            />
          </div>
          <div>
            <label for="confirm-password" class="block text-sm font-medium text-gray-700 mb-1.5">Confirm New Password</label>
            <input
              id="confirm-password"
              v-model="form.confirm_password"
              type="password"
              required
              minlength="8"
              maxlength="72"
              autocomplete="new-password"
              class="field"
            />
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="btn btn-primary w-full py-2.5"
          >
            <span v-if="!loading">Save and Continue</span>
            <span v-else>Saving...</span>
          </button>
        </form>

        <div v-if="error" class="mt-4 p-3 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <div class="mt-6 flex justify-center">
          <button type="button" @click="logout" class="text-sm text-gray-500 hover:text-bsu-ink underline">
            Log out instead
          </button>
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

const form = ref({ current_password: '', new_password: '', confirm_password: '' })
const loading = ref(false)
const error = ref('')

const submit = async () => {
  error.value = ''
  if (form.value.new_password !== form.value.confirm_password) {
    error.value = 'New password and confirmation do not match.'
    return
  }
  if (form.value.new_password === form.value.current_password) {
    error.value = 'Choose a password different from the temporary one.'
    return
  }

  loading.value = true
  try {
    await queueStore.changePassword(form.value.current_password, form.value.new_password)
    router.push('/admin')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to change password'
  } finally {
    loading.value = false
  }
}

const logout = async () => {
  await queueStore.logout()
  router.push('/login')
}
</script>
