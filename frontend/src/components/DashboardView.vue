<template>
  <div class="flex-1 bg-[#f7f8fa] overflow-y-auto h-full flex flex-col">
    <div class="max-w-6xl w-full mx-auto p-10 flex-1">
      
      <!-- Top Navigator -->
      <div class="flex justify-between items-end mb-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">{{ workspaceName || 'My Projects' }}</h1>
          <p class="text-sm text-gray-500 mt-1">Projects in this workspace.</p>
        </div>
        
        <div class="flex items-center gap-3">
          <!-- Multiselect -->
          <button 
            v-if="selectedPrIds.length > 0"
            @click="batchDelete"
            class="flex items-center gap-1.5 bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Trash2 class="w-4 h-4" /> Delete ({{ selectedPrIds.length }})
          </button>

          <button @click="openNewProject" class="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition shadow-sm font-medium">
            <Plus class="w-5 h-5" /> New Project
          </button>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="projects.length === 0" class="flex flex-col items-center justify-center py-32 text-gray-400">
        <FolderOpen class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium">No projects yet</p>
        <p class="text-sm mt-1">Click "New Project" to create one in this workspace.</p>
      </div>

      <!-- List View -->
      <div v-else class="bg-white border border-gray-200 rounded-xl shadow-sm">
        <!-- List head -->
        <div class="flex items-center gap-4 px-6 py-3 bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-500 uppercase tracking-wider">
          <div class="w-8 flex justify-center">
            <input 
              type="checkbox" 
              :checked="isAllSelected" 
              @change="toggleSelectAll"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
            />
          </div>
          <div class="flex-1">Project Name</div>
          <div class="w-48 hidden md:block">Description</div>
          <div class="w-32 text-right">Last Updated</div>
          <div class="w-20 text-right">Actions</div>
        </div>

        <!-- List rows -->
        <div 
          v-for="p in projects" 
          :key="p.prid"
          class="flex items-center gap-4 px-6 py-4 border-b border-gray-100 hover:bg-blue-50/30 transition-colors group cursor-pointer"
          :class="selectedPrIds.includes(p.prid) ? 'bg-blue-50/50' : ''"
          @click="$emit('open', p.prid)"
        >

          <div class="w-8 flex justify-center" @click.stop>
            <input 
              type="checkbox" 
              :value="p.prid"
              :checked="selectedPrIds.includes(p.prid)"
              @change="toggleSelect(p.prid)"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
            />
          </div>

          <!-- Icon, title, and workspace move control -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 bg-blue-100 text-blue-600 rounded flex items-center justify-center shrink-0">
                <Layers class="w-4 h-4" />
              </div>
              <span class="font-semibold text-gray-800 truncate">{{ p.title }}</span>
            </div>
            <div class="mt-1.5 ml-11" @click.stop>
              <WorkspacePicker
                :wsid="p.wsid"
                :workspaces="workspaces"
                @move="(wsid: string) => moveProject(p, wsid)"
              />
            </div>
          </div>

          <!-- Description -->
          <div class="w-48 text-sm text-gray-500 truncate hidden md:block">
            {{ p.description || '-' }}
          </div>

          <!-- Update time -->
            <div class="w-40 text-right text-xs text-gray-400 font-mono whitespace-nowrap">
            {{ formatDate(p.updated_at) }}
            </div>

          <!-- Operation buttons -->
          <div class="w-20 text-right flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button @click.stop="renameProject(p)" class="text-gray-400 hover:text-blue-600 p-1" title="Rename">
              <Edit2 class="w-4 h-4" />
            </button>
            <button @click.stop="deleteProject(p.prid)" class="text-gray-400 hover:text-red-600 p-1" title="Delete">
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Project create -->
    <ProjectModal 
      :isOpen="isModalOpen" 
      :isEditing="isEditing"
      :initialData="editingProject"
      :workspaces="workspaces"
      :wsid="props.wsid"
      @close="isModalOpen = false" 
      @save="handleSave" 
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, Layers, FolderOpen, Trash2, Edit2 } from 'lucide-vue-next'
import ProjectModal from './ProjectModal.vue'
import WorkspacePicker from './WorkspacePicker.vue'

const props = defineProps<{
  wsid: string | null
  workspaceName?: string
  projects: any[]
  workspaces: any[]
}>()

const emit = defineEmits(['open', 'changed', 'error', 'conflict'])

// --- Prompt state management ---
const isModalOpen = ref(false)
const isEditing = ref(false)
const editingProject = ref<any>(null)

// --- Multiselect logic ---
const selectedPrIds = ref<string[]>([])
const isAllSelected = computed(() => props.projects.length > 0 && selectedPrIds.value.length === props.projects.length)

const toggleSelectAll = () => {
  selectedPrIds.value = isAllSelected.value ? [] : props.projects.map(p => p.prid)
}
const toggleSelect = (prid: string) => {
  const idx = selectedPrIds.value.indexOf(prid)
  idx > -1 ? selectedPrIds.value.splice(idx, 1) : selectedPrIds.value.push(prid)
}
const batchDelete = async () => {
  if (!confirm(`Delete ${selectedPrIds.value.length} projects?`)) return
  for (const prid of selectedPrIds.value) {
    await fetch(`/api/projects/${prid}`, { method: 'DELETE' })
  }
  selectedPrIds.value = []
  emit('changed')
}

const moveProject = async (project: any, targetWsid: string) => {
  if (!targetWsid || targetWsid === project.wsid) return
  try {
    const res = await fetch(`/api/projects/${project.prid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wsid: targetWsid,
        version: project.version
      })
    })
    if (res.status === 409) {
      emit('conflict', { prid: project.prid, title: project.title })
      return
    }
    if (!res.ok) {
      let message = `Request failed (${res.status})`
      try {
        const body = await res.json()
        if (typeof body?.error?.detail === 'string') {
          message = body.error.detail
        }
      } catch { /* keep default */ }
      throw new Error(message)
    }
    selectedPrIds.value = selectedPrIds.value.filter(
      id => id !== project.prid)
    emit('changed')
  } catch (err) {
    emit('error', err instanceof Error ? err.message : String(err))
  }
}

const formatDate = (isoStr: string | null) => {
  if (!isoStr) return 'Unknown'
  const date = new Date(isoStr)
  if (isNaN(date.getTime())) return 'Invalid Date'
  
  return date.toLocaleString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric',
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false
  })
}

// --- Prompt control ---
const openNewProject = () => {
  isEditing.value = false
  editingProject.value = null
  isModalOpen.value = true
}

const renameProject = (p: any) => {
  isEditing.value = true
  editingProject.value = p
  isModalOpen.value = true
}

const handleSave = async (data: any) => {
  if (isEditing.value) {
    // Update projects (PUT)
    const res = await fetch(`/api/projects/${editingProject.value.prid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...data,
        version: editingProject.value.version
      })
    })
    if (res.status === 409) {
      isModalOpen.value = false
      emit('conflict', {
        prid: editingProject.value.prid,
        title: editingProject.value.title
      })
      return
    }
    if (!res.ok) {
      emit('error', await res.text())
      return
    }
  } else {
    // Create projects (POST)
    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...data, wsid: data.wsid || props.wsid })
    })
    if (!res.ok) {
      emit('error', await res.text())
      return
    }
  }
  isModalOpen.value = false
  emit('changed')
}

const deleteProject = async (prid: string) => {
  if (!confirm("Are you sure you want to delete this project?")) return
  await fetch(`/api/projects/${prid}`, { method: 'DELETE' })
  selectedPrIds.value = selectedPrIds.value.filter(id => id !== prid)
  emit('changed')
}
</script>