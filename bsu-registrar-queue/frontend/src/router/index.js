import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue')
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
      component: () => import('../views/AdminView.vue')
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

export default router