<template>
  <!-- Floating pill header (landing page) -->
  <header v-if="floating" class="sticky top-0 z-50 w-full px-3 sm:px-6 pt-3 sm:pt-4">
    <div
      class="relative w-full max-w-7xl mx-auto bg-white/95 backdrop-blur shadow-soft-lg rounded-2xl sm:rounded-[1.75rem] border border-gray-100"
      style="padding-top: env(safe-area-inset-top)"
    >
      <div class="flex items-center justify-between gap-2 px-4 sm:px-6 lg:px-8 py-3 sm:py-4">
        <router-link to="/" class="flex items-center gap-2 sm:gap-3 min-w-0">
          <div class="flex items-center -space-x-2 flex-shrink-0">
            <img :src="BSUlogo" alt="BSU Logo" class="h-9 w-auto xs:h-10 sm:h-12 object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="h-9 w-auto xs:h-10 sm:h-12 object-contain" />
          </div>
          <div class="min-w-0">
            <span class="block text-bsu-ink font-bold tracking-wide text-xs xs:text-sm sm:text-base md:text-lg uppercase truncate">
              BSU Meneses Campus
            </span>
            <span class="hidden sm:block text-xs text-gray-500 truncate">Registrar Queue Management System</span>
          </div>
        </router-link>

        <div class="hidden md:flex items-center gap-1">
          <slot name="actions" />
        </div>

        <button
          v-if="$slots.actions"
          type="button"
          class="md:hidden text-bsu-ink p-2 -mr-1 rounded-xl hover:bg-bsu-primary/10 transition-colors flex-shrink-0"
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
          class="md:hidden flex flex-col items-stretch gap-1 px-4 sm:px-6 pb-4 pt-1 border-t border-gray-100"
        >
          <slot name="actions" />
        </div>
      </transition>
    </div>
  </header>

  <!-- Standard app header (dashboard / admin / display pages) -->
  <header v-else class="bg-white shadow-soft border-b border-gray-100">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
      <div class="flex items-center justify-between">
        <router-link to="/" class="flex items-center space-x-3">
          <div class="flex items-center space-x-2 flex-shrink-0">
            <img :src="BSUlogo" alt="BSU Logo" class="h-12 w-auto sm:h-14 object-contain" />
            <img :src="MENESESlogo" alt="Meneses Campus Logo" class="h-12 w-auto sm:h-14 object-contain" />
          </div>
          <div>
            <h1 class="text-lg sm:text-xl font-bold leading-tight text-bsu-ink">BSU Meneses Campus</h1>
            <p class="text-sm text-bsu-primary-dark font-medium">{{ subtitle }}</p>
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
