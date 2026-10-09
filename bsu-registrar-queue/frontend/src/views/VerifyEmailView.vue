<template>
  <div class="min-h-screen bg-bsu-surface flex items-center justify-center px-4 py-10">
    <div class="relative z-10 w-full max-w-md bg-white rounded-2xl shadow-soft-lg border border-gray-100 overflow-hidden">
      <div class="p-8">
        <div class="flex flex-col items-center text-center mb-6">
          <div class="flex items-center space-x-2 mb-4">
            <img :src="BSUlogo" alt="BSU Logo" class="h-12 w-auto object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="h-12 w-auto object-contain" />
          </div>
          <h1 class="text-2xl font-bold text-bsu-ink">Confirm Email</h1>
        </div>

        <p v-if="state === 'working'" class="text-sm text-gray-500 text-center">Confirming your email...</p>

        <div v-else-if="state === 'done'" class="p-4 bg-green-50 border border-green-100 rounded-xl">
          <p class="text-sm text-green-800">{{ message }}</p>
        </div>

        <div v-else class="p-4 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ message }}</p>
          <p class="mt-2 text-xs text-red-600">
            Log in and ask for a new confirmation link, or ask an administrator to resend it.
          </p>
        </div>

        <div class="mt-6 flex justify-center">
          <router-link to="/login" class="text-sm text-gray-500 hover:text-bsu-ink underline">
            Go to login
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { takeTokenFromUrl } from '@/services/emailLinkToken'
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

const queueStore = useQueueStore()

const token = takeTokenFromUrl()
const state = ref('working')
const message = ref('')

onMounted(async () => {
  if (!token) {
    state.value = 'failed'
    message.value = 'This confirmation link is incomplete. Open the link from your email again.'
    return
  }
  try {
    message.value = await queueStore.verifyEmail(token)
    state.value = 'done'
    if (queueStore.currentUser) await queueStore.fetchCurrentUser().catch(() => {})
  } catch (err) {
    state.value = 'failed'
    message.value = err.response?.data?.detail || 'Could not confirm this email.'
  }
})
</script>
