<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-bsu-ink">Dashboard</h2>
      <p class="mt-2 text-gray-500">Overview of queues, tickets, and staff</p>
    </div>

    <div v-if="summaryError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ summaryError }}</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
      <div class="panel border-t-4 border-t-bsu-primary/60 p-6">
        <p class="text-sm text-gray-500">Users</p>
        <p class="text-2xl font-bold text-bsu-ink">{{ summary?.users_count ?? 0 }}</p>
      </div>
      <div class="panel border-t-4 border-t-bsu-peach/70 p-6">
        <p class="text-sm text-gray-500">Queues</p>
        <p class="text-2xl font-bold text-bsu-ink">{{ summary?.queues_count ?? 0 }}</p>
      </div>
      <div class="panel border-t-4 border-t-bsu-gold p-6">
        <p class="text-sm text-gray-500">Active Queues</p>
        <p class="text-2xl font-bold text-bsu-ink">{{ summary?.active_queues_count ?? 0 }}</p>
      </div>
      <div
        class="panel border-t-4 p-6"
        :class="(summary?.waiting_count ?? 0) > 0 ? 'border-t-amber-400' : 'border-t-bsu-primary/60'"
      >
        <p class="text-sm text-gray-500">Waiting</p>
        <p class="text-2xl font-bold text-bsu-ink">{{ summary?.waiting_count ?? 0 }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div class="panel border-t-4 border-t-bsu-primary/60 p-6">
        <p class="text-sm text-gray-500">Serving</p>
        <p class="text-2xl font-bold text-bsu-ink">{{ summary?.serving_count ?? 0 }}</p>
      </div>
      <div class="panel border-t-4 border-t-bsu-peach/70 p-6">
        <p class="text-sm text-gray-500">Completed Today</p>
        <p class="text-2xl font-bold text-bsu-ink">{{ summary?.completed_today_count ?? 0 }}</p>
      </div>
      <div
        class="panel border-t-4 p-6"
        :class="(summary?.no_shows_today_count ?? 0) > 0 ? 'border-t-amber-400' : 'border-t-bsu-primary/60'"
      >
        <p class="text-sm text-gray-500">No-Shows</p>
        <p class="text-2xl font-bold text-bsu-ink">{{ summary?.no_shows_today_count ?? 0 }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="panel overflow-hidden">
        <div class="panel-header">
          <h3 class="text-lg font-semibold text-bsu-ink">Tickets Today by Service</h3>
        </div>
        <div class="p-6">
          <div v-if="hasServiceData" class="h-64">
            <Bar :data="barData" :options="barOptions" />
          </div>
          <p v-else class="text-center text-gray-500 py-8">No tickets today</p>
        </div>
      </div>

      <div class="panel overflow-hidden">
        <div class="panel-header">
          <h3 class="text-lg font-semibold text-bsu-ink">Today's Tickets by Status</h3>
        </div>
        <div class="p-6">
          <div v-if="hasStatusData" class="h-64">
            <Doughnut :data="doughnutData" :options="doughnutOptions" />
          </div>
          <p v-else class="text-center text-gray-500 py-8">No tickets today</p>
        </div>
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

const hasServiceData = computed(() => (summary.value?.tickets_today_by_service?.length ?? 0) > 0)
const hasStatusData = computed(() => {
  const byStatus = summary.value?.tickets_today_by_status
  return !!byStatus && Object.values(byStatus).some((count) => count > 0)
})

const barData = computed(() => ({
  labels: (summary.value?.tickets_today_by_service ?? []).map((s) => s.service_name),
  datasets: [
    {
      label: 'Tickets Today',
      data: (summary.value?.tickets_today_by_service ?? []).map((s) => s.count),
      backgroundColor: '#E85D8E',
      borderRadius: 8,
      maxBarThickness: 48,
    },
  ],
}))

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#F1F1F1' } },
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
  waiting: '#E85D8E',
  serving: '#F8C95A',
  completed: '#22c55e',
  cancelled: '#9CA3AF',
  no_show: '#ef4444',
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
