<template>
  <div>
    <div class="flex items-baseline justify-between mb-2">
      <p class="block text-sm font-medium text-gray-700">Documents to request</p>
      <p class="text-xs text-gray-500">Select one or more</p>
    </div>

    <p v-if="loading" class="text-sm text-gray-500 py-4 text-center">Loading documents…</p>
    <p v-else-if="!documents.length" class="text-sm text-red-600 py-4">
      No documents are available to request right now. Please ask at the registrar's window.
    </p>

    <ul v-else class="space-y-2" role="group" aria-label="Documents to request">
      <li v-for="doc in documents" :key="doc.id">
        <label
          class="flex gap-3 p-3 sm:p-4 rounded-xl border cursor-pointer transition-colors"
          :class="isChecked(doc.id)
            ? 'border-bsu-primary bg-bsu-primary/5'
            : 'border-gray-200 bg-white hover:border-bsu-primary/40'"
        >
          <input
            type="checkbox"
            class="mt-0.5 w-5 h-5 shrink-0 accent-bsu-primary"
            :checked="isChecked(doc.id)"
            @change="toggle(doc.id)"
          />
          <span class="flex-1 min-w-0">
            <span class="flex flex-wrap items-baseline justify-between gap-x-3">
              <span class="font-medium text-bsu-ink">{{ doc.name }}</span>
              <span v-if="formatFee(doc.fee)" class="text-sm font-semibold text-bsu-primary whitespace-nowrap">
                {{ formatFee(doc.fee) }}
              </span>
            </span>
            <span v-if="doc.processing_time" class="block text-xs text-gray-500 mt-0.5">
              Processing time: {{ doc.processing_time }}
            </span>
            <span
              v-if="isChecked(doc.id) && doc.requirements"
              class="block text-sm text-gray-700 mt-2 p-2 rounded-lg bg-bsu-gold/10 border border-bsu-gold/30"
            >
              <span class="font-semibold">Bring:</span> {{ doc.requirements }}
            </span>
          </span>
        </label>
      </li>
    </ul>

    <div
      v-if="selected.length"
      class="sticky bottom-0 mt-3 flex flex-wrap items-center justify-between gap-2 px-4 py-3 rounded-xl bg-bsu-primary text-white text-sm shadow-sm"
      aria-live="polite"
    >
      <span>{{ selected.length }} document{{ selected.length === 1 ? '' : 's' }} selected</span>
      <span v-if="totalLabel(selected)" class="font-semibold">{{ totalLabel(selected) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatFee, totalLabel } from '@/services/documentFees'

const props = defineProps({
  // Active catalog entries, in display order.
  documents: { type: Array, required: true },
  // Selected document ids.
  modelValue: { type: Array, required: true },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const isChecked = (id) => props.modelValue.includes(id)

// Emitted in catalog order whatever order they were ticked in, matching how
// the server stores them.
const toggle = (id) => {
  const next = isChecked(id)
    ? props.modelValue.filter(x => x !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', props.documents.map(d => d.id).filter(x => next.includes(x)))
}

const selected = computed(() => props.documents.filter(d => props.modelValue.includes(d.id)))
</script>
