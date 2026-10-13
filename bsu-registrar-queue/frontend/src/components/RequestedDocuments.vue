<template>
  <div v-if="documents.length" class="text-left">
    <p class="text-xs font-semibold text-bsu-primary uppercase tracking-wide mb-1.5">{{ title }}</p>
    <ul class="divide-y divide-gray-100 border border-gray-200 rounded-xl bg-white">
      <li
        v-for="doc in documents"
        :key="doc.document_id"
        class="flex items-baseline justify-between gap-3 px-3 py-2 text-sm"
      >
        <span class="text-bsu-ink">{{ doc.name }}</span>
        <span v-if="formatFee(doc.fee)" class="text-gray-600 whitespace-nowrap">{{ formatFee(doc.fee) }}</span>
      </li>
    </ul>
    <p v-if="totalLabel(documents)" class="text-sm font-semibold text-bsu-ink text-right mt-1.5">
      {{ totalLabel(documents) }}
    </p>
  </div>
</template>

<script setup>
import { formatFee, totalLabel } from '@/services/documentFees'

defineProps({
  // RequestedDocument items from a ticket/appointment response.
  documents: { type: Array, default: () => [] },
  title: { type: String, default: 'Requested documents' },
})
</script>
