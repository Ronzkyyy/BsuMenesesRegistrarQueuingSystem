<template>
  <div>
    <div class="mb-8 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-3xl font-bold text-bsu-ink">Document List</h2>
        <p class="mt-2 text-gray-500">Documents students can request under Request Documents, with fees and requirements</p>
      </div>
      <button @click="openCreate" class="btn-primary btn-md">
        <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Add Document
      </button>
    </div>

    <div v-if="listError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ listError }}</p>
    </div>
    <div v-if="notice" class="bg-green-50 border border-green-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-green-800">{{ notice }}</p>
    </div>

    <div class="panel overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-100">
        <thead class="bg-bsu-surface">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Order</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Document</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Fee</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Processing Time</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
            <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr
            v-for="(doc, index) in queueStore.documents"
            :key="doc.id"
            class="table-row-hover"
            :class="doc.is_active ? '' : 'opacity-60'"
          >
            <td class="px-4 py-3 text-sm whitespace-nowrap">
              <div v-if="doc.is_active" class="flex gap-1">
                <button
                  type="button"
                  class="btn-secondary btn-sm px-2"
                  :disabled="actionLoading || !canMove(index, -1)"
                  :aria-label="`Move ${doc.short_name} up`"
                  @click="move(index, -1)"
                >↑</button>
                <button
                  type="button"
                  class="btn-secondary btn-sm px-2"
                  :disabled="actionLoading || !canMove(index, 1)"
                  :aria-label="`Move ${doc.short_name} down`"
                  @click="move(index, 1)"
                >↓</button>
              </div>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td class="px-4 py-3 text-sm">
              <p class="font-medium text-bsu-ink">{{ doc.name }}</p>
              <p class="text-xs text-gray-500">{{ doc.short_name }}</p>
              <p v-if="doc.requirements" class="text-xs text-gray-500 mt-1 max-w-md">
                <span class="font-semibold">Bring:</span> {{ doc.requirements }}
              </p>
            </td>
            <td class="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{{ formatFee(doc.fee) || 'Not listed' }}</td>
            <td class="px-4 py-3 text-sm text-gray-600">{{ doc.processing_time || '—' }}</td>
            <td class="px-4 py-3 text-sm">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-lg text-[11px] font-semibold uppercase tracking-wide"
                :class="doc.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'"
              >
                {{ doc.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="px-4 py-3 text-sm text-right whitespace-nowrap">
              <div class="inline-flex gap-2">
                <button type="button" class="btn-secondary btn-sm" @click="openEdit(doc)">Edit</button>
                <button
                  v-if="doc.is_active"
                  type="button"
                  class="btn-danger btn-sm"
                  @click="deactivateConfirm = { open: true, doc }"
                >Deactivate</button>
                <button
                  v-else
                  type="button"
                  class="btn-primary btn-sm"
                  :disabled="actionLoading"
                  @click="setActive(doc, true)"
                >Activate</button>
              </div>
            </td>
          </tr>
          <tr v-if="!queueStore.documents.length && !queueStore.loading">
            <td colspan="6" class="px-4 py-8 text-center text-sm text-gray-500">No documents yet.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add / Edit modal -->
    <div v-if="form.open" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-lg w-full max-h-full overflow-y-auto">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">{{ form.id ? 'Edit Document' : 'Add Document' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Name shown to students</label>
            <input v-model="form.name" type="text" maxlength="100" class="field"
                   placeholder="e.g., Certified True Copy - Transcript of Records (TOR)" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Short name</label>
            <input v-model="form.short_name" type="text" maxlength="30" class="field" placeholder="e.g., TOR" />
            <p class="mt-1 text-xs text-gray-500">Used on the Counter screen, in reports and in the Excel export.</p>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Fee (₱)</label>
              <input v-model="form.fee" type="text" inputmode="decimal" maxlength="9" class="field" placeholder="Leave blank if not listed" />
              <p class="mt-1 text-xs text-gray-500">Enter 0 for free.</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Processing time</label>
              <input v-model="form.processing_time" type="text" maxlength="50" class="field" placeholder="e.g., 3–5 working days" />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Requirements</label>
            <textarea v-model="form.requirements" rows="3" maxlength="500" class="field"
                      placeholder="What the student should bring, e.g., valid school ID and clearance form"></textarea>
          </div>

          <div v-if="form.error" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ form.error }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
          <button @click="form.open = false" class="btn-secondary btn-md">Cancel</button>
          <button @click="save" :disabled="actionLoading" class="btn-primary btn-md">
            {{ form.id ? 'Save Changes' : 'Add' }}
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      v-model="deactivateConfirm.open"
      title="Deactivate document?"
      :message="`${deactivateConfirm.doc?.name} will no longer appear on the kiosk or booking form. Tickets and appointments that already requested it keep it.`"
      confirm-label="Deactivate"
      variant="danger"
      :loading="actionLoading"
      @confirm="setActive(deactivateConfirm.doc, false)"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { formatFee } from '@/services/documentFees'

const queueStore = useQueueStore()

const listError = ref('')
const notice = ref('')
const actionLoading = ref(false)
const deactivateConfirm = ref({ open: false, doc: null })

const emptyForm = () => ({
  open: false, id: null, error: '',
  name: '', short_name: '', fee: '', processing_time: '', requirements: '',
})
const form = reactive(emptyForm())

const FEE_PATTERN = /^\d{1,6}(\.\d{1,2})?$/

const errorText = (err, fallback) => {
  const detail = err.response?.data?.detail
  return Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail || fallback
}

const openCreate = () => {
  Object.assign(form, emptyForm(), { open: true })
}

const openEdit = (doc) => {
  Object.assign(form, emptyForm(), {
    open: true,
    id: doc.id,
    name: doc.name,
    short_name: doc.short_name,
    fee: doc.fee ?? '',
    processing_time: doc.processing_time ?? '',
    requirements: doc.requirements ?? '',
  })
}

const save = async () => {
  form.error = ''
  const fee = String(form.fee).trim()
  if (!form.name.trim() || !form.short_name.trim()) {
    form.error = 'Name and short name are required.'
    return
  }
  if (fee && !FEE_PATTERN.test(fee)) {
    form.error = 'Enter the fee as a number, e.g. 50 or 75.50.'
    return
  }
  const payload = {
    name: form.name.trim(),
    short_name: form.short_name.trim(),
    fee: fee || null,
    processing_time: form.processing_time.trim() || null,
    requirements: form.requirements.trim() || null,
  }
  actionLoading.value = true
  try {
    if (form.id) {
      await queueStore.updateDocument(form.id, payload)
      notice.value = `Saved changes to ${payload.short_name}.`
    } else {
      await queueStore.createDocument(payload)
      notice.value = `Added ${payload.short_name}. It now appears on the kiosk and booking form.`
    }
    form.open = false
  } catch (err) {
    form.error = errorText(err, 'Failed to save the document')
  } finally {
    actionLoading.value = false
  }
}

const setActive = async (doc, active) => {
  if (!doc) return
  listError.value = ''
  notice.value = ''
  actionLoading.value = true
  try {
    await queueStore.updateDocument(doc.id, { is_active: active })
    deactivateConfirm.value = { open: false, doc: null }
    // Re-fetch so the row moves to its group (active first).
    await queueStore.fetchAllDocuments()
    notice.value = `${doc.short_name} is now ${active ? 'active' : 'inactive'}.`
  } catch (err) {
    deactivateConfirm.value = { open: false, doc: null }
    listError.value = errorText(err, 'Failed to update the document')
  } finally {
    actionLoading.value = false
  }
}

// Moves only swap neighbours within the active group - inactive entries
// aren't shown to students, so their order doesn't matter.
const canMove = (index, dir) => {
  const neighbour = queueStore.documents[index + dir]
  return Boolean(neighbour && neighbour.is_active)
}

const move = async (index, dir) => {
  if (!canMove(index, dir)) return
  const ids = queueStore.documents.map((d) => d.id)
  ;[ids[index], ids[index + dir]] = [ids[index + dir], ids[index]]
  listError.value = ''
  actionLoading.value = true
  try {
    await queueStore.reorderDocuments(ids)
  } catch (err) {
    listError.value = errorText(err, 'Failed to save the new order')
  } finally {
    actionLoading.value = false
  }
}

onMounted(async () => {
  try {
    await queueStore.fetchAllDocuments()
  } catch (err) {
    listError.value = errorText(err, 'Failed to load documents')
  }
})
</script>
