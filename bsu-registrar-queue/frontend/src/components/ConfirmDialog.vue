<template>
  <Transition
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-100 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="modelValue"
      class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-[60] p-4"
      @keydown.esc="cancel"
    >
      <Transition
        appear
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div v-if="modelValue" class="bg-white rounded-2xl shadow-soft-lg max-w-sm w-full mx-4">
          <div class="p-6 text-center">
            <div
              class="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4"
              :class="isDanger ? 'bg-red-50' : 'bg-bsu-primary/10'"
            >
              <svg
                v-if="isDanger"
                class="w-6 h-6 text-red-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <svg
                v-else
                class="w-6 h-6 text-bsu-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>

            <h3 class="text-lg font-bold text-bsu-ink mb-1">{{ title }}</h3>
            <p class="text-sm text-gray-500 whitespace-pre-line">{{ message }}</p>

            <div class="flex gap-3 mt-6">
              <button
                type="button"
                @click="cancel"
                :disabled="loading"
                class="btn btn-secondary flex-1 py-2"
              >
                {{ cancelLabel }}
              </button>
              <button
                type="button"
                @click="confirm"
                :disabled="loading"
                class="btn flex-1 py-2"
                :class="isDanger ? 'btn-danger-solid' : 'btn-primary'"
              >
                <span v-if="!loading">{{ confirmLabel }}</span>
                <span v-else>Please wait…</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: 'Are you sure?' },
  message: { type: String, default: '' },
  confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Go Back' },
  variant: { type: String, default: 'primary' }, // 'primary' | 'danger'
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const isDanger = computed(() => props.variant === 'danger')

const confirm = () => {
  if (props.loading) return
  emit('confirm')
}

const cancel = () => {
  if (props.loading) return
  emit('update:modelValue', false)
  emit('cancel')
}
</script>
