<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-gray-900">Media & Announcements</h2>
      <p class="mt-2 text-gray-600">Manage the media playlist and announcement ticker shown on display boards</p>
    </div>

    <!-- Media Section -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 mb-8">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
        <h3 class="text-xl font-bold text-gray-900">Media Playlist</h3>
        <button
          @click="openCreateMediaModal"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
        >
          Add Media Item
        </button>
      </div>
      <div class="p-6">
        <div v-if="mediaError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p class="text-sm text-red-700">{{ mediaError }}</p>
        </div>

        <div class="overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">URL</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="item in queueStore.mediaItems" :key="item.id">
                <td class="px-4 py-4 text-sm text-gray-900 capitalize">{{ item.media_type }}</td>
                <td class="px-4 py-4 text-sm text-gray-500 max-w-xs truncate">{{ item.url }}</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_duration_seconds }}s</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_order }}</td>
                <td class="px-4 py-4">
                  <StatusBadge :status="item.is_active ? 'active' : 'inactive'" />
                </td>
                <td class="px-4 py-4 text-right space-x-2 whitespace-nowrap">
                  <button
                    @click="toggleMediaActive(item)"
                    :disabled="mediaActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
                  >
                    {{ item.is_active ? 'Deactivate' : 'Activate' }}
                  </button>
                  <button
                    @click="openEditMediaModal(item)"
                    :disabled="mediaActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200 disabled:opacity-50"
                  >
                    Edit
                  </button>
                  <button
                    @click="removeMediaItem(item.id)"
                    :disabled="mediaActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
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
    <div class="bg-white rounded-xl shadow-sm border border-gray-100">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
        <h3 class="text-xl font-bold text-gray-900">Announcements</h3>
        <button
          @click="openCreateAnnouncementModal"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
        >
          Add Announcement
        </button>
      </div>
      <div class="p-6">
        <div v-if="announcementError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p class="text-sm text-red-700">{{ announcementError }}</p>
        </div>

        <div class="overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Text</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="item in queueStore.announcements" :key="item.id">
                <td class="px-4 py-4 text-sm text-gray-900 max-w-md truncate">{{ item.text }}</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_order }}</td>
                <td class="px-4 py-4">
                  <StatusBadge :status="item.is_active ? 'active' : 'inactive'" />
                </td>
                <td class="px-4 py-4 text-right space-x-2 whitespace-nowrap">
                  <button
                    @click="toggleAnnouncementActive(item)"
                    :disabled="announcementActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
                  >
                    {{ item.is_active ? 'Deactivate' : 'Activate' }}
                  </button>
                  <button
                    @click="openEditAnnouncementModal(item)"
                    :disabled="announcementActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200 disabled:opacity-50"
                  >
                    Edit
                  </button>
                  <button
                    @click="removeAnnouncement(item.id)"
                    :disabled="announcementActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
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
    <div v-if="showMediaModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">{{ editingMediaId ? 'Edit Media Item' : 'Add Media Item' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              v-model="mediaForm.media_type"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            >
              <option value="image">Image</option>
              <option value="video">Video (embeddable URL, e.g. YouTube /embed/ link)</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">URL</label>
            <input
              v-model="mediaForm.url"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="https://..."
            />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Duration (seconds)</label>
              <input
                v-model.number="mediaForm.display_duration_seconds"
                type="number"
                min="1"
                max="300"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Order</label>
              <input
                v-model.number="mediaForm.display_order"
                type="number"
                min="0"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
          </div>
          <div v-if="mediaModalError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ mediaModalError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showMediaModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="saveMedia"
            :disabled="mediaActionLoading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            {{ editingMediaId ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Announcement Modal -->
    <div v-if="showAnnouncementModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">{{ editingAnnouncementId ? 'Edit Announcement' : 'Add Announcement' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Text</label>
            <textarea
              v-model="announcementForm.text"
              rows="3"
              maxlength="500"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="e.g., Enrollment for AY 2026-2027 is now open"
            ></textarea>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Order</label>
            <input
              v-model.number="announcementForm.display_order"
              type="number"
              min="0"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            />
          </div>
          <div v-if="announcementModalError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ announcementModalError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showAnnouncementModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="saveAnnouncement"
            :disabled="announcementActionLoading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            {{ editingAnnouncementId ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'

const queueStore = useQueueStore()

// Media state
const mediaError = ref('')
const mediaModalError = ref('')
const mediaActionLoading = ref(false)
const showMediaModal = ref(false)
const editingMediaId = ref(null)
const mediaForm = ref({
  media_type: 'image',
  url: '',
  display_duration_seconds: 10,
  display_order: 0,
})

const openCreateMediaModal = () => {
  mediaModalError.value = ''
  editingMediaId.value = null
  mediaForm.value = { media_type: 'image', url: '', display_duration_seconds: 10, display_order: 0 }
  showMediaModal.value = true
}

const openEditMediaModal = (item) => {
  mediaModalError.value = ''
  editingMediaId.value = item.id
  mediaForm.value = {
    media_type: item.media_type,
    url: item.url,
    display_duration_seconds: item.display_duration_seconds,
    display_order: item.display_order,
  }
  showMediaModal.value = true
}

const saveMedia = async () => {
  if (!mediaForm.value.url) return

  mediaActionLoading.value = true
  mediaModalError.value = ''
  try {
    if (editingMediaId.value) {
      await queueStore.updateMediaItem(editingMediaId.value, mediaForm.value)
    } else {
      await queueStore.createMediaItem(mediaForm.value)
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

const removeMediaItem = async (itemId) => {
  if (!confirm('Delete this media item? This cannot be undone.')) return
  mediaActionLoading.value = true
  mediaError.value = ''
  try {
    await queueStore.deleteMediaItem(itemId)
  } catch (err) {
    mediaError.value = err.response?.data?.detail || 'Failed to delete media item'
  } finally {
    mediaActionLoading.value = false
  }
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

const saveAnnouncement = async () => {
  if (!announcementForm.value.text) return

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

const removeAnnouncement = async (itemId) => {
  if (!confirm('Delete this announcement? This cannot be undone.')) return
  announcementActionLoading.value = true
  announcementError.value = ''
  try {
    await queueStore.deleteAnnouncement(itemId)
  } catch (err) {
    announcementError.value = err.response?.data?.detail || 'Failed to delete announcement'
  } finally {
    announcementActionLoading.value = false
  }
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
