<template>
  <div class="min-h-screen flex flex-col">
    <AppHeader gradient />

    <main class="relative flex-1 flex items-center justify-center overflow-hidden">
      <img
        :src="archBackground"
        alt=""
        class="absolute inset-0 w-full h-full object-cover scale-110 blur-sm"
      />
      <div class="absolute inset-0 bg-white/40"></div>

      <div class="relative z-10 text-center px-4">
        <p
          class="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-bsu-primary to-bsu-gold bg-clip-text text-transparent"
        >
          WELCOME TO THE
        </p>
        <h1
          class="text-4xl sm:text-6xl font-extrabold bg-gradient-to-r from-bsu-primary to-bsu-gold bg-clip-text text-transparent leading-tight"
        >
          REGISTRAR QUEUING SYSTEM
        </h1>

        <router-link
          to="/queues"
          class="mt-8 inline-flex items-center gap-2 bg-white text-bsu-primary font-bold px-8 py-3 rounded-full shadow-lg hover:shadow-xl transition-shadow focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary"
        >
          BROWSE
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
