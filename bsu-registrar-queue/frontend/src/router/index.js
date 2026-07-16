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
      path: '/queues/:id',
      name: 'queue-detail',
      component: () => import('../views/QueueDetailView.vue')
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/display',
      name: 'display-index',
      component: () => import('../views/DisplayIndexView.vue')
    },
    {
      path: '/display/:id',
      name: 'display-board',
      component: () => import('../views/DisplayBoardView.vue')
    }
  ]
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const queueStore = useQueueStore()
    if (!queueStore.isAuthenticated) {
      return { name: 'login' }
    }
  }
})

export default router