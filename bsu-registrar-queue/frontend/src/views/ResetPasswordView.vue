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
          <p class="mt-1 text-sm text-gray-500">Choose a new password for your staff account.</p>
        </div>

        <div v-if="done" class="p-4 bg-green-50 border border-green-100 rounded-xl">
          <p class="text-sm text-green-800">{{ done }}</p>
        </div>

        <div v-else-if="!token" class="p-4 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">
            This reset link is incomplete. Open the link from your email again, or request a new one.
          </p>
        </div>

        <form v-else @submit.prevent="submit" class="space-y-4">
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

          <button type="submit" :disabled="loading" class="btn btn-primary w-full py-2.5">
            <span v-if="!loading">Save New Password</span>
            <span v-else>Saving...</span>
          </button>
        </form>

        <div v-if="error" class="mt-4 p-3 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <div class="mt-6 flex justify-center gap-4">
          <router-link to="/login" class="text-sm text-gray-500 hover:text-bsu-ink underline">
            {{ done ? 'Go to login' : 'Back to login' }}
          </router-link>
          <router-link v-if="!done" to="/forgot-password" class="text-sm text-gray-500 hover:text-bsu-ink underline">
            Request a new link
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { takeTokenFromUrl } from '@/services/emailLinkToken'
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

const queueStore = useQueueStore()

const token = takeTokenFromUrl()
const form = ref({ new_password: '', confirm_password: '' })
const loading = ref(false)
const error = ref('')
const done = ref('')

const submit = async () => {
  error.value = ''
  if (form.value.new_password !== form.value.confirm_password) {
    error.value = 'New password and confirmation do not match.'
    return
  }
  loading.value = true
  try {
    done.value = await queueStore.resetPasswordWithToken(token, form.value.new_password)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to reset password'
  } finally {
    loading.value = false
  }
}
</script>
