<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-[110]">
    <div class="bg-white rounded-xl shadow-xl w-[560px] max-h-[85vh] flex flex-col">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <div>
          <h3 class="text-lg font-semibold text-gray-800">Saved checkpoints</h3>
          <p class="text-[11px] text-gray-400">Edits are auto-saved. Checkpoints are manual and keep the 10 most recent.</p>
        </div>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600">
          <span class="text-xl leading-none">×</span>
        </button>
      </div>

      <div class="p-4 overflow-y-auto flex flex-col gap-2">
        <p v-if="loading" class="text-xs text-gray-400 italic px-2 py-4">Loading checkpoints…</p>
        <p v-else-if="revisions.length === 0" class="text-xs text-gray-400 italic px-2 py-4">
          No checkpoints yet. Use the save icon or the button below.
        </p>

        <div
          v-for="revision in revisions"
          :key="revision.id"
          class="flex items-center justify-between gap-3 border border-gray-200 rounded-lg px-3 py-2"
        >
          <div class="min-w-0">
            <p class="text-xs font-medium text-gray-700 truncate">
              {{ revision.label || revision.title || 'Untitled checkpoint' }}
            </p>
            <p class="text-[10px] text-gray-400">
              {{ revision.title || 'Untitled Project' }} · {{ formatDate(revision.created_at) }} · {{ revision.event_count }} tasks
            </p>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button @click="openRename(revision)" class="p-1.5 text-gray-400 hover:text-blue-600" title="Rename checkpoint">
              <Pencil class="w-3.5 h-3.5" />
            </button>
            <button @click="deleteTarget = revision" class="p-1.5 text-gray-400 hover:text-red-500" title="Delete checkpoint">
              <Trash2 class="w-3.5 h-3.5" />
            </button>
            <button
              @click="$emit('restore', revision.id)"
              class="px-2.5 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-md hover:bg-blue-50"
            >
              Restore
            </button>
          </div>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-between items-center">
        <button @click="$emit('save')" class="px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
          Save current checkpoint
        </button>
        <button @click="$emit('close')" class="px-3 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">
          Close
        </button>
      </div>
    </div>

    <!-- Rename dialog -->
    <div v-if="renameTarget" class="fixed inset-0 bg-black/40 flex items-center justify-center z-[120]">
      <div class="bg-white rounded-xl shadow-xl w-[380px] p-5">
        <h4 class="text-sm font-semibold text-gray-800">Rename checkpoint</h4>
        <input
          ref="renameInput"
          v-model="renameDraft"
          @keyup.enter="submitRename"
          @keyup.esc="cancelRename"
          class="mt-3 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Checkpoint name"
        />
        <div class="flex justify-end gap-2 mt-4">
          <button @click="cancelRename" class="px-3 py-1.5 text-xs text-gray-600 bg-white border rounded-md">Cancel</button>
          <button @click="submitRename" class="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-md">Rename</button>
        </div>
      </div>
    </div>

    <!-- Delete dialog -->
    <div v-if="deleteTarget" class="fixed inset-0 bg-black/40 flex items-center justify-center z-[120]">
      <div class="bg-white rounded-xl shadow-xl w-[400px] p-5">
        <h4 class="text-sm font-semibold text-gray-800">Delete checkpoint?</h4>
        <p class="text-xs text-gray-500 mt-2">
          “{{ deleteTarget.label || deleteTarget.title || 'Untitled checkpoint' }}” will be permanently deleted.
        </p>
        <div class="flex justify-end gap-2 mt-4">
          <button @click="deleteTarget = null" class="px-3 py-1.5 text-xs text-gray-600 bg-white border rounded-md">Cancel</button>
          <button @click="confirmDelete" class="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded-md">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { Pencil, Trash2 } from 'lucide-vue-next'

defineProps<{
  isOpen: boolean
  revisions: any[]
  loading: boolean
}>()

const emit = defineEmits(['close', 'restore', 'rename', 'delete', 'save'])

const renameTarget = ref<any>(null)
const renameDraft = ref('')
const renameInput = ref<HTMLInputElement | null>(null)
const deleteTarget = ref<any>(null)

const openRename = async (revision: any) => {
  renameTarget.value = revision
  renameDraft.value = revision.label || revision.title || ''
  await nextTick()
  renameInput.value?.focus()
  renameInput.value?.select()
}

const submitRename = () => {
  const label = renameDraft.value.trim()
  if (!label) return
  emit('rename', { revision: renameTarget.value, label })
  renameTarget.value = null
}

const cancelRename = () => {
  renameTarget.value = null
}

const confirmDelete = () => {
  if (!deleteTarget.value) return
  emit('delete', deleteTarget.value)
  deleteTarget.value = null
}

const formatDate = (value: string) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
</script>
