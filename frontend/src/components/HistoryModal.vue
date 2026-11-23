<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-[110]">
    <div class="bg-white rounded-xl shadow-xl w-[560px] max-h-[85vh] flex flex-col">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <div>
          <h3 class="text-lg font-semibold text-gray-800">Revision history</h3>
          <p class="text-[11px] text-gray-400">Restore a previous version; restoring creates a new version.</p>
        </div>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600">
          <span class="text-xl leading-none">×</span>
        </button>
      </div>

      <div class="p-4 overflow-y-auto flex flex-col gap-2">
        <p v-if="loading" class="text-xs text-gray-400 italic px-2 py-4">Loading revisions…</p>
        <p v-else-if="revisions.length === 0" class="text-xs text-gray-400 italic px-2 py-4">
          No revisions yet.
        </p>

        <div
          v-for="revision in revisions"
          :key="revision.version"
          class="flex items-center justify-between gap-3 border border-gray-200 rounded-lg px-3 py-2"
        >
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-xs font-semibold text-gray-700">v{{ revision.version }}</span>
              <span v-if="revision.version === currentVersion" class="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">current</span>
            </div>
            <p class="text-xs font-medium text-gray-700 truncate">{{ revision.label || revision.title || 'Untitled version' }}</p>
            <p class="text-[10px] text-gray-400">
              {{ revision.title || 'Untitled Project' }} · {{ formatDate(revision.created_at) }} · {{ revision.event_count }} tasks
            </p>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button @click="$emit('rename', revision)" class="p-1.5 text-gray-400 hover:text-blue-600" title="Rename version">
              <Pencil class="w-3.5 h-3.5" />
            </button>
            <button @click="$emit('delete', revision)" class="p-1.5 text-gray-400 hover:text-red-500" title="Delete version">
              <Trash2 class="w-3.5 h-3.5" />
            </button>
            <button
              v-if="revision.version !== currentVersion"
              @click="$emit('restore', revision.version)"
              class="px-2.5 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-md hover:bg-blue-50"
            >
              Restore
            </button>
          </div>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-between items-center">
        <button @click="$emit('save')" class="px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
          Save current version
        </button>
        <button @click="$emit('close')" class="px-3 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Pencil, Trash2 } from 'lucide-vue-next'

defineProps<{
  isOpen: boolean
  revisions: any[]
  loading: boolean
  currentVersion: number
}>()

defineEmits(['close', 'restore', 'rename', 'delete', 'save'])

const formatDate = (value: string) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
</script>
