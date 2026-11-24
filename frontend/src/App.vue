<template>
  <div v-if="!authChecked" class="min-h-screen bg-[#f7f8fa] flex items-center justify-center text-sm text-gray-400">
    Loading…
  </div>
  <AuthView
    v-else-if="!authUser"
    :needsSetup="needsSetup"
    :loading="authLoading"
    :error="authError"
    @submit="handleAuthSubmit"
  />
  <div v-else class="flex h-screen bg-[#f7f8fa] text-[#262626] font-sans">
    <Sidebar
      :workspaces="workspaces"
      :projects="workspaceProjects"
      :activeWorkspaceId="activeWorkspaceId"
      :activeProjectId="activeProjectId"
      :user="authUser"
      @home="goHome"
      @logout="logout"
      @manage-users="isAdminUsersOpen = true"
      @select-workspace="selectWorkspace"
      @select-project="openProject"
      @new-workspace="openNewWorkspace"
      @edit-workspace="openEditWorkspace"
      @delete-workspace="deleteWorkspace"
      @new-project="openNewProject"
      @edit-project="openEditProjectFromSidebar"
      @delete-project="deleteProjectFromSidebar"
      @move-project="moveProjectToWorkspace"
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
            <button
              @click="undoEdit"
              :disabled="undoStack.length === 0"
              class="p-1 shrink-0 rounded"
              :class="undoStack.length ? 'text-gray-400 hover:text-blue-600' : 'text-gray-200 cursor-not-allowed'"
              title="Undo edit"
            >
              <ArrowLeft class="w-4 h-4" />
            </button>
            <button
              @click="redoEdit"
              :disabled="redoStack.length === 0"
              class="p-1 shrink-0 rounded"
              :class="redoStack.length ? 'text-gray-400 hover:text-blue-600' : 'text-gray-200 cursor-not-allowed'"
              title="Redo edit"
            >
              <ArrowRight class="w-4 h-4" />
            </button>
            <button @click="saveVersion" class="text-gray-400 hover:text-blue-600 p-1 shrink-0" title="Save version">
              <Save class="w-4 h-4" />
            </button>
            <button @click="openHistory" class="text-gray-400 hover:text-blue-600 p-1 shrink-0" title="Checkpoints">
              <History class="w-4 h-4" />
            </button>
            <button @click="exportProject" class="text-gray-400 hover:text-blue-600 p-1 shrink-0" title="Export project JSON">
              <Download class="w-4 h-4" />
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
              :activeIds="activeWorkerIds"
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

        <div
          v-if="report?.project_overdue"
          class="border-b px-5 py-2 text-xs flex items-center gap-2 shrink-0"
          :class="report.deadline_mode === 'hard'
            ? 'bg-red-50 border-red-100 text-red-600'
            : 'bg-amber-50 border-amber-100 text-amber-700'"
        >
          <span class="font-medium">
            {{ report.deadline_mode === 'hard'
              ? 'Hard deadline violated'
              : 'Project deadline exceeded' }}
          </span>
          <span>by {{ report.project_late_human }}</span>
          <span v-if="report.deadline_mode === 'hard'" class="font-medium">— no feasible schedule</span>
        </div>

        <div
          v-if="holidayCoverageWarning"
          class="bg-amber-50 border-b border-amber-100 px-5 py-2 text-xs text-amber-700 shrink-0"
        >
          {{ holidayCoverageWarning }}
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
          :workspaceRole="activeWorkspace?.role"
          :projects="workspaceProjects"
          :workspaces="workspaces"
          @open="openProject"
          @changed="handleDashboardChanged"
          @conflict="onProjectConflict"
          @import-project="importProjectFile"
          @error="globalError = $event"
        />
      </template>

      <HomeView
        v-else
        :workspaces="workspaces"
        @open="selectWorkspace"
        @new-workspace="openNewWorkspace"
        @import-workspace="importWorkspaceFile"
      />
    </div>

    <div v-if="globalError" class="fixed top-3 right-3 z-[100] max-w-md flex items-start gap-2 bg-red-50 border border-red-200 text-red-600 text-xs px-3 py-2 rounded-lg shadow-lg">
      <span class="flex-1">{{ globalError }}</span>
      <button @click="globalError = ''" class="text-red-400 hover:text-red-600">×</button>
    </div>

    <div v-if="versionNotice" class="fixed top-3 right-3 z-[100] bg-green-50 border border-green-200 text-green-700 text-xs px-3 py-2 rounded-lg shadow-lg">
      {{ versionNotice }}
    </div>

    <ImportConflictModal
      :conflict="importConflict"
      @choose="chooseImportAction"
    />

    <MergeConflictModal
      :conflict="projectConflict"
      @apply="applyConflictMerge"
      @overwrite="overwriteConflict"
      @reload="reloadConflictProject"
    />

    <TaskModal
      :isOpen="isModalOpen"
      :isEditing="isEditing"
      :initialData="editingTask"
      :tasks="tasks"
      :workers="currentProject?.workers || []"
      :activeWorkerIds="activeWorkerIds"
      :workerMode="workerMode"
      :workerCount="workerMode === 'workers' ? customWorkerCount : 1"
      :projectTimezone="projectTimezoneInfo"
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
      :holidayCoverage="holidayCoverage"
      @close="closeProjectModal"
      @save="handleProjectSave"
    />

    <AdminUsersModal
      :isOpen="isAdminUsersOpen"
      @close="isAdminUsersOpen = false"
      @created="isAdminUsersOpen = false"
    />

    <HistoryModal
      :isOpen="isHistoryModalOpen"
      :revisions="projectRevisions"
      :loading="historyLoading"
      @close="isHistoryModalOpen = false"
      @restore="restoreRevision"
      @rename="renameRevision"
      @delete="deleteRevision"
      @save="saveVersion"
    />

    <TeamModal
      :isOpen="isTeamModalOpen"
      :workers="currentProject?.workers || []"
      :activeWorkerIds="activeWorkerIds"
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
import { ArrowLeft, ArrowRight, BarChart2, ChevronLeft, Download, Edit2, GitGraph, History, Save, Users } from 'lucide-vue-next'

import Sidebar from './components/Sidebar.vue'
import DashboardView from './components/DashboardView.vue'
import HomeView from './components/HomeView.vue'
import AuthView from './components/AuthView.vue'
import AdminUsersModal from './components/AdminUsersModal.vue'
import TaskSidebar from './components/TaskSidebar.vue'
import TaskModal from './components/TaskModal.vue'
import ProjectModal from './components/ProjectModal.vue'
import TeamModal from './components/TeamModal.vue'
import MergeConflictModal from './components/MergeConflictModal.vue'
import HistoryModal from './components/HistoryModal.vue'
import ImportConflictModal from './components/ImportConflictModal.vue'
import WorkspaceModal from './components/WorkspaceModal.vue'
import GanttView from './components/GanttView.vue'
import DependencyView from './components/DependencyView.vue'
import WorkerModeSelector from './components/WorkerModeSelector.vue'
import {
  projectTimezone, timeInTimezone, wallTimeInTimezone
} from './utils/timezone'
import { applyMergeChoices, mergeProjectState } from './utils/merge'
import { downloadFromUrl } from './utils/download'

const authUser = ref<any>(null)
const authChecked = ref(false)
const authLoading = ref(false)
const authError = ref('')
const needsSetup = ref(false)

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
const projectTimezoneInfo = computed(() => projectTimezone(currentProject.value))
const projectConflict = ref<any>(null)
const projectBase = ref<any>(null)
const undoStack = ref<any[]>([])
const redoStack = ref<any[]>([])
const historySuppressed = ref(false)
const versionNotice = ref('')
const importConflict = ref<any>(null)
const pendingImport = ref<any>(null)

const tasks = ref<any[]>([])
const report = ref<any>(null)
const ganttData = ref<any[]>([])
const scheduledTasks = ref<any[]>([])
const mermaidCode = ref('')
const activeTab = ref('gantt')
const workerMode = ref('infinite')
const customWorkerCount = ref(2)
const activeWorkerIds = ref<string[]>([])
const workerRows = ref<any[]>([])
const capabilityFallbacks = ref<string[]>([])
const holidayCoverage = ref<any>({
  region: 'CN',
  name: 'China statutory holidays',
  years: [],
  updated_at: '',
  sources: {}
})
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
const isHistoryModalOpen = ref(false)
const isAdminUsersOpen = ref(false)
const projectRevisions = ref<any[]>([])
const historyLoading = ref(false)

const isWorkspaceModalOpen = ref(false)
const isEditingWorkspace = ref(false)
const editingWorkspaceData = ref<any>(null)

let suppressTaskRun = false

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : String(error)

const readApiError = async (res: Response) => {
  if (res.status === 401 && authUser.value) {
    authUser.value = null
    globalError.value = 'Your session expired. Please sign in again.'
  }
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

const loadHolidayCoverage = async () => {
  try {
    const res = await fetch('/api/holidays/coverage')
    if (!res.ok) return
    const data = await res.json()
    if (Array.isArray(data?.years) && data.years.length) {
      holidayCoverage.value = data
    }
  } catch {
    // Holiday metadata is advisory; scheduling still works without it.
  }
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

  const rosterIds = (project?.workers || []).map((worker: any) => worker.wid)
  const active = (project?.active_worker_ids || []).filter(
    (wid: string) => rosterIds.includes(wid))
  activeWorkerIds.value = active.length ? active : rosterIds
}

const cloneProject = (project: any) =>
  project ? JSON.parse(JSON.stringify(project)) : null

const historyKey = (prid: string) =>
  `dag-scheduler:edits:${authUser.value?.id || 'anonymous'}:${prid}`

const clearAllDurableHistory = () => {
  try {
    const keys: string[] = []
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (key?.startsWith('dag-scheduler:edits:')) keys.push(key)
    }
    keys.forEach(key => window.localStorage.removeItem(key))
  } catch { /* storage unavailable */ }
}

const clearDurableHistory = (prid: string) => {
  try {
    window.localStorage.removeItem(historyKey(prid))
  } catch { /* storage may be unavailable */ }
}

const persistDurableHistory = () => {
  if (!activeProjectId.value || !authUser.value) return
  try {
    window.localStorage.setItem(historyKey(activeProjectId.value), JSON.stringify({
      undo: undoStack.value,
      redo: redoStack.value
    }))
  } catch { /* quota/unavailable: keep the in-memory queue */ }
}

const loadDurableHistory = (prid: string) => {
  undoStack.value = []
  redoStack.value = []
  if (!authUser.value) return
  try {
    const raw = window.localStorage.getItem(historyKey(prid))
    if (!raw) return
    const parsed = JSON.parse(raw)
    undoStack.value = Array.isArray(parsed.undo)
      ? parsed.undo.slice(-20) : []
    redoStack.value = Array.isArray(parsed.redo)
      ? parsed.redo.slice(-20) : []
  } catch {
    clearDurableHistory(prid)
  }
}

const applyProject = (project: any, preserveDurableHistory = false) => {
  historySuppressed.value = true
  undoStack.value = []
  redoStack.value = []
  if (!preserveDurableHistory) clearDurableHistory(project.prid)
  currentProject.value = project
  activeProjectId.value = project.prid
  if (project?.holiday_coverage?.years?.length) {
    holidayCoverage.value = project.holiday_coverage
  }
  projectBase.value = cloneProject(project)
  applyWorkerSettings(project)
  nextTick(() => {
    historySuppressed.value = false
  })
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

const exportProject = async () => {
  if (!activeProjectId.value) return
  try {
    await downloadFromUrl(
      `/api/projects/${activeProjectId.value}/export`,
      'project.json')
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const runImport = async (pending: any, strategy = 'cancel') => {
  try {
    const isWorkspace = pending.kind === 'workspace'
    const url = isWorkspace
      ? `/api/workspaces/import?on_duplicate=${strategy}`
      : `/api/projects/import?wsid=${encodeURIComponent(pending.wsid)}&on_duplicate=${strategy}`
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': isWorkspace ? 'application/zip' : 'application/json'
      },
      body: pending.body
    })
    if (res.status === 409) {
      const data = await res.json()
      const error = data?.error
      if (error?.kind && error?.duplicates) {
        importConflict.value = {
          kind: error.kind,
          duplicates: error.duplicates
        }
        pendingImport.value = pending
        return
      }
      throw new Error(
        typeof error?.detail === 'string' ? error.detail : 'Import conflict')
    }
    if (!res.ok) throw new Error(await readApiError(res))
    const imported = await res.json()
    importConflict.value = null
    pendingImport.value = null
    if (isWorkspace) {
      await loadWorkspaces()
      if (imported?.workspace?.wsid) {
        await selectWorkspace(imported.workspace.wsid)
      }
      versionNotice.value = 'Workspace imported'
    } else {
      await refreshWorkspaceProjects()
      await loadWorkspaces()
      if (imported?.prid) await openProject(imported.prid)
      versionNotice.value = 'Project imported'
    }
    window.setTimeout(() => { versionNotice.value = '' }, 2500)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const importWorkspaceFile = async (file: File) => {
  if (!file) return
  await runImport({
    kind: 'workspace',
    body: await file.arrayBuffer()
  })
}

const importProjectFile = async (file: File) => {
  if (!file || !activeWorkspaceId.value) return
  await runImport({
    kind: 'project',
    wsid: activeWorkspaceId.value,
    body: await file.text()
  })
}

const chooseImportAction = async (action: string) => {
  if (action === 'cancel') {
    importConflict.value = null
    pendingImport.value = null
    return
  }
  const pending = pendingImport.value
  if (!pending) return
  await runImport(pending, action)
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

    applyProject(project, true)
    await setTasksFromProject(project.events || [])
    loadDurableHistory(project.prid)
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

const refreshHistory = async () => {
  if (!activeProjectId.value) return
  historyLoading.value = true
  try {
    const res = await fetch(
      `/api/projects/${activeProjectId.value}/revisions`)
    if (!res.ok) throw new Error(await readApiError(res))
    projectRevisions.value = await res.json()
  } catch (error) {
    globalError.value = errorMessage(error)
  } finally {
    historyLoading.value = false
  }
}

const openHistory = async () => {
  if (!activeProjectId.value) return
  isHistoryModalOpen.value = true
  projectRevisions.value = []
  await refreshHistory()
}

const renameRevision = async (payload: any) => {
  const revision = payload?.revision
  const label = String(payload?.label || '').trim()
  if (!revision?.id || !label) return
  try {
    const res = await fetch(
      `/api/projects/${activeProjectId.value}/revisions/${revision.id}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label })
      }
    )
    if (!res.ok) throw new Error(await readApiError(res))
    await refreshHistory()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const deleteRevision = async (revision: any) => {
  if (!revision?.id) return
  try {
    const res = await fetch(
      `/api/projects/${activeProjectId.value}/revisions/${revision.id}`,
      { method: 'DELETE' })
    if (!res.ok && res.status !== 404) {
      throw new Error(await readApiError(res))
    }
    await refreshHistory()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const restoreRevision = async (revisionId: number) => {
  if (!activeProjectId.value || !currentProject.value) return
  try {
    const res = await fetch(
      `/api/projects/${activeProjectId.value}/restore`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version: currentProject.value.version,
          revision_id: revisionId
        })
      }
    )
    if (res.status === 409) {
      isHistoryModalOpen.value = false
      globalError.value = 'Project changed while opening checkpoints. Reloaded the latest version.'
      await openProject(activeProjectId.value, false)
      return
    }
    if (!res.ok) throw new Error(await readApiError(res))
    const updated = await res.json()
    isHistoryModalOpen.value = false
    if (updated.wsid && updated.wsid !== activeWorkspaceId.value) {
      activeWorkspaceId.value = updated.wsid
    }
    applyProject(updated)
    await setTasksFromProject(updated.events || [])
    await refreshWorkspaceProjects()
    await loadWorkspaces()
    pushUrl()
    await runSchedule(false)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const openTeamModal = () => {
  if (workerMode.value !== 'team') return
  isTeamModalOpen.value = true
}

const saveTeam = async (payload: any) => {
  if (!activeProjectId.value) return
  try {
    const res = await fetch(`/api/projects/${activeProjectId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workers: payload.workers,
        active_worker_ids: payload.active_worker_ids,
        version: currentProject.value?.version
      })
    })
    if (res.status === 409) {
      await openConflictMerge({
        prid: activeProjectId.value,
        title: currentProject.value?.title,
        localPatch: {
          workers: payload.workers,
          active_worker_ids: payload.active_worker_ids
        }
      })
      return
    }
    if (!res.ok) throw new Error(await readApiError(res))
    const updated = await res.json()
    currentProject.value = updated
    projectBase.value = cloneProject(updated)
    applyWorkerSettings(updated)
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
          body: JSON.stringify({
            ...data,
            version: editingProjectData.value.version
          })
        }
      )
      if (res.status === 409) {
        const target = editingProjectData.value
        closeProjectModal()
        await openConflictMerge({
          prid: target.prid,
          title: target.title,
          localPatch: data
        })
        return
      }
      if (!res.ok) throw new Error(await readApiError(res))
      const updated = await res.json()
      projectBase.value = cloneProject(updated)

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

    clearDurableHistory(project.prid)
    await refreshWorkspaceProjects()
    await loadWorkspaces()

    if (activeProjectId.value === project.prid) goWorkspace()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const moveProjectToWorkspace = async ({ prid, wsid }: any) => {
  if (!prid || !wsid) return
  const known = currentProject.value?.prid === prid
    ? currentProject.value
    : workspaceProjects.value.find((project: any) => project.prid === prid)
  try {
    const res = await fetch(`/api/projects/${prid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wsid, version: known?.version })
    })
    if (res.status === 409) {
      await openConflictMerge({
        prid,
        title: known?.title,
        localPatch: { wsid }
      })
      return
    }
    if (!res.ok) throw new Error(await readApiError(res))
    const updated = await res.json()
    projectBase.value = cloneProject(updated)

    await loadWorkspaces()

    if (activeProjectId.value === prid) {
      activeWorkspaceId.value = updated.wsid
      currentProject.value = updated
      await refreshWorkspaceProjects()
      pushUrl()
      await runSchedule(false)
    } else {
      await refreshWorkspaceProjects()
    }
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

const checkAuth = async () => {
  authLoading.value = true
  authError.value = ''
  try {
    const me = await fetch('/api/auth/me')
    if (me.ok) {
      authUser.value = await me.json()
      needsSetup.value = false
      await loadFromUrl()
    } else {
      authUser.value = null
      const status = await fetch('/api/auth/status')
      if (status.ok) {
        const body = await status.json()
        needsSetup.value = Boolean(body.needs_setup)
      }
    }
  } catch (error) {
    authError.value = errorMessage(error)
  } finally {
    authChecked.value = true
    authLoading.value = false
  }
}

const handleAuthSubmit = async (payload: any) => {
  authLoading.value = true
  authError.value = ''
  try {
    const endpoint = needsSetup.value ? '/api/auth/bootstrap' : '/api/auth/login'
    const body = needsSetup.value
      ? {
          username: payload.username,
          display_name: payload.displayName,
          password: payload.password
        }
      : { username: payload.username, password: payload.password }
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!res.ok) throw new Error(await readApiError(res))
    authUser.value = await res.json()
    needsSetup.value = false
    await loadFromUrl()
  } catch (error) {
    authError.value = errorMessage(error)
  } finally {
    authLoading.value = false
  }
}

const logout = async () => {
  try {
    await fetch('/api/auth/logout', { method: 'POST' })
  } catch { /* clear locally regardless */ }
  clearAllDurableHistory()
  authUser.value = null
  authChecked.value = true
  needsSetup.value = false
  activeWorkspaceId.value = null
  activeProjectId.value = null
  currentProject.value = null
  workspaceProjects.value = []
  workspaces.value = []
  tasks.value = []
  resetEditor()
  window.history.replaceState({}, '', '/')
}

const loadFromUrl = async () => {
  if (!authUser.value) return
  globalError.value = ''
  try {
    if (!holidayCoverage.value.years?.length) {
      await loadHolidayCoverage()
    }
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

const onHistoryKeydown = (event: KeyboardEvent) => {
  if (!(event.metaKey || event.ctrlKey)) return
  const target = event.target as HTMLElement | null
  if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
  if (target?.isContentEditable) return
  const key = event.key.toLowerCase()
  if (key === 'z') {
    event.preventDefault()
    if (event.shiftKey) void redoEdit()
    else void undoEdit()
  } else if (key === 'y') {
    event.preventDefault()
    void redoEdit()
  }
}

onMounted(() => {
  window.addEventListener('popstate', loadFromUrl)
  window.addEventListener('keydown', onHistoryKeydown)
  checkAuth()
})

onUnmounted(() => {
  window.removeEventListener('popstate', loadFromUrl)
  window.removeEventListener('keydown', onHistoryKeydown)
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

const buildLocalSnapshot = (patch: any = {}) => {
  const project = currentProject.value || {}
  const snapshot = {
    ...project,
    ...patch,
    events: patch.events ?? tasks.value,
    worker_mode: patch.worker_mode ?? workerMode.value,
    worker_count: patch.worker_count ?? customWorkerCount.value,
    active_worker_ids: patch.active_worker_ids ?? activeWorkerIds.value,
    version: project.version
  }
  return cloneProject(snapshot)
}

const fetchLatestProject = async (prid: string) => {
  const res = await fetch(`/api/projects/${prid}`)
  if (!res.ok) throw new Error(await readApiError(res))
  return await res.json()
}

const openConflictMerge = async (conflict: any) => {
  const prid = conflict?.prid || activeProjectId.value
  if (!prid) return
  try {
    const remote = await fetchLatestProject(prid)
    const title = remote?.title || conflict?.title || 'Project'
    if (activeProjectId.value !== prid || !projectBase.value) {
      projectConflict.value = {
        prid,
        title,
        conflicts: [],
        merged: null,
        local: null,
        remote,
        canMerge: false
      }
      return
    }
    const local = buildLocalSnapshot(conflict?.localPatch || {})
    const result = mergeProjectState(projectBase.value, local, remote)
    projectConflict.value = {
      prid,
      title,
      conflicts: result.conflicts,
      merged: result.merged,
      local,
      remote,
      canMerge: true
    }
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const onProjectConflict = (conflict: any) => {
  void openConflictMerge(conflict)
}

const reloadConflictProject = async () => {
  const conflict = projectConflict.value
  projectConflict.value = null
  if (!conflict) return
  try {
    if (activeProjectId.value === conflict.prid) {
      await openProject(conflict.prid, false)
    } else {
      await refreshWorkspaceProjects()
      await loadWorkspaces()
    }
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const projectSnapshotPayload = (snapshot: any, version: number) => ({
  version,
  title: snapshot.title,
  description: snapshot.description ?? '',
  origin: snapshot.origin,
  ddl: snapshot.ddl,
  wsid: snapshot.wsid,
  workers: snapshot.workers || [],
  worker_mode: snapshot.worker_mode,
  worker_count: snapshot.worker_count,
  single_worker_id: snapshot.single_worker_id ?? null,
  active_worker_ids: snapshot.active_worker_ids || [],
  capability_mode: snapshot.capability_mode,
  deadline_mode: snapshot.deadline_mode,
  timezone_mode: snapshot.timezone_mode,
  timezone: snapshot.timezone,
  utc_offset_minutes: snapshot.utc_offset_minutes,
  skip_weekends: Boolean(snapshot.skip_weekends),
  holidays: snapshot.holidays || [],
  holiday_ranges: snapshot.holiday_ranges || [],
  default_holidays: Boolean(snapshot.default_holidays),
  events: snapshot.events || []
})

const stripVolatile = (snapshot: any) => {
  const copy = cloneProject(snapshot) || {}
  delete copy.report
  delete copy.holiday_coverage
  delete copy.version
  delete copy.created_at
  delete copy.updated_at
  return copy
}

const historySnapshot = computed(() => stripVolatile(buildLocalSnapshot()))

watch(historySnapshot, (next, previous) => {
  if (historySuppressed.value || !activeProjectId.value || !previous) return
  if (JSON.stringify(next) === JSON.stringify(previous)) return
  undoStack.value.push(cloneProject(previous))
  if (undoStack.value.length > 20) undoStack.value.shift()
  redoStack.value = []
  persistDurableHistory()
}, { deep: true })

const applyHistorySnapshot = async (snapshot: any) => {
  historySuppressed.value = true
  suppressTaskRun = true
  const preserved = currentProject.value || {}
  currentProject.value = {
    ...preserved,
    ...cloneProject(snapshot),
    version: preserved.version,
    report: preserved.report,
    holiday_coverage: preserved.holiday_coverage,
    created_at: preserved.created_at,
    updated_at: preserved.updated_at
  }
  tasks.value = cloneProject(snapshot.events) || []
  workerMode.value = snapshot.worker_mode || 'infinite'
  customWorkerCount.value = snapshot.worker_count || 2
  activeWorkerIds.value = snapshot.active_worker_ids || []
  await nextTick()
  suppressTaskRun = false
}

const saveHistorySnapshot = async (snapshot: any) => {
  if (!activeProjectId.value || !currentProject.value) return false
  const res = await fetch(`/api/projects/${activeProjectId.value}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(projectSnapshotPayload(
      snapshot, currentProject.value.version))
  })
  if (res.status === 409) {
    historySuppressed.value = false
    await openConflictMerge({
      prid: activeProjectId.value,
      title: currentProject.value.title,
      localPatch: snapshot
    })
    return false
  }
  if (!res.ok) {
    historySuppressed.value = false
    throw new Error(await readApiError(res))
  }
  const updated = await res.json()
  if (updated.wsid && updated.wsid !== activeWorkspaceId.value) {
    activeWorkspaceId.value = updated.wsid
  }
  suppressTaskRun = true
  currentProject.value = updated
  projectBase.value = cloneProject(updated)
  report.value = updated.report || null
  tasks.value = updated.events || []
  await nextTick()
  suppressTaskRun = false
  await refreshWorkspaceProjects()
  await loadWorkspaces()
  pushUrl()
  await runSchedule(false)
  historySuppressed.value = false
  return true
}

const undoEdit = async () => {
  if (!undoStack.value.length || projectConflict.value) return
  try {
    const snapshot = undoStack.value.pop()
    redoStack.value.push(cloneProject(historySnapshot.value))
    if (redoStack.value.length > 20) redoStack.value.shift()
    await applyHistorySnapshot(snapshot)
    await saveHistorySnapshot(snapshot)
    persistDurableHistory()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const redoEdit = async () => {
  if (!redoStack.value.length || projectConflict.value) return
  try {
    const snapshot = redoStack.value.pop()
    undoStack.value.push(cloneProject(historySnapshot.value))
    if (undoStack.value.length > 20) undoStack.value.shift()
    await applyHistorySnapshot(snapshot)
    await saveHistorySnapshot(snapshot)
    persistDurableHistory()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const saveVersion = async () => {
  if (!activeProjectId.value || projectConflict.value) return
  try {
    const saved = await saveProjectToServer()
    if (!saved) return
    const res = await fetch(
      `/api/projects/${activeProjectId.value}/revisions`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      }
    )
    if (!res.ok) throw new Error(await readApiError(res))
    versionNotice.value = 'Checkpoint saved'
    window.setTimeout(() => { versionNotice.value = '' }, 2500)
    if (isHistoryModalOpen.value) {
      await openHistory()
    }
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const persistProjectSnapshot = async (snapshot: any, version: number) => {
  const conflict = projectConflict.value
  if (!conflict) return
  const res = await fetch(`/api/projects/${conflict.prid}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(projectSnapshotPayload(snapshot, version))
  })
  if (res.status === 409) {
    await openConflictMerge({
      prid: conflict.prid,
      title: conflict.title,
      localPatch: snapshot
    })
    return
  }
  if (!res.ok) throw new Error(await readApiError(res))

  const updated = await res.json()
  projectConflict.value = null
  if (updated.wsid && updated.wsid !== activeWorkspaceId.value) {
    activeWorkspaceId.value = updated.wsid
  }
  applyProject(updated)
  await setTasksFromProject(updated.events || [])
  await refreshWorkspaceProjects()
  await loadWorkspaces()
  pushUrl()
  await runSchedule(false)
}

const applyConflictMerge = async (choices: Record<string, 'mine' | 'theirs'>) => {
  const conflict = projectConflict.value
  if (!conflict?.canMerge) return
  try {
    const merged = applyMergeChoices({
      merged: conflict.merged,
      conflicts: conflict.conflicts
    }, choices)
    await persistProjectSnapshot(merged, conflict.remote.version)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const overwriteConflict = async () => {
  const conflict = projectConflict.value
  if (!conflict?.canMerge) return
  try {
    await persistProjectSnapshot(conflict.local, conflict.remote.version)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const saveProjectToServer = async () => {
  if (!activeProjectId.value) return null
  const res = await fetch(`/api/projects/${activeProjectId.value}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      events: tasks.value,
      worker_mode: workerMode.value,
      worker_count: customWorkerCount.value,
      active_worker_ids: activeWorkerIds.value,
      version: currentProject.value?.version
    })
  })
  if (res.status === 409) {
    await openConflictMerge({ prid: activeProjectId.value })
    return null
  }
  if (!res.ok) throw new Error(await readApiError(res))

  const updated = await res.json()
  currentProject.value = updated
  projectBase.value = cloneProject(updated)
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

const markerLabel = (iso: string) => {
  const wall = wallTimeInTimezone(iso, projectTimezoneInfo.value)
  if (!wall) return ''
  return globalSpan.value > 1440 * 60000
    ? wall.substring(5, 10)
    : wall.substring(11, 16)
}

const runSchedule = async (persist = true) => {
  if (!activeProjectId.value || projectConflict.value) return
  loading.value = true
  globalError.value = ''

  try {
    if (persist) {
      const saved = await saveProjectToServer()
      if (!saved) return
    }
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
        const iso = new Date(timeVal).toISOString()
        markers.push({
          time: iso,
          label: markerLabel(iso)
        })
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
      const activeSet = activeWorkerIds.value.filter(
        (wid: string) => roster.some((worker: any) => worker.wid === wid))
      const chosen = activeSet.length
        ? activeSet
        : roster.map((worker: any) => worker.wid)
      const activeRows = roster.filter(
        (worker: any) => chosen.includes(worker.wid))
      const teamIds = activeRows.map((worker: any) => worker.wid)
      activeIds = teamIds
      workers = teamIds.length
      workerRows.value = activeRows.map((worker: any) => ({
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
    const projectDdlMs = Date.parse(currentProject.value?.ddl || '')

    scheduledTasks.value = eids.map(eid => {
      const s = startTimes[eid] - minT
      const e = endTimes[eid] - minT
      const info = schedData.tasks[eid]
        || { description: eid, status: 'normal' }

      let status = info.status
      if (hasOrigin) {
        const deadlineMs = Date.parse(
          eventsByEid.get(eid)?.deadline)
        const effectiveDeadlineMs = (
          Number.isFinite(projectDdlMs) && Number.isFinite(deadlineMs)
            ? Math.min(projectDdlMs, deadlineMs)
            : (Number.isFinite(projectDdlMs) ? projectDdlMs : deadlineMs)
        )
        if (Number.isFinite(effectiveDeadlineMs)
            && endTimes[eid] > effectiveDeadlineMs) {
          status = 'overdue'
        }
      }
      statuses[eid] = status

      const startIso = new Date(startTimes[eid]).toISOString()
      const endIso = new Date(endTimes[eid]).toISOString()
      return {
        id: eid,
        name: info.description,
        start: startIso,
        end: endIso,
        startLabel: timeInTimezone(startIso, projectTimezoneInfo.value),
        endLabel: timeInTimezone(endIso, projectTimezoneInfo.value),
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
    const projectOverdue = Number.isFinite(projectDdlMs) && maxT > projectDdlMs
    const projectLateMinutes = projectOverdue
      ? Math.round((maxT - projectDdlMs) / 60000)
      : 0
    report.value = {
      ...(currentProject.value?.report || {}),
      makespan: schedData.makespan,
      makespan_human: formatMinutes(schedData.makespan),
      critical_count: statusList.filter(
        s => s === 'critical').length,
      overdue_count: statusList.filter(
        s => s === 'overdue').length,
      project_ddl: currentProject.value?.ddl || null,
      project_finish: new Date(maxT).toISOString(),
      project_overdue: projectOverdue,
      project_late_minutes: projectLateMinutes,
      project_late_human: formatMinutes(projectLateMinutes)
    }

    const markerCount = 5
    const markers = []
    for (let i = 0; i < markerCount; i++) {
      const timeVal = minT + (
        globalSpan.value * (i / (markerCount - 1)))
      const iso = new Date(timeVal).toISOString()
      markers.push({
        time: iso,
        label: markerLabel(iso)
      })
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

const holidayYearsLabel = computed(() => {
  const years = holidayCoverage.value?.years || []
  return years.length ? `${years[0]}–${years[years.length - 1]}` : 'none'
})

const holidayCoverageWarning = computed(() => {
  const project = currentProject.value
  if (!project?.default_holidays) return ''
  const covered = holidayCoverage.value?.years || []
  if (!covered.length) return ''

  const years = new Set<number>()
  const addYear = (value: string | null | undefined) => {
    if (!value) return
    const parsed = new Date(value)
    if (!Number.isNaN(parsed.getTime())) years.add(parsed.getFullYear())
  }
  addYear(project.origin)
  addYear(project.ddl)
  for (const event of project.events || []) {
    addYear(event.start)
    addYear(event.deadline)
  }

  const uncovered = [...years]
    .filter(year => !covered.includes(year))
    .sort((a, b) => a - b)
  if (!uncovered.length) return ''

  return `Default statutory holidays cover ${holidayYearsLabel.value}. `
    + `${uncovered.join(', ')} has no official holiday data yet; only weekends `
    + `and custom holiday periods are skipped.`
})

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
