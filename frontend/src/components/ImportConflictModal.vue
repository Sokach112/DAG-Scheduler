<template>
  <div v-if="conflict" class="fixed inset-0 bg-black/50 flex items-center justify-center z-[130] p-6">
    <div class="bg-white rounded-xl shadow-xl w-[480px] p-6">
      <h3 class="text-lg font-semibold text-gray-800">IDs already exist</h3>
      <p class="text-sm text-gray-600 mt-2">
        <template v-if="conflict.kind === 'workspace'">
          This workspace export contains IDs that already exist.
        </template>
        <template v-else>
          This project ID already exists.
        </template>
      </p>

      <div class="mt-4 bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs text-gray-600 space-y-1">
        <p v-if="duplicateWorkspaces.length">
          <strong>Workspace IDs:</strong> {{ duplicateWorkspaces.join(', ') }}
        </p>
        <p v-if="duplicateProjects.length">
          <strong>Project IDs ({{ duplicateProjects.length }}):</strong>
          {{ preview(duplicateProjects) }}
        </p>
      </div>

      <p class="text-xs text-gray-500 mt-3">
        <strong>Build new</strong> keeps IDs that are free and generates new IDs
        only for duplicates. <strong>Replace existing</strong> overwrites the
        existing records; for a workspace, its current projects are replaced.
      </p>

      <div class="flex flex-col gap-2 mt-5">
        <button @click="$emit('choose', 'new')" class="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
          Build new IDs
        </button>
        <button @click="$emit('choose', 'replace')" class="w-full px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700">
          Replace existing
        </button>
        <button @click="$emit('choose', 'cancel')" class="w-full px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">
          Cancel upload
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  conflict: any
}>()

defineEmits(['choose'])

const duplicateWorkspaces = computed(
  () => props.conflict?.duplicates?.workspace || [])
const duplicateProjects = computed(
  () => props.conflict?.duplicates?.projects || [])

const preview = (ids: string[]) => {
  if (ids.length <= 6) return ids.join(', ')
  return `${ids.slice(0, 6).join(', ')} +${ids.length - 6} more`
}
</script>
