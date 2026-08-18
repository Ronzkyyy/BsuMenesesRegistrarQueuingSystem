<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-bsu-ink">Media & Announcements</h2>
      <p class="mt-2 text-gray-500">Manage the media playlist and announcement ticker shown on display boards</p>
    </div>

    <!-- Media Section -->
    <div class="panel mb-8">
      <div class="panel-header flex items-center justify-between">
        <h3 class="text-xl font-bold text-bsu-ink">Media Playlist</h3>
        <button
          @click="openCreateMediaModal"
          class="btn-primary btn-md"
        >
          Add Media Item
        </button>
      </div>
      <div class="p-6">
        <div v-if="mediaError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-4">
          <p class="text-sm text-red-700">{{ mediaError }}</p>
        </div>

        <div class="overflow-hidden">
          <table class="min-w-full divide-y divide-gray-100">
            <thead class="bg-bsu-surface">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Type</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">URL</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Duration</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Order</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="item in queueStore.mediaItems" :key="item.id" class="table-row-hover">
                <td class="px-4 py-4 text-sm text-bsu-ink capitalize">{{ item.media_type }}</td>
                <td class="px-4 py-4 text-sm text-gray-500 max-w-xs">
                  <span class="block truncate">{{ item.url }}</span>
                  <span class="block text-xs text-gray-400">{{ item.source === 'upload' ? 'Uploaded file' : 'External link' }}</span>
                </td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_duration_seconds }}s</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_order }}</td>
                <td class="px-4 py-4">
                  <StatusBadge :status="item.is_active ? 'active' : 'inactive'" />
                </td>
                <td class="px-4 py-4 text-right space-x-2 whitespace-nowrap">
                  <button
                    @click="toggleMediaActive(item)"
                    :disabled="mediaActionLoading"
                    class="btn-secondary btn-sm"
                  >
                    {{ item.is_active ? 'Deactivate' : 'Activate' }}
                  </button>
                  <button
                    @click="openEditMediaModal(item)"
                    :disabled="mediaActionLoading"
                    class="btn-secondary btn-sm"
                  >
                    Edit
                  </button>
                  <button
                    @click="removeMediaItem(item.id)"
                    :disabled="mediaActionLoading"
                    class="btn-danger btn-sm"
                  >
                    Delete
                  </button>
                </td>
              </tr>
              <tr v-if="queueStore.mediaItems.length === 0">
                <td colspan="6" class="px-4 py-8 text-center text-gray-500">No media items yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Announcements Section -->
    <div class="panel">
      <div class="panel-header flex items-center justify-between">
        <h3 class="text-xl font-bold text-bsu-ink">Announcements</h3>
        <button
          @click="openCreateAnnouncementModal"
          class="btn-primary btn-md"
        >
          Add Announcement
        </button>
      </div>
      <div class="p-6">
        <div v-if="announcementError" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-4">
          <p class="text-sm text-red-700">{{ announcementError }}</p>
        </div>

        <div class="overflow-hidden">
          <table class="min-w-full divide-y divide-gray-100">
            <thead class="bg-bsu-surface">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Text</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Order</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="item in queueStore.announcements" :key="item.id" class="table-row-hover">
                <td class="px-4 py-4 text-sm text-bsu-ink max-w-md truncate">{{ item.text }}</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_order }}</td>
                <td class="px-4 py-4">
                  <StatusBadge :status="item.is_active ? 'active' : 'inactive'" />
                </td>
                <td class="px-4 py-4 text-right space-x-2 whitespace-nowrap">
                  <button
                    @click="toggleAnnouncementActive(item)"
                    :disabled="announcementActionLoading"
                    class="btn-secondary btn-sm"
                  >
                    {{ item.is_active ? 'Deactivate' : 'Activate' }}
                  </button>
                  <button
                    @click="openEditAnnouncementModal(item)"
                    :disabled="announcementActionLoading"
                    class="btn-secondary btn-sm"
                  >
                    Edit
                  </button>
                  <button
                    @click="removeAnnouncement(item.id)"
                    :disabled="announcementActionLoading"
                    class="btn-danger btn-sm"
                  >
                    Delete
                  </button>
                </td>
              </tr>
              <tr v-if="queueStore.announcements.length === 0">
                <td colspan="4" class="px-4 py-8 text-center text-gray-500">No announcements yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Media Modal -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div v-if="showMediaModal" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50">
      <Transition
        appear
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">{{ editingMediaId ? 'Edit Media Item' : 'Add Media Item' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div class="flex rounded-xl border border-gray-200 overflow-hidden">
            <button
              type="button"
              @click="mediaMode = 'upload'"
              class="flex-1 px-3 py-2 text-sm font-medium transition-colors duration-150"
              :class="mediaMode === 'upload' ? 'bg-bsu-primary text-white' : 'bg-white text-gray-700 hover:bg-bsu-primary/10'"
            >
              Upload File
            </button>
            <button
              type="button"
              @click="mediaMode = 'link'"
              class="flex-1 px-3 py-2 text-sm font-medium transition-colors duration-150"
              :class="mediaMode === 'link' ? 'bg-bsu-primary text-white' : 'bg-white text-gray-700 hover:bg-bsu-primary/10'"
            >
              Paste URL
            </button>
          </div>

          <div v-if="mediaMode === 'link'">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Type</label>
            <select
              v-model="mediaForm.media_type"
              class="field"
            >
              <option value="image">Image</option>
              <option value="video">Video (embeddable URL, e.g. YouTube /embed/ link)</option>
            </select>
          </div>

          <div v-if="mediaMode === 'link'">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">URL</label>
            <input
              v-model="mediaForm.url"
              type="text"
              class="field"
              placeholder="https://..."
            />
          </div>

          <div v-else>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">File</label>
            <input
              type="file"
              accept="image/*,video/*"
              @change="onMediaFileSelected"
              class="w-full text-sm text-gray-700 file:mr-3 file:px-3 file:py-2 file:rounded-xl file:border-0 file:bg-bsu-primary file:text-white file:text-sm file:transition-colors file:duration-150 hover:file:bg-bsu-primary-dark"
            />
            <p v-if="editingMediaId && !selectedFile" class="mt-1 text-xs text-gray-500">Leave empty to keep the current file.</p>
            <p class="mt-1 text-xs text-gray-500">Images up to 5MB (jpg, png, gif, webp); videos up to 50MB (mp4, webm, ogg).</p>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Duration (seconds)</label>
              <input
                v-model.number="mediaForm.display_duration_seconds"
                type="number"
                min="1"
                max="300"
                class="field"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Order</label>
              <input
                v-model.number="mediaForm.display_order"
                type="number"
                min="0"
                class="field"
              />
            </div>
          </div>
          <div v-if="mediaModalError" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ mediaModalError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
          <button
            @click="showMediaModal = false"
            class="btn-secondary btn-md"
          >
            Cancel
          </button>
          <button
            @click="saveMedia"
            :disabled="mediaActionLoading"
            class="btn-primary btn-md"
          >
            {{ editingMediaId ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
      </Transition>
    </div>
    </Transition>

    <!-- Announcement Modal -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div v-if="showAnnouncementModal" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50">
      <Transition
        appear
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">{{ editingAnnouncementId ? 'Edit Announcement' : 'Add Announcement' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Text</label>
            <textarea
              v-model="announcementForm.text"
              rows="3"
              maxlength="500"
              class="field"
              placeholder="e.g., Enrollment for AY 2026-2027 is now open"
            ></textarea>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Order</label>
            <input
              v-model.number="announcementForm.display_order"
              type="number"
              min="0"
              class="field"
            />
          </div>
          <div v-if="announcementModalError" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ announcementModalError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
          <button
            @click="showAnnouncementModal = false"
            class="btn-secondary btn-md"
          >
            Cancel
          </button>
          <button
            @click="saveAnnouncement"
            :disabled="announcementActionLoading"
            class="btn-primary btn-md"
          >
            {{ editingAnnouncementId ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
      </Transition>
    </div>
    </Transition>

    <ConfirmDialog
      v-model="confirmDialog.open"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :confirm-label="confirmDialog.confirmLabel"
      :variant="confirmDialog.variant"
      :loading="confirmLoading"
      @confirm="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const queueStore = useQueueStore()

// Shared confirm dialog (edits and deletes, media and announcements alike -
// only one modal can be on screen at a time anyway).
const confirmDialog = ref({ open: false, title: '', message: '', confirmLabel: 'Confirm', variant: 'primary' })
const confirmLoading = ref(false)
let confirmAction = null

const openConfirm = ({ title, message, confirmLabel = 'Confirm', variant = 'primary', action }) => {
  confirmAction = action
  confirmDialog.value = { open: true, title, message, confirmLabel, variant }
}

const handleConfirm = async () => {
  if (!confirmAction) return
  confirmLoading.value = true
  try {
    await confirmAction()
  } catch (err) {
    // the action itself already recorded a user-facing error message
  } finally {
    confirmLoading.value = false
    confirmDialog.value.open = false
    confirmAction = null
  }
}

// Media state
const mediaError = ref('')
const mediaModalError = ref('')
const mediaActionLoading = ref(false)
const showMediaModal = ref(false)
const editingMediaId = ref(null)
const mediaMode = ref('link')
const selectedFile = ref(null)
const editingOriginalSource = ref(null)
const mediaForm = ref({
  media_type: 'image',
  url: '',
  display_duration_seconds: 10,
  display_order: 0,
})

const ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
const ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.webm', '.ogg']
const MAX_IMAGE_SIZE = 5 * 1024 * 1024
const MAX_VIDEO_SIZE = 50 * 1024 * 1024

const validateSelectedFile = (file) => {
  const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
  const isImage = ALLOWED_IMAGE_EXTENSIONS.includes(ext)
  const isVideo = ALLOWED_VIDEO_EXTENSIONS.includes(ext)
  if (!isImage && !isVideo) {
    return `Unsupported file type '${ext}'. Allowed: images (${ALLOWED_IMAGE_EXTENSIONS.join(', ')}), videos (${ALLOWED_VIDEO_EXTENSIONS.join(', ')})`
  }
  const maxSize = isImage ? MAX_IMAGE_SIZE : MAX_VIDEO_SIZE
  if (file.size > maxSize) {
    return `File too large. Maximum size for ${isImage ? 'image' : 'video'} is ${maxSize / (1024 * 1024)}MB`
  }
  return null
}

const onMediaFileSelected = (event) => {
  const file = event.target.files[0] || null
  if (file) {
    const validationError = validateSelectedFile(file)
    if (validationError) {
      mediaModalError.value = validationError
      selectedFile.value = null
      event.target.value = ''
      return
    }
  }
  mediaModalError.value = ''
  selectedFile.value = file
}

const openCreateMediaModal = () => {
  mediaModalError.value = ''
  editingMediaId.value = null
  mediaMode.value = 'link'
  selectedFile.value = null
  editingOriginalSource.value = null
  mediaForm.value = { media_type: 'image', url: '', display_duration_seconds: 10, display_order: 0 }
  showMediaModal.value = true
}

const openEditMediaModal = (item) => {
  mediaModalError.value = ''
  editingMediaId.value = item.id
  mediaMode.value = item.source === 'upload' ? 'upload' : 'link'
  selectedFile.value = null
  editingOriginalSource.value = item.source
  mediaForm.value = {
    media_type: item.media_type,
    url: item.url,
    display_duration_seconds: item.display_duration_seconds,
    display_order: item.display_order,
  }
  showMediaModal.value = true
}

const performSaveMedia = async () => {
  mediaActionLoading.value = true
  mediaModalError.value = ''
  try {
    let payload = { ...mediaForm.value, source: mediaMode.value }

    if (mediaMode.value === 'upload' && selectedFile.value) {
      const uploadResult = await queueStore.uploadMediaFile(selectedFile.value)
      payload = { ...payload, url: uploadResult.url, media_type: uploadResult.media_type }
    }

    if (editingMediaId.value) {
      await queueStore.updateMediaItem(editingMediaId.value, payload)
    } else {
      await queueStore.createMediaItem(payload)
    }
    showMediaModal.value = false
  } catch (err) {
    const detail = err.response?.data?.detail
    mediaModalError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to save media item'
  } finally {
    mediaActionLoading.value = false
  }
}

const saveMedia = async () => {
  if (mediaMode.value === 'link' && !mediaForm.value.url) return
  if (mediaMode.value === 'upload' && editingOriginalSource.value !== 'upload' && !selectedFile.value) {
    mediaModalError.value = 'Please choose a file to upload.'
    return
  }
  mediaModalError.value = ''

  if (editingMediaId.value) {
    openConfirm({
      title: 'Save changes to this media item?',
      message: 'Confirm the updated details for this media playlist item.',
      confirmLabel: 'Yes, Save Changes',
      variant: 'primary',
      action: performSaveMedia,
    })
    return
  }

  await performSaveMedia()
}

const toggleMediaActive = async (item) => {
  mediaActionLoading.value = true
  mediaError.value = ''
  try {
    await queueStore.updateMediaItem(item.id, { is_active: !item.is_active })
  } catch (err) {
    mediaError.value = err.response?.data?.detail || 'Failed to update media item'
  } finally {
    mediaActionLoading.value = false
  }
}

const removeMediaItem = (itemId) => {
  openConfirm({
    title: 'Delete this media item?',
    message: 'This cannot be undone.',
    confirmLabel: 'Yes, Delete',
    variant: 'danger',
    action: async () => {
      mediaActionLoading.value = true
      mediaError.value = ''
      try {
        await queueStore.deleteMediaItem(itemId)
      } catch (err) {
        mediaError.value = err.response?.data?.detail || 'Failed to delete media item'
      } finally {
        mediaActionLoading.value = false
      }
    },
  })
}

// Announcement state
const announcementError = ref('')
const announcementModalError = ref('')
const announcementActionLoading = ref(false)
const showAnnouncementModal = ref(false)
const editingAnnouncementId = ref(null)
const announcementForm = ref({
  text: '',
  display_order: 0,
})

const openCreateAnnouncementModal = () => {
  announcementModalError.value = ''
  editingAnnouncementId.value = null
  announcementForm.value = { text: '', display_order: 0 }
  showAnnouncementModal.value = true
}

const openEditAnnouncementModal = (item) => {
  announcementModalError.value = ''
  editingAnnouncementId.value = item.id
  announcementForm.value = { text: item.text, display_order: item.display_order }
  showAnnouncementModal.value = true
}

const performSaveAnnouncement = async () => {
  announcementActionLoading.value = true
  announcementModalError.value = ''
  try {
    if (editingAnnouncementId.value) {
      await queueStore.updateAnnouncement(editingAnnouncementId.value, announcementForm.value)
    } else {
      await queueStore.createAnnouncement(announcementForm.value)
    }
    showAnnouncementModal.value = false
  } catch (err) {
    const detail = err.response?.data?.detail
    announcementModalError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to save announcement'
  } finally {
    announcementActionLoading.value = false
  }
}

const saveAnnouncement = async () => {
  if (!announcementForm.value.text) return
  announcementModalError.value = ''

  if (editingAnnouncementId.value) {
    openConfirm({
      title: 'Save changes to this announcement?',
      message: 'Confirm the updated announcement text before it goes live on the display boards.',
      confirmLabel: 'Yes, Save Changes',
      variant: 'primary',
      action: performSaveAnnouncement,
    })
    return
  }

  await performSaveAnnouncement()
}

const toggleAnnouncementActive = async (item) => {
  announcementActionLoading.value = true
  announcementError.value = ''
  try {
    await queueStore.updateAnnouncement(item.id, { is_active: !item.is_active })
  } catch (err) {
    announcementError.value = err.response?.data?.detail || 'Failed to update announcement'
  } finally {
    announcementActionLoading.value = false
  }
}

const removeAnnouncement = (itemId) => {
  openConfirm({
    title: 'Delete this announcement?',
    message: 'This cannot be undone.',
    confirmLabel: 'Yes, Delete',
    variant: 'danger',
    action: async () => {
      announcementActionLoading.value = true
      announcementError.value = ''
      try {
        await queueStore.deleteAnnouncement(itemId)
      } catch (err) {
        announcementError.value = err.response?.data?.detail || 'Failed to delete announcement'
      } finally {
        announcementActionLoading.value = false
      }
    },
  })
}

onMounted(async () => {
  try {
    await queueStore.fetchMediaItems()
  } catch (err) {
    mediaError.value = err.response?.data?.detail || 'Failed to load media items'
  }
  try {
    await queueStore.fetchAnnouncements()
  } catch (err) {
    announcementError.value = err.response?.data?.detail || 'Failed to load announcements'
  }
})
</script>
