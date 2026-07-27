<template>
  <header
    :class="[
      'text-white shadow-lg',
      gradient ? 'bg-gradient-to-r from-bsu-primary to-bsu-gold' : 'bg-bsu-primary',
    ]"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
      <div class="flex items-center justify-between">
        <router-link to="/" class="flex items-center space-x-3">
          <div class="flex items-center space-x-2 flex-shrink-0">
            <img :src="BSUlogo" alt="BSU Logo" class="w-24 h-24 object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="w-16 h-16 object-contain" />
          </div>
          <div>
            <h1 class="text-2xl font-bold leading-tight">BSU Meneses Campus</h1>
            <p class="text-sm text-pink-100">{{ subtitle }}</p>
          </div>
        </router-link>
        <div class="flex items-center space-x-3">
          <slot name="actions" />
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import BSUlogo from '@/assets/BSUlogo.png'
import MENESESlogo from '@/assets/MENESESlogo.png'

defineProps({
  subtitle: {
    type: String,
    default: 'Registrar Queue Management System',
  },
  gradient: {
    type: Boolean,
    default: false,
  },
})
</script>
