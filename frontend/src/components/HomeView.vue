<template>
  <div class="flex-1 bg-[#f7f8fa] overflow-y-auto h-full">
    <div class="max-w-6xl w-full mx-auto p-10">
      <div class="flex justify-between items-end mb-8">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">Workspaces</h1>
          <p class="text-sm text-gray-500 mt-1">
            Choose a workspace to open its projects, or create a new one.
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="fileInput?.click()"
            class="flex items-center gap-2 bg-white text-gray-700 border border-gray-300 px-4 py-2 rounded-lg hover:bg-gray-50 transition shadow-sm font-medium"
          >
            <Upload class="w-4 h-4" /> Import Workspace
          </button>
          <input ref="fileInput" type="file" accept=".zip,application/zip" class="hidden" @change="onFile" />
          <button
            @click="$emit('new-workspace')"
            class="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition shadow-sm font-medium"
          >
            <Plus class="w-5 h-5" /> New Workspace
          </button>
        </div>
      </div>

      <div v-if="workspaces.length === 0" class="flex flex-col items-center justify-center py-32 text-gray-400">
        <FolderOpen class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium">No workspaces yet</p>
        <p class="text-sm mt-1">Create a workspace to get started.</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <button
          v-for="workspace in workspaces"
          :key="workspace.wsid"
          @click="$emit('open', workspace.wsid)"
          class="group text-left bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:border-blue-300 hover:shadow-md transition-all"
        >
          <div class="flex items-start justify-between mb-4">
            <div class="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <FolderKanban class="w-5 h-5" />
            </div>
            <span class="text-[11px] text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
              {{ workspace.project_count || 0 }}
              {{ (workspace.project_count || 0) === 1 ? 'project' : 'projects' }}
            </span>
          </div>

          <h2 class="font-semibold text-gray-800 truncate">{{ workspace.name }}</h2>
          <p class="text-xs text-gray-500 mt-1 line-clamp-2 min-h-[2rem]">
            {{ workspace.description || 'No description yet.' }}
          </p>

          <div class="flex items-center gap-1 text-xs font-medium text-blue-600 mt-5 group-hover:gap-2 transition-all">
            Open workspace
            <ArrowRight class="w-3.5 h-3.5" />
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowRight, FolderKanban, FolderOpen, Plus, Upload } from 'lucide-vue-next'

defineProps<{
  workspaces: any[]
}>()

const emit = defineEmits(['open', 'new-workspace', 'import-workspace'])
const fileInput = ref<HTMLInputElement | null>(null)

const onFile = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('import-workspace', file)
  input.value = ''
}
</script>
