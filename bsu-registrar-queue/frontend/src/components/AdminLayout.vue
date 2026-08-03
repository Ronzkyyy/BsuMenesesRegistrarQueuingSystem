<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <AppHeader subtitle="Registrar Staff Dashboard">
      <template #actions>
        <span class="hidden md:block text-sm text-pink-100">
          Logged in as: {{ queueStore.currentUser?.full_name || queueStore.currentUser?.username || 'Staff' }}
        </span>
        <button
          @click="logout"
          class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
        >
          Logout
        </button>
      </template>
    </AppHeader>

    <div class="flex-1 flex max-w-7xl mx-auto w-full">
      <aside class="w-56 flex-shrink-0 border-r border-gray-200 bg-white py-6 px-3 hidden sm:block">
        <nav class="space-y-1">
          <router-link
            to="/admin"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Dashboard
          </router-link>
          <router-link
            to="/admin/queues"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/queues' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Queue Management
          </router-link>
          <router-link
            to="/admin/counter"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/counter' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Counter
          </router-link>
          <router-link
            to="/admin/students"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/students' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Students
          </router-link>
          <router-link
            v-if="['admin', 'registrar'].includes(queueStore.currentUser?.role)"
            to="/admin/media"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/media' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Media & Announcements
          </router-link>
          <router-link
            v-if="queueStore.currentUser?.role === 'admin'"
            to="/admin/users"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/users' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
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
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
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

onMounted(async () => {
  try {
    await queueStore.fetchCurrentUser()
  } catch (err) {
    queueStore.logout()
    router.push('/login')
  }
})
</script>
