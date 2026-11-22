<template>
  <div class="flex-1 p-10 bg-[#f7f8fa] overflow-y-auto h-full">
    <div class="max-w-6xl mx-auto">
      <div class="flex justify-between items-center mb-8">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">My Projects</h1>
          <p class="text-sm text-gray-500 mt-1">Select a project to start scheduling or create a new one.</p>
        </div>
        <button @click="createProject" class="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition shadow-sm">
          <Plus class="w-5 h-5" /> New Project
        </button>
      </div>

      <div v-if="projects.length === 0" class="text-center text-gray-400 mt-20">
        <FolderOpen class="w-16 h-16 mx-auto mb-4 opacity-30" />
        <p>No projects yet. Click "New Project" to get started.</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div 
          v-for="p in projects" 
          :key="p.prid"
          class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition group cursor-pointer overflow-hidden flex flex-col"
        >
          <div @click="$emit('open', p.prid)" class="p-6 flex-1">
            <div class="w-10 h-10 bg-blue-50 text-blue-600 rounded-lg flex items-center justify-center mb-4">
              <Layers class="w-5 h-5" />
            </div>
            <h3 class="text-lg font-semibold text-gray-800 truncate">{{ p.title }}</h3>
            <p class="text-sm text-gray-500 mt-1 line-clamp-2">{{ p.description || 'No description' }}</p>
          </div>
          
          <div class="px-6 py-3 bg-gray-50 border-t border-gray-100 flex justify-between items-center opacity-0 group-hover:opacity-100 transition-opacity">
            <span class="text-[11px] text-gray-400">Updated: {{ new Date(p.updated_at).toLocaleDateString() }}</span>
            <div class="flex gap-3">
              <button @click.stop="renameProject(p)" class="text-xs text-gray-500 hover:text-blue-600 font-medium">Rename</button>
              <button @click.stop="deleteProject(p.prid)" class="text-xs text-red-500 hover:text-red-700 font-medium">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Layers, FolderOpen } from 'lucide-vue-next'

const projects = ref<any[]>([])
const emit = defineEmits(['open'])

const fetchProjects = async () => {
  try {
    const res = await fetch('/api/projects')
    projects.value = await res.json()
  } catch (e) {
    console.error("Failed to fetch projects")
  }
}

const createProject = async () => {
  const title = prompt("Enter project title:", "New Project")
  if (!title) return
  
  await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description: "A new DAG project" })
  })
  fetchProjects()
}

const renameProject = async (p: any) => {
  const newName = prompt("Rename project:", p.title)
  if (!newName || newName === p.title) return
  
  await fetch(`/api/projects/${p.prid}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: newName })
  })
  fetchProjects()
}

const deleteProject = async (prid: string) => {
  if (!confirm("Are you sure you want to delete this project? This action cannot be undone.")) return
  
  await fetch(`/api/projects/${prid}`, { method: 'DELETE' })
  fetchProjects()
}

onMounted(fetchProjects)
</script>