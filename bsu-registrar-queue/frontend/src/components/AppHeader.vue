<template>
  <!-- Full-width oblong banner header (landing page) -->
  <header v-if="floating" class="sticky top-0 z-50 w-full">
    <div
      class="relative w-full bg-gradient-to-r from-pink-600 via-orange-500 to-amber-400 shadow-lg shadow-pink-500/20"
      style="padding-top: env(safe-area-inset-top); border-radius: 0 0 50% 50% / 0 0 28% 28%"
    >
      <div class="max-w-7xl mx-auto flex items-center justify-between gap-2 px-4 sm:px-6 lg:px-10 py-4 sm:py-5 md:py-6">
        <router-link to="/" class="flex items-center gap-2 sm:gap-3 min-w-0">
          <div class="flex items-center -space-x-2 flex-shrink-0">
            <img :src="BSUlogo" alt="BSU Logo" class="w-9 h-9 xs:w-10 xs:h-10 sm:w-12 sm:h-12 md:w-14 md:h-14 lg:w-16 lg:h-16 object-contain drop-shadow" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="w-9 h-9 xs:w-10 xs:h-10 sm:w-12 sm:h-12 md:w-14 md:h-14 lg:w-16 lg:h-16 object-contain drop-shadow" />
          </div>
          <span class="text-white font-extrabold tracking-wide text-xs xs:text-sm sm:text-lg md:text-xl lg:text-2xl uppercase truncate">
            BSU Meneses Campus
          </span>
        </router-link>

        <div class="hidden md:flex items-center gap-1">
          <slot name="actions" />
        </div>

        <button
          v-if="$slots.actions"
          type="button"
          class="md:hidden text-white p-2 -mr-1 rounded-full hover:bg-white/15 transition-colors flex-shrink-0"
          :aria-expanded="mobileOpen"
          aria-label="Toggle navigation menu"
          @click="mobileOpen = !mobileOpen"
        >
          <svg v-if="!mobileOpen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 -translate-y-1"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-1"
      >
        <div
          v-if="mobileOpen && $slots.actions"
          class="md:hidden flex flex-col items-stretch gap-1 px-4 sm:px-6 pb-4 pt-1 border-t border-white/25"
        >
          <slot name="actions" />
        </div>
      </transition>
    </div>
  </header>

  <!-- Standard app header (dashboard / admin / display pages) -->
  <header
    v-else
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
import { ref } from 'vue'
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
  floating: {
    type: Boolean,
    default: false,
  },
})

const mobileOpen = ref(false)
</script>
