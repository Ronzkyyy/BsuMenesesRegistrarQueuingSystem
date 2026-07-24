import { createRouter, createWebHistory } from 'vue-router'
import { useQueueStore } from '../stores/queue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue')
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue')
    },
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
    {
      path: '/admin',
      component: () => import('../components/AdminLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'admin-dashboard',
          component: () => import('../views/DashboardView.vue')
        },
        {
          path: 'queues',
          name: 'admin-queues',
          component: () => import('../views/QueueManagementView.vue')
        },
        {
          path: 'counter',
          name: 'admin-counter',
          component: () => import('../views/CounterView.vue')
        },
        {
          path: 'media',
          name: 'admin-media',
          component: () => import('../views/MediaAnnouncementsView.vue'),
          meta: { requiresRegistrarOrAdmin: true }
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('../views/UserManagementView.vue'),
          meta: { requiresAdmin: true }
        }
      ]
    },
    {
      path: '/display',
      name: 'display-index',
      component: () => import('../views/DisplayIndexView.vue')
    },
    {
      path: '/display/overview',
      name: 'display-overview',
      component: () => import('../views/DisplayOverviewView.vue')
    },
    {
      path: '/display/:id',
      name: 'display-board',
      component: () => import('../views/DisplayBoardView.vue')
    }
  ]
})

router.beforeEach(async (to) => {
  const queueStore = useQueueStore()

  if (to.meta.requiresAuth && !queueStore.isAuthenticated) {
    return { name: 'login' }
  }

  if (to.meta.requiresAdmin) {
    if (!queueStore.currentUser) {
      try {
        await queueStore.fetchCurrentUser()
      } catch (err) {
        return { name: 'login' }
      }
    }
    if (queueStore.currentUser?.role !== 'admin') {
      return { name: 'admin-dashboard' }
    }
  }

  if (to.meta.requiresRegistrarOrAdmin) {
    if (!queueStore.currentUser) {
      try {
        await queueStore.fetchCurrentUser()
      } catch (err) {
        return { name: 'login' }
      }
    }
    if (!['admin', 'registrar'].includes(queueStore.currentUser?.role)) {
      return { name: 'admin-dashboard' }
    }
  }
})

export default router
