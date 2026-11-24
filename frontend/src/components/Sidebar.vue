<template>
  <aside class="w-64 shrink-0 h-full bg-[#fbfbfc] border-r border-gray-200 flex flex-col">
    <!-- Brand / home -->
    <button
      @click="$emit('home')"
      class="h-14 px-4 flex items-center gap-2 border-b border-gray-200 hover:bg-gray-50 transition-colors text-left"
    >
      <div class="bg-blue-600 text-white p-1.5 rounded-md flex items-center justify-center">
        <Activity class="w-5 h-5" />
      </div>
      <span class="font-bold text-gray-800 tracking-tight">DAG Scheduler</span>
    </button>

    <div class="flex-1 overflow-y-auto px-2 py-3">
      <!-- Dashboard / home -->
      <button
        @click="$emit('home')"
        class="w-full flex items-center gap-2 px-2 py-2 mb-2 rounded-md text-sm transition-colors"
        :class="!activeWorkspaceId
          ? 'bg-blue-50 text-blue-700 font-medium'
          : 'text-gray-700 hover:bg-gray-100'"
      >
        <LayoutDashboard
          class="w-4 h-4 shrink-0"
          :class="!activeWorkspaceId ? 'text-blue-600' : 'text-gray-400'"
        />
        <span>Dashboard</span>
      </button>

      <!-- Workspaces header -->
      <div class="flex items-center justify-between px-2 mb-1">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
          Workspaces
        </span>
        <button
          @click="$emit('new-workspace')"
          class="p-0.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50"
          title="New workspace"
        >
          <Plus class="w-4 h-4" />
        </button>
      </div>

      <div v-if="workspaces.length === 0" class="px-2 py-3 text-xs text-gray-400 italic">
        No workspaces yet.
      </div>

      <div v-for="ws in workspaces" :key="ws.wsid" class="mb-0.5">
        <!-- Workspace row -->
        <div
          @click="$emit('select-workspace', ws.wsid)"
          @dragover.prevent="onWorkspaceDragOver(ws.wsid, $event)"
          @dragleave="onWorkspaceDragLeave(ws.wsid)"
          @drop.prevent="onWorkspaceDrop(ws.wsid)"
          class="group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors"
          :class="[
            ws.wsid === activeWorkspaceId
              ? 'bg-blue-50 text-blue-700 font-medium'
              : 'text-gray-700 hover:bg-gray-100',
            draggedProject && draggedProject.wsid !== ws.wsid && dragOverWsid === ws.wsid
              ? 'ring-2 ring-blue-400 bg-blue-100/60'
              : ''
          ]"
        >
          <Folder class="w-4 h-4 shrink-0" :class="ws.wsid === activeWorkspaceId ? 'text-blue-600' : 'text-gray-400'" />
          <span class="truncate flex-1">{{ ws.name }}</span>
          <span
            v-if="ws.project_count"
            class="text-[10px] text-gray-400 shrink-0"
          >{{ ws.project_count }}</span>
          <span class="hidden group-hover:flex items-center gap-0.5 shrink-0">
            <button
              @click.stop="$emit('edit-workspace', ws)"
              class="p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-white"
              title="Rename workspace"
            >
              <Edit2 class="w-3.5 h-3.5" />
            </button>
            <button
              @click.stop="$emit('delete-workspace', ws)"
              class="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-white"
              title="Delete workspace"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </span>
        </div>

        <!-- Projects nested under the active workspace -->
        <div v-if="ws.wsid === activeWorkspaceId" class="ml-4 mt-0.5 border-l border-gray-200 pl-2">
          <div class="flex items-center justify-between px-2 py-1">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Projects
            </span>
            <button
              @click.stop="$emit('new-project')"
              class="p-0.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50"
              title="New project"
            >
              <Plus class="w-3.5 h-3.5" />
            </button>
          </div>

          <div v-if="projects.length === 0" class="px-2 py-1.5 text-xs text-gray-400 italic">
            No projects
          </div>

          <div
            v-for="p in projects"
            :key="p.prid"
            @click="$emit('select-project', p.prid)"
            draggable="true"
            @dragstart.stop="onProjectDragStart(p, $event)"
            @dragend="onProjectDragEnd"
            title="Drag onto another workspace to move"
            class="group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-grab active:cursor-grabbing text-sm transition-colors"
            :class="p.prid === activeProjectId
              ? 'bg-white text-gray-900 font-medium shadow-sm border border-gray-200'
              : 'text-gray-600 hover:bg-gray-100'"
          >
            <FileText class="w-4 h-4 shrink-0" :class="p.prid === activeProjectId ? 'text-blue-500' : 'text-gray-400'" />
            <span class="truncate flex-1">{{ p.title }}</span>
            <span class="hidden group-hover:flex items-center gap-0.5 shrink-0">
              <button
                @click.stop="$emit('edit-project', p)"
                class="p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-white"
                title="Rename project"
              >
                <Edit2 class="w-3.5 h-3.5" />
              </button>
              <button
                @click.stop="$emit('delete-project', p)"
                class="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-white"
                title="Delete project"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="px-3 py-3 border-t border-gray-200">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-semibold shrink-0">
          {{ (user?.display_name || user?.username || '?').slice(0, 1).toUpperCase() }}
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-xs font-medium text-gray-700 truncate">{{ user?.display_name || user?.username }}</p>
          <p class="text-[10px] text-gray-400 truncate">
            {{ user?.is_admin ? 'Administrator' : '@' + (user?.username || '') }}
          </p>
        </div>
        <button
          v-if="user?.is_admin"
          @click="$emit('manage-users')"
          class="p-1.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50"
          title="Manage users"
        >
          <Users class="w-4 h-4" />
        </button>
        <button
          @click="$emit('logout')"
          class="p-1.5 rounded text-gray-400 hover:text-red-500 hover:bg-red-50"
          title="Sign out"
        >
          <LogOut class="w-4 h-4" />
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Activity, Edit2, FileText, Folder, LayoutDashboard, LogOut, Plus, Trash2, Users } from 'lucide-vue-next'

const emit = defineEmits([
  'home',
  'select-workspace',
  'select-project',
  'new-workspace',
  'edit-workspace',
  'delete-workspace',
  'new-project',
  'edit-project',
  'delete-project',
  'move-project',
  'logout',
  'manage-users',
])

const draggedProject = ref<any>(null)
const dragOverWsid = ref<string | null>(null)

const onProjectDragStart = (project: any, event: DragEvent) => {
  draggedProject.value = project
  dragOverWsid.value = null
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', project.prid)
  }
}

const onProjectDragEnd = () => {
  draggedProject.value = null
  dragOverWsid.value = null
}

const onWorkspaceDragOver = (wsid: string, event: DragEvent) => {
  if (!draggedProject.value || draggedProject.value.wsid === wsid) return
  dragOverWsid.value = wsid
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

const onWorkspaceDragLeave = (wsid: string) => {
  if (dragOverWsid.value === wsid) dragOverWsid.value = null
}

const onWorkspaceDrop = (wsid: string) => {
  const project = draggedProject.value
  dragOverWsid.value = null
  draggedProject.value = null
  if (project && project.wsid !== wsid) {
    emit('move-project', { prid: project.prid, wsid })
  }
}

defineProps<{
  workspaces: any[]
  projects: any[]
  activeWorkspaceId: string | null
  activeProjectId: string | null
  user: any
}>()

</script>
