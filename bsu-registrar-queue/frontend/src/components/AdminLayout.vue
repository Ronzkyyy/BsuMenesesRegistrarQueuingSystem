<template>
  <div class="min-h-screen bg-bsu-surface flex flex-col">
    <AppHeader subtitle="Registrar Staff Dashboard">
      <template #actions>
        <span class="hidden md:block text-sm text-gray-500">
          Logged in as: <span class="font-medium text-bsu-ink">{{ queueStore.currentUser?.full_name || queueStore.currentUser?.username || 'Staff' }}</span>
        </span>
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
