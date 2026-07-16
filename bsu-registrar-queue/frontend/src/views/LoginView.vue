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
