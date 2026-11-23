<template>
  <div class="flex h-screen bg-[#f7f8fa] text-[#262626] font-sans">
    <Sidebar
      :workspaces="workspaces"
      :projects="workspaceProjects"
      :activeWorkspaceId="activeWorkspaceId"
      :activeProjectId="activeProjectId"
      @home="goHome"
      @select-workspace="selectWorkspace"
      @select-project="openProject"
      @new-workspace="openNewWorkspace"
      @edit-workspace="openEditWorkspace"
      @delete-workspace="deleteWorkspace"
      @new-project="openNewProject"
      @edit-project="openEditProjectFromSidebar"
      @delete-project="deleteProjectFromSidebar"
    />

    <div class="flex-1 flex flex-col overflow-hidden">
      <template v-if="activeProjectId">
        <header class="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-5 shrink-0 z-10">
          <div class="flex items-center gap-2 min-w-0">
            <button @click="goWorkspace" class="text-sm text-gray-500 hover:text-gray-800 flex items-center gap-1 shrink-0">
              <ChevronLeft class="w-4 h-4" />
              {{ activeWorkspace?.name || 'Workspace' }}
            </button>
            <span class="text-gray-300">/</span>
            <span class="font-semibold text-gray-800 truncate">{{ currentProject?.title || 'Project' }}</span>
            <button @click="openEditProject" class="text-gray-400 hover:text-blue-600 p-1 shrink-0" title="Edit project settings">
              <Edit2 class="w-4 h-4" />
            </button>
            <button v-if="workerMode === 'team'" @click="openTeamModal" class="text-xs text-gray-500 hover:text-blue-600 flex items-center gap-1 px-2 py-1 rounded hover:bg-blue-50 shrink-0" title="Edit team members">
              <Users class="w-3.5 h-3.5" />
              Edit team
            </button>
          </div>

          <div class="flex items-center gap-5 text-sm text-gray-500 shrink-0">
            <WorkerModeSelector
              v-model="workerMode"
              v-model:count="customWorkerCount"
              :workers="currentProject?.workers || []"
              :maxConcurrency="report?.max_concurrency"
              @change="runSchedule()"
            />
            <span>Makespan: <strong class="text-gray-900">{{ report?.makespan_human || '--' }}</strong></span>
            <span>Critical: <strong class="text-orange-500">{{ report?.critical_count || 0 }}</strong></span>
            <span>Overdue: <strong :class="report?.overdue_count > 0 ? 'text-red-500' : 'text-gray-900'">{{ report?.overdue_count || 0 }}</strong></span>
          </div>
        </header>

        <div
          v-if="workerMode === 'team' && currentProject && !(currentProject.workers && currentProject.workers.length)"
          class="bg-blue-50 border-b border-blue-100 px-5 py-2 text-xs text-blue-700 flex items-center justify-between shrink-0"
        >
          <span>Team mode is selected, but this project has no team members yet.</span>
          <button @click="openTeamModal" class="font-medium underline shrink-0 ml-3">Set up team</button>
        </div>

        <div class="flex flex-1 overflow-hidden">
          <TaskSidebar
            :tasks="tasks"
            @update:tasks="handleTasksUpdate"
            @edit="openEditModal"
            @open-new="openNewModal"
          />

          <section class="flex-1 flex flex-col bg-white overflow-hidden relative">
            <div class="flex items-center px-4 border-b border-gray-200 bg-white shrink-0 z-10">
              <button
                @click="activeTab = 'gantt'"
                :class="activeTab === 'gantt' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'"
                class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2"
              >
                <BarChart2 class="w-4 h-4" /> Gantt Graph
              </button>
              <button
                @click="activeTab = 'graph'"
                :class="activeTab === 'graph' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'"
                class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2"
              >
                <GitGraph class="w-4 h-4" /> Dependency Graph
              </button>
            </div>

            <div class="flex-1 relative overflow-hidden bg-[#f7f8fa]">
              <GanttView
                v-show="activeTab === 'gantt'"
                :ganttData="ganttData"
                :scheduledTasks="scheduledTasks"
                :effectiveWorkers="effectiveWorkers"
                :workerRows="workerRows"
                :capabilityFallbacks="capabilityFallbacks"
                :timeMarkers="timeMarkers"
                :globalSpan="globalSpan"
                :loading="loading"
              />
              <DependencyView
                v-show="activeTab === 'graph'"
                :mermaidCode="mermaidCode"
              />
            </div>
          </section>
        </div>
      </template>

      <template v-else-if="activeWorkspaceId">
        <DashboardView
          :key="activeWorkspaceId"
          :wsid="activeWorkspaceId"
          :workspaceName="activeWorkspace?.name"
          :projects="workspaceProjects"
          :workspaces="workspaces"
          @open="openProject"
          @changed="handleDashboardChanged"
          @error="globalError = $event"
        />
      </template>

      <HomeView
        v-else
        :workspaces="workspaces"
        @open="selectWorkspace"
        @new-workspace="openNewWorkspace"
      />
    </div>

    <div v-if="globalError" class="fixed top-3 right-3 z-[100] max-w-md flex items-start gap-2 bg-red-50 border border-red-200 text-red-600 text-xs px-3 py-2 rounded-lg shadow-lg">
      <span class="flex-1">{{ globalError }}</span>
      <button @click="globalError = ''" class="text-red-400 hover:text-red-600">×</button>
    </div>

    <TaskModal
      :isOpen="isModalOpen"
      :isEditing="isEditing"
      :initialData="editingTask"
      :tasks="tasks"
      :workers="currentProject?.workers || []"
      :workerMode="workerMode"
      :workerCount="workerMode === 'workers' ? customWorkerCount : 1"
      :projectOrigin="projectOrigin"
      :projectDdl="projectDdl"
      @close="isModalOpen = false"
      @save="saveTask"
      @delete="deleteTask"
    />

    <ProjectModal
      :isOpen="isProjectModalOpen"
      :isEditing="isEditingProject"
      :initialData="editingProjectData"
      :workspaces="workspaces"
      :wsid="activeWorkspaceId"
      @close="closeProjectModal"
      @save="handleProjectSave"
    />

    <TeamModal
      :isOpen="isTeamModalOpen"
      :workers="currentProject?.workers || []"
      @close="isTeamModalOpen = false"
      @save="saveTeam"
    />

    <WorkspaceModal
      :isOpen="isWorkspaceModalOpen"
      :isEditing="isEditingWorkspace"
      :initialData="editingWorkspaceData"
      @close="closeWorkspaceModal"
      @save="handleWorkspaceSave"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { BarChart2, ChevronLeft, Edit2, GitGraph, Users } from 'lucide-vue-next'

import Sidebar from './components/Sidebar.vue'
import DashboardView from './components/DashboardView.vue'
import HomeView from './components/HomeView.vue'
import TaskSidebar from './components/TaskSidebar.vue'
import TaskModal from './components/TaskModal.vue'
import ProjectModal from './components/ProjectModal.vue'
import TeamModal from './components/TeamModal.vue'
import WorkspaceModal from './components/WorkspaceModal.vue'
import GanttView from './components/GanttView.vue'
import DependencyView from './components/DependencyView.vue'
import WorkerModeSelector from './components/WorkerModeSelector.vue'

const workspaces = ref<any[]>([])
const workspaceProjects = ref<any[]>([])
const activeWorkspaceId = ref<string | null>(null)
const activeProjectId = ref<string | null>(null)
const currentProject = ref<any>(null)

const activeWorkspace = computed(() =>
  workspaces.value.find(w => w.wsid === activeWorkspaceId.value) || null
)
const projectOrigin = computed(() => currentProject.value?.origin || '')
const projectDdl = computed(() => currentProject.value?.ddl || '')

const tasks = ref<any[]>([])
const report = ref<any>(null)
const ganttData = ref<any[]>([])
const scheduledTasks = ref<any[]>([])
const mermaidCode = ref('')
const activeTab = ref('gantt')
const workerMode = ref('infinite')
const customWorkerCount = ref(2)
const workerRows = ref<any[]>([])
const capabilityFallbacks = ref<string[]>([])
const loading = ref(false)
const globalError = ref('')
const timeMarkers = ref<any[]>([])
const globalSpan = ref(0)

const isModalOpen = ref(false)
const isEditing = ref(false)
const editingTask = ref<any>(null)

const isProjectModalOpen = ref(false)
const isEditingProject = ref(false)
const editingProjectData = ref<any>(null)

const isTeamModalOpen = ref(false)

const isWorkspaceModalOpen = ref(false)
const isEditingWorkspace = ref(false)
const editingWorkspaceData = ref<any>(null)

let suppressTaskRun = false

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : String(error)

const readApiError = async (res: Response) => {
  try {
    const body = await res.json()
    const detail = body?.error?.detail
    if (typeof detail === 'string') return detail
    if (detail) return JSON.stringify(detail)
    return `Request failed (${res.status})`
  } catch {
    return `Request failed (${res.status})`
  }
}

const urlFor = (wsid: string | null, prid: string | null) => {
  const params = new URLSearchParams()
  if (wsid) params.set('wsid', wsid)
  if (prid) params.set('prid', prid)
  const query = params.toString()
  return query ? `/?${query}` : '/'
}

const pushUrl = () => {
  window.history.pushState(
    {}, '', urlFor(activeWorkspaceId.value, activeProjectId.value))
}

const createDefaultWorkspace = async () => {
  const res = await fetch('/api/workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'My Workspace', description: '' })
  })
  if (!res.ok) throw new Error(await readApiError(res))
  return await res.json()
}

const loadWorkspaces = async () => {
  const res = await fetch('/api/workspaces')
  if (!res.ok) throw new Error(await readApiError(res))
  workspaces.value = await res.json()
  if (workspaces.value.length === 0) {
    workspaces.value = [await createDefaultWorkspace()]
  }
}

const refreshWorkspaceProjects = async () => {
  if (!activeWorkspaceId.value) {
    workspaceProjects.value = []
    return
  }
  const res = await fetch(
    `/api/projects?wsid=${encodeURIComponent(activeWorkspaceId.value)}`)
  if (!res.ok) throw new Error(await readApiError(res))
  workspaceProjects.value = await res.json()
}

const openNewWorkspace = () => {
  isEditingWorkspace.value = false
  editingWorkspaceData.value = null
  isWorkspaceModalOpen.value = true
}

const openEditWorkspace = (workspace: any) => {
  isEditingWorkspace.value = true
  editingWorkspaceData.value = workspace
  isWorkspaceModalOpen.value = true
}

const closeWorkspaceModal = () => {
  isWorkspaceModalOpen.value = false
  editingWorkspaceData.value = null
}

const handleWorkspaceSave = async (data: any) => {
  const editing = isEditingWorkspace.value
  try {
    const res = await fetch(
      editing && editingWorkspaceData.value
        ? `/api/workspaces/${editingWorkspaceData.value.wsid}`
        : '/api/workspaces',
      {
        method: editing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      }
    )
    if (!res.ok) throw new Error(await readApiError(res))
    const saved = await res.json()

    closeWorkspaceModal()
    await loadWorkspaces()
    if (!editing) await selectWorkspace(saved.wsid)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const deleteWorkspace = async (workspace: any) => {
  if (!confirm(
    `Delete workspace "${workspace.name}" and all of its projects?`
  )) return

  try {
    const res = await fetch(`/api/workspaces/${workspace.wsid}`, {
      method: 'DELETE'
    })
    if (!res.ok && res.status !== 404) {
      throw new Error(await readApiError(res))
    }

    const wasActive = activeWorkspaceId.value === workspace.wsid
    await loadWorkspaces()

    if (wasActive) {
      await goHome()
    }
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const selectWorkspace = async (wsid: string) => {
  if (!wsid) return
  activeWorkspaceId.value = wsid
  activeProjectId.value = null
  currentProject.value = null
  tasks.value = []
  resetEditor()
  try {
    await refreshWorkspaceProjects()
    pushUrl()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const applyWorkerSettings = (project: any) => {
  let mode = project?.worker_mode
  if (mode === 'custom') {
    // Legacy mode: named custom projects were the old Team mode.
    mode = (project?.workers || []).length ? 'team' : 'workers'
  }
  const modes = ['infinite', '1', 'workers', 'team']
  workerMode.value = modes.includes(mode) ? mode : 'infinite'

  const count = Number(project?.worker_count)
  customWorkerCount.value = Number.isFinite(count) && count >= 1
    ? Math.floor(count)
    : 2
}

const applyProject = (project: any) => {
  currentProject.value = project
  activeProjectId.value = project.prid
  applyWorkerSettings(project)
}

const setTasksFromProject = async (events: any[]) => {
  suppressTaskRun = true
  try {
    tasks.value = events
    await nextTick()
  } finally {
    suppressTaskRun = false
  }
}

const openProject = async (prid: string, push = true) => {
  loading.value = true
  globalError.value = ''
  try {
    const res = await fetch(`/api/projects/${prid}`)
    if (!res.ok) throw new Error(await readApiError(res))
    const project = await res.json()

    if (project.wsid && project.wsid !== activeWorkspaceId.value) {
      activeWorkspaceId.value = project.wsid
      await refreshWorkspaceProjects()
    }

    applyProject(project)
    await setTasksFromProject(project.events || [])
    if (push) pushUrl()
    await runSchedule(false)
  } catch (error) {
    globalError.value = errorMessage(error)
    activeProjectId.value = null
    currentProject.value = null
    tasks.value = []
    resetEditor()
    if (push) pushUrl()
  } finally {
    loading.value = false
  }
}

const goWorkspace = () => {
  activeProjectId.value = null
  currentProject.value = null
  tasks.value = []
  resetEditor()
  pushUrl()
}

const goHome = async () => {
  activeWorkspaceId.value = null
  activeProjectId.value = null
  currentProject.value = null
  workspaceProjects.value = []
  tasks.value = []
  resetEditor()
  pushUrl()
  try {
    await loadWorkspaces()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const openNewProject = () => {
  if (!activeWorkspaceId.value) return
  isEditingProject.value = false
  editingProjectData.value = null
  isProjectModalOpen.value = true
}

const openEditProjectFromSidebar = (project: any) => {
  isEditingProject.value = true
  editingProjectData.value = project
  isProjectModalOpen.value = true
}

const openEditProject = () => {
  if (currentProject.value) openEditProjectFromSidebar(currentProject.value)
}

const closeProjectModal = () => {
  isProjectModalOpen.value = false
  editingProjectData.value = null
}

const openTeamModal = () => {
  if (workerMode.value !== 'team') return
  isTeamModalOpen.value = true
}

const saveTeam = async (workers: any[]) => {
  if (!activeProjectId.value) return
  try {
    const res = await fetch(`/api/projects/${activeProjectId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workers })
    })
    if (!res.ok) throw new Error(await readApiError(res))
    currentProject.value = await res.json()
    isTeamModalOpen.value = false
    await refreshWorkspaceProjects()
    await runSchedule(false)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const handleProjectSave = async (data: any) => {
  const editing = isEditingProject.value
  try {
    if (editing && editingProjectData.value) {
      const res = await fetch(
        `/api/projects/${editingProjectData.value.prid}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        }
      )
      if (!res.ok) throw new Error(await readApiError(res))
      const updated = await res.json()

      closeProjectModal()

      if (activeProjectId.value === updated.prid
          && updated.wsid !== activeWorkspaceId.value) {
        activeWorkspaceId.value = updated.wsid
      }

      await refreshWorkspaceProjects()
      await loadWorkspaces()

      if (activeProjectId.value === updated.prid) {
        currentProject.value = updated
        applyWorkerSettings(updated)
        pushUrl()
        await runSchedule(false)
      }
      return
    }

    if (!activeWorkspaceId.value) {
      throw new Error('Select a workspace before creating a project')
    }

    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...data,
        wsid: data.wsid || activeWorkspaceId.value,
        events: []
      })
    })
    if (!res.ok) throw new Error(await readApiError(res))
    const created = await res.json()

    closeProjectModal()
    await refreshWorkspaceProjects()
    await loadWorkspaces()
    await openProject(created.prid)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const deleteProjectFromSidebar = async (project: any) => {
  if (!confirm(`Delete project "${project.title}"?`)) return
  try {
    const res = await fetch(`/api/projects/${project.prid}`, {
      method: 'DELETE'
    })
    if (!res.ok && res.status !== 404) {
      throw new Error(await readApiError(res))
    }

    await refreshWorkspaceProjects()
    await loadWorkspaces()

    if (activeProjectId.value === project.prid) goWorkspace()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const handleDashboardChanged = async () => {
  try {
    await refreshWorkspaceProjects()
    await loadWorkspaces()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const loadFromUrl = async () => {
  globalError.value = ''
  try {
    await loadWorkspaces()

    const params = new URLSearchParams(window.location.search)
    const urlWsid = params.get('wsid')
    const validWsid = workspaces.value.some(w => w.wsid === urlWsid)
      ? urlWsid
      : null
    const prid = params.get('prid')

    activeWorkspaceId.value = null
    activeProjectId.value = null
    currentProject.value = null
    workspaceProjects.value = []
    tasks.value = []
    resetEditor()

    if (prid) {
      await openProject(prid, false)
    } else if (validWsid) {
      activeWorkspaceId.value = validWsid
      await refreshWorkspaceProjects()
    }

    window.history.replaceState(
      {}, '', urlFor(activeWorkspaceId.value, activeProjectId.value))
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

onMounted(() => {
  window.addEventListener('popstate', loadFromUrl)
  loadFromUrl()
})

onUnmounted(() => {
  window.removeEventListener('popstate', loadFromUrl)
})

const resetEditor = () => {
  report.value = null
  ganttData.value = []
  scheduledTasks.value = []
  workerRows.value = []
  capabilityFallbacks.value = []
  mermaidCode.value = ''
  timeMarkers.value = []
  globalSpan.value = 0
}

const saveProjectToServer = async () => {
  if (!activeProjectId.value) return null
  const res = await fetch(`/api/projects/${activeProjectId.value}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      events: tasks.value,
      worker_mode: workerMode.value,
      worker_count: customWorkerCount.value
    })
  })
  if (!res.ok) throw new Error(await readApiError(res))

  const updated = await res.json()
  currentProject.value = updated
  report.value = updated.report || null

  const index = workspaceProjects.value.findIndex(
    p => p.prid === updated.prid)
  if (index >= 0) {
    workspaceProjects.value[index] = {
      ...workspaceProjects.value[index],
      ...updated,
      event_count: updated.events?.length ?? 0,
      makespan: updated.report?.makespan ?? 0,
      makespan_human: updated.report?.makespan_human ?? ''
    }
  }
  return updated
}

const formatMinutes = (total: number) => {
  const sign = total < 0 ? '-' : ''
  const minutes = Math.abs(total)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h && m) return `${sign}${h}h ${m}m`
  if (h) return `${sign}${h}h`
  return `${sign}${m}m`
}

const runSchedule = async (persist = true) => {
  if (!activeProjectId.value) return
  loading.value = true
  globalError.value = ''

  try {
    if (persist) await saveProjectToServer()
    report.value = currentProject.value?.report || null

    const prid = activeProjectId.value
    const graphRes = await fetch(
      `/api/projects/${prid}/graph?format=mermaid`)
    if (!graphRes.ok) throw new Error(await readApiError(graphRes))
    mermaidCode.value = (await graphRes.json()).content

    capabilityFallbacks.value = []

    if (workerMode.value === 'infinite') {
      workerRows.value = []
      const ganttRes = await fetch(`/api/projects/${prid}/gantt`)
      if (!ganttRes.ok) throw new Error(await readApiError(ganttRes))
      const rawGantt = await ganttRes.json()
      scheduledTasks.value = []

      if (rawGantt.length === 0) {
        ganttData.value = []
        timeMarkers.value = []
        globalSpan.value = 0
        return
      }

      const originMs = Date.parse(currentProject.value?.origin || '')
      const ddlMs = Date.parse(currentProject.value?.ddl || '')
      const starts = rawGantt.map(
        (t: any) => new Date(t.start).getTime())
      const ends = rawGantt.map(
        (t: any) => new Date(t.end).getTime())
      const minTime = Number.isFinite(originMs)
        ? Math.min(originMs, ...starts)
        : Math.min(...starts)
      const maxTime = Number.isFinite(ddlMs)
        ? Math.max(ddlMs, ...ends)
        : Math.max(...ends)
      globalSpan.value = maxTime - minTime || 1

      ganttData.value = rawGantt.map((task: any) => {
        const tStart = new Date(task.start).getTime()
        const tEnd = new Date(task.end).getTime()
        return {
          id: task.eid,
          name: task.description,
          start: task.start,
          end: task.end,
          leftPct: ((tStart - minTime) / globalSpan.value) * 100,
          widthPct: Math.max(
            ((tEnd - tStart) / globalSpan.value) * 100, 1),
          custom_class: task.status === 'critical'
            ? 'bg-orange-400'
            : (task.status === 'overdue' ? 'bg-red-400' : 'bg-blue-500')
        }
      })

      const markerCount = 5
      const markers = []
      for (let i = 0; i < markerCount; i++) {
        const timeVal = minTime + (
          globalSpan.value * (i / (markerCount - 1)))
        markers.push({ time: new Date(timeVal).toISOString() })
      }
      timeMarkers.value = markers
      return
    }

    const roster = currentProject.value?.workers || []
    let workers = workerMode.value === 'workers'
      ? customWorkerCount.value
      : 1
    let activeIds: string[] | null = null

    if (workerMode.value === 'team') {
      if (!roster.length) {
        workerRows.value = []
        scheduledTasks.value = []
        ganttData.value = []
        timeMarkers.value = []
        globalSpan.value = 0
        capabilityFallbacks.value = []
        return
      }
      const teamIds = roster.map((worker: any) => worker.wid)
      activeIds = teamIds
      workers = teamIds.length
      workerRows.value = roster.map((worker: any) => ({
        id: worker.wid,
        name: worker.name
      }))
    } else {
      workerRows.value = Array.from(
        { length: workers }, (_, index) => ({
          id: index,
          name: `Worker ${index}`
        }))
    }

    const params = new URLSearchParams({ workers: String(workers) })
    if (activeIds?.length) {
      params.set('worker_ids', activeIds.join(','))
    }
    const schedRes = await fetch(
      `/api/projects/${prid}/schedule?${params.toString()}`)
    if (!schedRes.ok) throw new Error(await readApiError(schedRes))
    const schedData = await schedRes.json()
    capabilityFallbacks.value = schedData.capability_fallbacks || []

    const eids = Object.keys(schedData.start)
    ganttData.value = []
    if (eids.length === 0) {
      scheduledTasks.value = []
      timeMarkers.value = []
      globalSpan.value = 0
      return
    }

    const originMs = Date.parse(currentProject.value?.origin || '')
    const hasOrigin = Number.isFinite(originMs)
    const startTimes: Record<string, number> = {}
    const endTimes: Record<string, number> = {}
    eids.forEach(eid => {
      startTimes[eid] = (hasOrigin ? originMs : 0)
        + schedData.start[eid] * 60000
      endTimes[eid] = (hasOrigin ? originMs : 0)
        + schedData.end[eid] * 60000
    })

    const minT = Math.min(...eids.map(eid => startTimes[eid]))
    const maxT = Math.max(...eids.map(eid => endTimes[eid]))
    globalSpan.value = maxT - minT || 1

    const eventsByEid = new Map<string, any>(
      (currentProject.value?.events || []).map(
        (e: any) => [e.eid, e] as [string, any])
    )
    const statuses: Record<string, string> = {}

    scheduledTasks.value = eids.map(eid => {
      const s = startTimes[eid] - minT
      const e = endTimes[eid] - minT
      const info = schedData.tasks[eid]
        || { description: eid, status: 'normal' }

      let status = info.status
      if (hasOrigin) {
        const deadlineMs = Date.parse(
          eventsByEid.get(eid)?.deadline)
        if (Number.isFinite(deadlineMs)
            && endTimes[eid] > deadlineMs) {
          status = 'overdue'
        }
      }
      statuses[eid] = status

      return {
        id: eid,
        name: info.description,
        start: new Date(startTimes[eid]).toISOString(),
        end: new Date(endTimes[eid]).toISOString(),
        leftPct: (s / globalSpan.value) * 100,
        widthPct: Math.max(
          ((e - s) / globalSpan.value) * 100, 1),
        workerId: schedData.assignments[eid],
        custom_class: status === 'critical'
          ? 'bg-indigo-500'
          : (status === 'overdue' ? 'bg-red-500' : 'bg-emerald-500')
      }
    })

    const statusList = Object.values(statuses)
    report.value = {
      ...(currentProject.value?.report || {}),
      makespan: schedData.makespan,
      makespan_human: formatMinutes(schedData.makespan),
      critical_count: statusList.filter(
        s => s === 'critical').length,
      overdue_count: statusList.filter(
        s => s === 'overdue').length
    }

    const markerCount = 5
    const markers = []
    for (let i = 0; i < markerCount; i++) {
      const timeVal = minT + (
        globalSpan.value * (i / (markerCount - 1)))
      markers.push({ time: new Date(timeVal).toISOString() })
    }
    timeMarkers.value = markers
  } catch (error) {
    globalError.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

watch(tasks, () => {
  if (suppressTaskRun || !activeProjectId.value) return
  runSchedule()
}, { deep: true })

const effectiveWorkers = computed(() => {
  if (workerMode.value === 'infinite') return 'infinite'
  if (workerMode.value === '1') return '1'
  return customWorkerCount.value.toString()
})

const handleTasksUpdate = (newTasks: any[]) => {
  tasks.value = newTasks
}

const openNewModal = () => {
  isEditing.value = false
  editingTask.value = null
  isModalOpen.value = true
}

const openEditModal = (task: any) => {
  isEditing.value = true
  editingTask.value = task
  isModalOpen.value = true
}

const saveTask = (taskData: any) => {
  if (!taskData.eid) {
    let nextNum = tasks.value.length + 1
    let nextEid = `T${nextNum}`
    while (tasks.value.some(t => t.eid === nextEid)) {
      nextNum++
      nextEid = `T${nextNum}`
    }
    taskData.eid = nextEid
  }

  if (isEditing.value) {
    const idx = tasks.value.findIndex(t => t.eid === taskData.eid)
    if (idx !== -1) tasks.value[idx] = taskData
  } else {
    tasks.value.push(taskData)
  }
  isModalOpen.value = false
}

const deleteTask = (eid: string) => {
  tasks.value = tasks.value.filter(t => t.eid !== eid)
  isModalOpen.value = false
}
</script>
