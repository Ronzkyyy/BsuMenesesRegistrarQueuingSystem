<template>
  <div class="relative min-h-screen flex flex-col bg-bsu-surface overflow-x-hidden">
    <AppHeader floating>
      <template #actions>
        <router-link
          to="/login"
          class="btn text-sm px-5 py-2 rounded-xl bg-gradient-to-r from-bsu-primary to-bsu-peach text-white shadow-sm hover:shadow focus:ring-bsu-primary"
        >
          Staff Login
        </router-link>
      </template>
    </AppHeader>

    <main class="flex-1">
      <!-- Full-screen hero -->
      <section class="relative w-full min-h-[75vh] sm:min-h-screen flex items-center overflow-hidden -mt-[1px]">
        <img
          :src="archBackground"
          alt="Bulacan State University Meneses Campus arch"
          class="absolute inset-0 w-full h-full object-cover"
        />
        <div class="absolute inset-0 bg-gradient-to-r from-bsu-surface/70 via-bsu-surface/30 to-transparent"></div>
        <div class="absolute inset-0 bg-gradient-to-t from-bsu-surface/40 via-transparent to-transparent"></div>

        <div class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 w-full py-24 sm:py-0">
          <div class="max-w-xl text-center sm:text-left">
            <h1 class="text-5xl sm:text-6xl md:text-7xl font-black tracking-tight leading-[1.05] text-[#C81E4E] [text-shadow:0_2px_10px_rgba(0,0,0,0.4)]">
              WELCOME
            </h1>
            <p class="mt-2 text-2xl sm:text-3xl md:text-4xl font-bold text-bsu-ink drop-shadow-sm">
              to BSU Registrar Queue System
            </p>
            <p class="mt-5 text-base sm:text-lg font-semibold text-gray-700 max-w-md mx-auto sm:mx-0 drop-shadow-sm">
              Fast, transparent, and accessible queue management for students.
            </p>

            <router-link
              to="/queues"
              class="btn mt-8 gap-2 text-base px-8 py-3.5 rounded-2xl bg-gradient-to-r from-bsu-primary to-bsu-peach text-white shadow-sm hover:shadow focus:ring-bsu-primary"
            >
              Let's Get Started
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </router-link>
          </div>
        </div>
      </section>

      <!-- Vision & Mission -->
      <section class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-10 py-16 sm:py-24">
        <div class="text-center mb-10 sm:mb-14">
          <span class="inline-block text-xs font-semibold tracking-[0.25em] uppercase text-bsu-primary">
            Bulacan State University
          </span>
          <h2 class="mt-2 text-3xl sm:text-4xl font-bold text-bsu-ink">Vision &amp; Mission</h2>
        </div>

        <div class="grid sm:grid-cols-2 gap-6 sm:gap-8">
          <div class="bg-white rounded-3xl shadow-soft border border-gray-100 p-8 sm:p-10">
            <div class="flex items-center gap-3 mb-5 border-l-4 border-bsu-primary pl-4">
              <h3 class="text-sm font-bold tracking-[0.2em] uppercase text-bsu-primary">Vision</h3>
            </div>
            <p class="text-lg sm:text-xl leading-relaxed text-bsu-ink font-medium">
              {{ vision }}
            </p>
          </div>

          <div class="bg-white rounded-3xl shadow-soft border border-gray-100 p-8 sm:p-10">
            <div class="flex items-center gap-3 mb-5 border-l-4 border-bsu-peach pl-4">
              <h3 class="text-sm font-bold tracking-[0.2em] uppercase text-bsu-peach-dark">Mission</h3>
            </div>
            <p class="text-lg sm:text-xl leading-relaxed text-bsu-ink font-medium">
              {{ mission }}
            </p>
          </div>
        </div>
      </section>
    </main>

    <AppFooter />
  </div>
</template>

<script setup>
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import archBackground from '@/assets/archBackground.png'

const vision = 'Ang Bulacan State University ay isang progresibong institusyong lumilikha ng kaalaman na kinikilala sa daigdig sa pinakamahusay na pagtuturo, nangungunang mga pananaliksik, at maagap na pagtugon sa pangangailangan ng komunidad.'

const mission = 'Ang Bulacan State University ay may hangaring humubog ng mga propesyonal na mahuhusay, etikal, at handang maglingkod, na nakapag-aambag sa patuloy na pagunlad ng bayan.'
</script>
