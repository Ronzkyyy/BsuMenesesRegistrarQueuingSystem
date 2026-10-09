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
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('../views/ForgotPasswordView.vue')
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('../views/ResetPasswordView.vue')
    },
    {
      path: '/verify-email',
      name: 'verify-email',
      component: () => import('../views/VerifyEmailView.vue')
    },
    {
      path: '/add-email',
      name: 'add-email',
      component: () => import('../views/AddEmailView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/change-password',
      name: 'change-password',
      component: () => import('../views/ChangePasswordView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
    {
      path: '/appointments',
      name: 'appointments',
      component: () => import('../views/AppointmentsView.vue')
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
          path: 'checkin',
          name: 'admin-checkin',
          component: () => import('../views/CheckInView.vue')
        },
        {
          path: 'appointments',
          name: 'admin-appointments',
          component: () => import('../views/AppointmentManagementView.vue')
        },
        {
          path: 'students',
          name: 'admin-students',
          component: () => import('../views/StudentManagementView.vue')
        },
        {
          path: 'reports',
          name: 'admin-reports',
          component: () => import('../views/TransactionHistoryView.vue'),
          meta: { requiresAdmin: true }
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
    try {
      await queueStore.fetchCurrentUser()
    } catch (err) {
      return { name: 'login' }
    }
  }

  // After an admin reset, nothing else is usable (the backend refuses it
  // too) until the user replaces the temporary password.
  // Then, an account from before emails existed must add one (the backend
  // refuses it too) - otherwise it could never reset its own password.
  if (to.meta.requiresAuth) {
    const mustChange = !!queueStore.currentUser?.must_change_password
    if (mustChange && to.name !== 'change-password') return { name: 'change-password' }
    if (!mustChange && to.name === 'change-password') return { name: 'admin-dashboard' }

    const needsEmail = !mustChange && !queueStore.currentUser?.email
    if (needsEmail && to.name !== 'add-email') return { name: 'add-email' }
    if (!needsEmail && to.name === 'add-email') return { name: 'admin-dashboard' }
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
