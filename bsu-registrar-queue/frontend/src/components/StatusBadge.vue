<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium uppercase transition-colors duration-150',
      solid ? solidClasses : softClasses,
    ]"
  >
    {{ status }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },
  solid: { type: Boolean, default: false },
})

const tone = computed(() => {
  const s = (props.status || '').toLowerCase()
  if (['active', 'completed'].includes(s)) return 'green'
  if (['paused', 'priority', 'serving'].includes(s)) return 'yellow'
  if (['urgent', 'no_show', 'cancelled'].includes(s)) return 'red'
  if (['waiting'].includes(s)) return 'blue'
  return 'gray'
})

const softClasses = computed(() => ({
  green: 'bg-green-100 text-green-800',
  yellow: 'bg-yellow-100 text-yellow-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-blue-100 text-blue-800',
  gray: 'bg-gray-100 text-gray-800',
}[tone.value]))

const solidClasses = computed(() => ({
  green: 'bg-green-500 text-white',
  yellow: 'bg-yellow-500 text-white',
  red: 'bg-red-500 text-white',
  blue: 'bg-blue-500 text-white',
  gray: 'bg-gray-500 text-white',
}[tone.value]))
</script>
