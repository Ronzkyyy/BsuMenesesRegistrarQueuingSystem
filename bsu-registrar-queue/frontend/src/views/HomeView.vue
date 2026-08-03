<template>
  <div class="relative min-h-screen flex flex-col overflow-x-hidden">
    <!-- Full-viewport background, fixed so it always covers the entire screen behind the header too -->
    <img
      :src="archBackground"
      alt=""
      class="fixed inset-0 -z-20 w-full h-full object-cover scale-110 blur-sm"
    />
    <div class="fixed inset-0 -z-10 bg-white/45"></div>
    <div
      class="fixed -top-24 -left-24 -z-10 w-72 h-72 sm:w-96 sm:h-96 rounded-full bg-pink-400/25 blur-3xl"
      aria-hidden="true"
    ></div>
    <div
      class="fixed -bottom-24 -right-24 -z-10 w-72 h-72 sm:w-96 sm:h-96 rounded-full bg-amber-300/25 blur-3xl"
      aria-hidden="true"
    ></div>

    <AppHeader floating>
      <template #actions>
        <router-link
          to="/queues"
          class="block md:inline-block text-center text-sm font-semibold text-white/90 hover:text-white px-4 py-2 md:py-1.5 rounded-full hover:bg-white/15 transition-colors"
        >
          Browse Queues
        </router-link>
        <router-link
          to="/login"
          class="block md:inline-block text-center text-sm font-semibold text-white/90 hover:text-white px-4 py-2 md:py-1.5 rounded-full hover:bg-white/15 transition-colors"
        >
          Staff Login
        </router-link>
      </template>
    </AppHeader>

    <main class="relative flex-1 flex items-center justify-center px-4 py-12 sm:py-16">
      <div class="relative z-10 flex flex-col items-center text-center px-4 sm:px-6 max-w-3xl mx-auto">
        <h1
          class="text-6xl sm:text-8xl md:text-9xl font-extrabold tracking-tight leading-none bg-gradient-to-r from-pink-600 via-orange-500 to-amber-400 bg-clip-text text-transparent drop-shadow-sm"
        >
          WELCOME
        </h1>

        <div class="flex items-center gap-3 mt-5 sm:mt-6 w-full max-w-xs sm:max-w-sm">
          <span class="h-px flex-1 bg-gradient-to-r from-transparent via-pink-400/70 to-orange-400/70"></span>
          <svg class="w-5 h-5 sm:w-6 sm:h-6 text-orange-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-5.13a4 4 0 11-8 0 4 4 0 018 0zm6 3a4 4 0 10-8 0" />
          </svg>
          <span class="h-px flex-1 bg-gradient-to-l from-transparent via-amber-400/70 to-orange-400/70"></span>
        </div>

        <p class="mt-3 sm:mt-4 text-xs sm:text-sm md:text-base font-semibold tracking-[0.2em] sm:tracking-[0.3em] text-gray-700 uppercase">
          Registrar Queuing System
        </p>

        <router-link
          to="/queues"
          class="group mt-8 sm:mt-10 inline-flex items-center gap-2 bg-white/90 backdrop-blur text-gray-900 font-semibold text-sm sm:text-base px-6 sm:px-8 py-3 sm:py-3.5 rounded-full shadow-lg hover:shadow-2xl hover:bg-white hover:-translate-y-0.5 active:translate-y-0 transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-pink-500"
        >
          Let's get started
          <svg
            class="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </router-link>
      </div>
    </main>
  </div>
</template>

<script setup>
import AppHeader from '@/components/AppHeader.vue'
import archBackground from '@/assets/archBackground.png'
</script>
