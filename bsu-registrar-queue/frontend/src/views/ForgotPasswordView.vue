<template>
  <div class="min-h-screen bg-bsu-surface flex items-center justify-center px-4 py-10">
    <div class="relative z-10 w-full max-w-md bg-white rounded-2xl shadow-soft-lg border border-gray-100 overflow-hidden">
      <div class="p-8">
        <div class="flex flex-col items-center text-center mb-6">
          <div class="flex items-center space-x-2 mb-4">
            <img :src="BSUlogo" alt="BSU Logo" class="h-12 w-auto object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="h-12 w-auto object-contain" />
          </div>
          <h1 class="text-2xl font-bold text-bsu-ink">Forgot Password</h1>
          <p class="mt-1 text-sm text-gray-500">
            Enter the email on your staff account and we'll send you a link to set a new password.
          </p>
        </div>

        <div v-if="sentMessage" class="p-4 bg-green-50 border border-green-100 rounded-xl">
          <p class="text-sm text-green-800">{{ sentMessage }}</p>
          <p class="mt-2 text-xs text-green-700">
            Check your spam folder too. No email? Your email may not be confirmed yet - ask an
            administrator to reset your password instead.
          </p>
        </div>

        <form v-else @submit.prevent="submit" class="space-y-4">
          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
            <input
              id="email"
              v-model="email"
              type="email"
              required
              maxlength="254"
              autocomplete="email"
              class="field"
              placeholder="you@example.com"
            />
          </div>

          <button type="submit" :disabled="loading" class="btn btn-primary w-full py-2.5">
            <span v-if="!loading">Send Reset Link</span>
            <span v-else>Sending...</span>
          </button>
        </form>

        <div v-if="error" class="mt-4 p-3 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <div class="mt-6 flex justify-center">
          <router-link to="/login" class="text-sm text-gray-500 hover:text-bsu-ink underline">
            Back to login
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useQueueStore } from '@/stores/queue'
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

const queueStore = useQueueStore()

const email = ref('')
const loading = ref(false)
const error = ref('')
const sentMessage = ref('')

const submit = async () => {
  error.value = ''
  loading.value = true
  try {
    sentMessage.value = await queueStore.requestPasswordReset(email.value.trim())
  } catch (err) {
    error.value = err.response?.status === 429
      ? 'Too many requests. Please wait a minute and try again.'
      : err.response?.data?.detail || 'Could not send the reset link. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>
