<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-gray-900">Dashboard</h2>
      <p class="mt-2 text-gray-600">Overview of queues, tickets, and staff</p>
    </div>

    <div v-if="summaryError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ summaryError }}</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Users</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.users_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Queues</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.queues_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Active Queues</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.active_queues_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Waiting</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.waiting_count ?? 0 }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Serving</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.serving_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Completed Today</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.completed_today_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">No-Shows</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.no_shows_today_count ?? 0 }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Tickets Today by Queue</h3>
        <div v-if="hasQueueData" class="h-64">
          <Bar :data="barData" :options="barOptions" />
        </div>
        <p v-else class="text-center text-gray-500 py-8">No tickets today</p>
      </div>

      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Today's Tickets by Status</h3>
        <div v-if="hasStatusData" class="h-64">
          <Doughnut :data="doughnutData" :options="doughnutOptions" />
        </div>
        <p v-else class="text-center text-gray-500 py-8">No tickets today</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Bar, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  ArcElement,
  CategoryScale,
  LinearScale,
} from 'chart.js'
import { useQueueStore } from '@/stores/queue'

ChartJS.register(Title, Tooltip, Legend, BarElement, ArcElement, CategoryScale, LinearScale)

const queueStore = useQueueStore()
const summaryError = ref('')

const summary = computed(() => queueStore.dashboardSummary)

const hasQueueData = computed(() => (summary.value?.tickets_today_by_queue?.length ?? 0) > 0)
const hasStatusData = computed(() => {
  const byStatus = summary.value?.tickets_today_by_status
  return !!byStatus && Object.values(byStatus).some((count) => count > 0)
})

const barData = computed(() => ({
  labels: (summary.value?.tickets_today_by_queue ?? []).map((q) => q.queue_name),
  datasets: [
    {
      label: 'Tickets Today',
      data: (summary.value?.tickets_today_by_queue ?? []).map((q) => q.count),
      backgroundColor: '#be185d',
      borderRadius: 4,
      maxBarThickness: 48,
    },
  ],
}))

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#e5e7eb' } },
    x: { grid: { display: false } },
  },
}

const STATUS_LABELS = {
  waiting: 'Waiting',
  serving: 'Serving',
  completed: 'Completed',
  cancelled: 'Cancelled',
  no_show: 'No-Show',
}

const STATUS_COLORS = {
  waiting: '#2a78d6',
  serving: '#eda100',
  completed: '#008300',
  cancelled: '#4a3aa7',
  no_show: '#e34948',
}

const doughnutData = computed(() => {
  const byStatus = summary.value?.tickets_today_by_status ?? {}
  const keys = Object.keys(STATUS_LABELS).filter((key) => key in byStatus)
  return {
    labels: keys.map((key) => STATUS_LABELS[key]),
    datasets: [
      {
        data: keys.map((key) => byStatus[key]),
        backgroundColor: keys.map((key) => STATUS_COLORS[key]),
        borderWidth: 0,
      },
    ],
  }
})

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '60%',
  plugins: { legend: { position: 'bottom' } },
}

onMounted(async () => {
  try {
    await queueStore.fetchDashboardSummary()
  } catch (err) {
    summaryError.value = err.response?.data?.detail || 'Failed to load dashboard summary'
  }
})
</script>
