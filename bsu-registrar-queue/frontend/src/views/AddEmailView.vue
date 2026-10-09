<template>
  <div class="min-h-screen bg-bsu-surface flex items-center justify-center px-4 py-10">
    <div class="relative z-10 w-full max-w-md bg-white rounded-2xl shadow-soft-lg border border-gray-100 overflow-hidden">
      <div class="p-8">
        <div class="flex flex-col items-center text-center mb-6">
          <div class="flex items-center space-x-2 mb-4">
            <img :src="BSUlogo" alt="BSU Logo" class="h-12 w-auto object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="h-12 w-auto object-contain" />
          </div>
          <h1 class="text-2xl font-bold text-bsu-ink">Add Your Email</h1>
          <p class="mt-1 text-sm text-gray-500">
            Staff accounts now need an email address, so
            <span class="font-medium text-bsu-ink">{{ queueStore.currentUser?.username }}</span>
            can reset its own password if it's ever forgotten.
          </p>
        </div>

        <form @submit.prevent="submit" class="space-y-4">
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
            <p class="mt-1.5 text-xs text-gray-500">
              We'll send a confirmation link. You can keep working meanwhile - the link only needs
              to be clicked before email password resets are possible.
            </p>
          </div>

          <button type="submit" :disabled="loading" class="btn btn-primary w-full py-2.5">
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

const email = ref('')
const loading = ref(false)
const error = ref('')

const submit = async () => {
  error.value = ''
  loading.value = true
  try {
    await queueStore.setMyEmail(email.value.trim())
    router.push('/admin')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to save email'
  } finally {
    loading.value = false
  }
}

const logout = async () => {
  await queueStore.logout()
  router.push('/login')
}
</script>
