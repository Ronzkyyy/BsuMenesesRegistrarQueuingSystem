<template>
  <div v-if="modelValue" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-soft-lg w-full max-w-3xl max-h-full flex flex-col">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-4">
        <h3 class="text-lg font-bold text-bsu-ink">Import Students</h3>
        <button type="button" class="text-gray-400 hover:text-gray-600 disabled:opacity-50" aria-label="Close" :disabled="busy" @click="close">✕</button>
      </div>

      <div class="px-6 py-4 overflow-y-auto space-y-4">
        <div v-if="error" class="p-3 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- Step 1: choose a file -->
        <template v-if="step === 'choose'">
          <p class="text-sm text-gray-600">
            Upload an Excel (.xlsx) or CSV file with one student per row. You'll see a preview before anything is saved.
            Up to 2,000 students and 2 MB per file.
          </p>
          <a href="/api/students/import-template.xlsx" class="btn-secondary btn-md inline-flex">Download template</a>
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1.5">Student file</span>
            <input
              ref="fileInput"
              type="file"
              accept=".xlsx,.csv"
              class="field"
              :disabled="busy"
              @change="onFileChosen"
            />
          </label>
          <p v-if="busy" class="text-sm text-gray-500">Checking the file…</p>
        </template>

        <!-- Step 2 & 3: preview / result -->
        <template v-else>
          <p class="text-sm text-gray-600">
            <span class="font-semibold text-bsu-ink">{{ fileName }}</span> ·
            {{ report.total_rows }} row{{ report.total_rows === 1 ? '' : 's' }}
            <span v-if="step === 'done'"> · import finished</span>
          </p>

          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div v-for="tile in tiles" :key="tile.label" class="rounded-xl border p-3" :class="tile.classes">
              <p class="text-2xl font-bold">{{ tile.value }}</p>
              <p class="text-xs font-semibold uppercase tracking-wide">{{ tile.label }}</p>
            </div>
          </div>

          <p v-if="report.ignored_columns.length" class="text-xs text-gray-500">
            Ignored columns: {{ report.ignored_columns.join(', ') }}
          </p>

          <div v-if="report.problems.length">
            <p class="text-sm font-semibold text-bsu-ink mb-1.5">
              {{ step === 'done' ? 'Not imported' : 'Rows that will be skipped' }}
            </p>
            <div class="overflow-x-auto border border-gray-200 rounded-xl max-h-64">
              <table class="min-w-full text-sm">
                <thead class="bg-bsu-surface text-xs uppercase text-gray-500">
                  <tr>
                    <th class="px-3 py-2 text-left">Row</th>
                    <th class="px-3 py-2 text-left">Student No.</th>
                    <th class="px-3 py-2 text-left">Column</th>
                    <th class="px-3 py-2 text-left">Problem</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="p in report.problems" :key="`${p.row}-${p.column}`">
                    <td class="px-3 py-2 whitespace-nowrap">{{ p.row }}</td>
                    <td class="px-3 py-2 whitespace-nowrap">{{ p.student_number || '—' }}</td>
                    <td class="px-3 py-2 whitespace-nowrap">{{ p.column }}</td>
                    <td class="px-3 py-2">{{ p.message }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <details v-if="report.changes.length" class="border border-gray-200 rounded-xl">
            <summary class="px-3 py-2 text-sm font-semibold text-bsu-ink cursor-pointer">
              {{ step === 'done' ? 'Saved changes' : 'Changes to be saved' }} ({{ report.changes.length }})
            </summary>
            <ul class="divide-y divide-gray-100 max-h-64 overflow-y-auto text-sm">
              <li v-for="c in report.changes" :key="c.row" class="px-3 py-2">
                <span class="font-medium text-bsu-ink">{{ c.student_number }} · {{ c.name }}</span>
                <span class="ml-2 text-xs uppercase font-semibold" :class="c.action === 'new' ? 'text-green-700' : 'text-bsu-gold-dark'">
                  {{ c.action === 'new' ? 'New' : 'Update' }}
                </span>
                <span v-for="(pair, field) in c.fields" :key="field" class="block text-xs text-gray-500">
                  {{ field.replace(/_/g, ' ') }}: {{ pair[0] }} → {{ pair[1] }}
                </span>
              </li>
            </ul>
          </details>
        </template>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 flex flex-wrap justify-end gap-3">
        <template v-if="step === 'preview'">
          <button type="button" class="btn-secondary btn-md" :disabled="busy" @click="reset">Choose another file</button>
          <button type="button" class="btn-primary btn-md" :disabled="busy || !toSave" @click="commit">
            {{ busy ? 'Importing…' : `Import ${toSave} student${toSave === 1 ? '' : 's'}` }}
          </button>
        </template>
        <template v-else-if="step === 'done'">
          <button v-if="report.problems.length" type="button" class="btn-secondary btn-md" @click="downloadErrors">
            Download rows with errors (.csv)
          </button>
          <button type="button" class="btn-primary btn-md" @click="close">Close</button>
        </template>
        <button v-else type="button" class="btn-secondary btn-md" :disabled="busy" @click="close">Cancel</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { buildErrorCsv } from '@/services/studentImportCsv'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'imported'])
const queueStore = useQueueStore()

const step = ref('choose') // choose | preview | done
const file = ref(null)
const fileInput = ref(null)
const report = ref(null)
const busy = ref(false)
const error = ref('')

const fileName = computed(() => file.value?.name || '')
const toSave = computed(() => (report.value ? report.value.new + report.value.updated : 0))
const tiles = computed(() => [
  { label: 'New', value: report.value.new, classes: 'border-green-100 bg-green-50 text-green-800' },
  { label: 'Updated', value: report.value.updated, classes: 'border-bsu-gold/40 bg-bsu-gold/10 text-bsu-gold-dark' },
  { label: 'Unchanged', value: report.value.unchanged, classes: 'border-gray-200 bg-gray-50 text-gray-600' },
  { label: 'Invalid', value: report.value.invalid, classes: 'border-red-100 bg-red-50 text-red-700' },
])

const reset = () => {
  step.value = 'choose'
  file.value = null
  report.value = null
  error.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

const close = () => {
  if (busy.value) return
  const imported = step.value === 'done'
  reset()
  emit('update:modelValue', false)
  if (imported) emit('imported')
}

const onFileChosen = async (event) => {
  const chosen = event.target.files?.[0]
  if (!chosen) return
  file.value = chosen
  error.value = ''
  busy.value = true
  try {
    report.value = await queueStore.previewStudentImport(chosen)
    step.value = 'preview'
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not read this file.'
    if (fileInput.value) fileInput.value.value = ''
  } finally {
    busy.value = false
  }
}

const commit = async () => {
  error.value = ''
  busy.value = true
  try {
    report.value = await queueStore.commitStudentImport(file.value)
    step.value = 'done'
  } catch (err) {
    error.value = err.response?.data?.detail || 'The import failed. Nothing was saved - please try again.'
  } finally {
    busy.value = false
  }
}

const downloadErrors = () => {
  const blob = new Blob([buildErrorCsv(report.value.columns, report.value.problems)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'students_import_errors.csv'
  a.click()
  URL.revokeObjectURL(url)
}
</script>
