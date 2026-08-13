<template>
  <span
    :class="[
      'inline-flex items-center px-3 py-1 rounded-xl text-xs font-semibold uppercase tracking-wide transition-colors duration-150',
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
  green: 'bg-green-50 text-green-700',
  yellow: 'bg-bsu-gold/20 text-bsu-gold-dark',
  red: 'bg-red-50 text-red-600',
  blue: 'bg-bsu-primary/10 text-bsu-primary-dark',
  gray: 'bg-gray-100 text-gray-600',
}[tone.value]))

const solidClasses = computed(() => ({
  green: 'bg-green-500 text-white',
  yellow: 'bg-bsu-gold text-bsu-ink',
  red: 'bg-red-500 text-white',
  blue: 'bg-bsu-primary text-white',
  gray: 'bg-gray-500 text-white',
}[tone.value]))
</script>
