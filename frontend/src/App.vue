<template>
  <div class="flex flex-col h-screen bg-[#f7f8fa] text-[#262626] font-sans">
    
    <!-- 1. Top Navigator -->
    <header class="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0 shadow-sm z-10">
      <div class="flex items-center gap-3">
        <div class="bg-blue-600 text-white p-1.5 rounded-md flex items-center justify-center">
          <Activity class="w-5 h-5" />
        </div>
        
        <!-- Project Selector -->
        <select 
          v-model="currentProjectId" 
          @change="loadProjectData"
          class="bg-blue-50 text-blue-700 font-semibold text-sm rounded px-2 py-1 border-none focus:ring-0 cursor-pointer"
        >
          <option v-for="p in projects" :key="p.prid" :value="p.prid">{{ p.title }}</option>
        </select>
        <button @click="createNewProject" class="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-2 py-1 rounded">+ New</button>
        <button @click="openProjectModal" title="Project settings" class="bg-gray-100 hover:bg-gray-200 text-gray-600 p-1.5 rounded">
          <Pencil class="w-4 h-4" />
        </button>
      </div>
      
      <!-- Right-side state and mode selector -->
      <div class="flex items-center gap-6 text-sm text-gray-500">
        <span v-if="globalError" class="text-red-500 bg-red-50 px-2 py-1 rounded border border-red-200 text-xs max-w-md truncate">
          ⚠ {{ globalError }}
        </span>
        
        <!-- Worker mode selector -->
        <WorkerModeSelector 
          v-model="workerMode" 
          v-model:count="customWorkerCount" 
          :maxConcurrency="report?.max_concurrency"
        />

        <span>Makespan: <strong class="text-gray-900">{{ report?.makespan_human || '--' }}</strong></span>
        <span>Critical: <strong class="text-orange-500">{{ report?.critical_count || 0 }}</strong></span>
        <span>Overdue: <strong :class="report?.overdue_count > 0 ? 'text-red-500' : 'text-gray-900'">{{ report?.overdue_count || 0 }}</strong></span>
      </div>
    </header>

    <!-- 2. 主体区域 -->
    <main class="flex flex-1 overflow-hidden">
      
      <!-- 左侧 -->
      <TaskSidebar 
        :tasks="tasks" 
        @update:tasks="handleTasksUpdate"
        @edit="openEditModal"
        @open-new="openNewModal"
      />

      <!-- 右侧 -->
      <section class="flex-1 flex flex-col bg-white overflow-hidden relative">
        <!-- 顶部 Tabs -->
        <div class="flex items-center px-4 border-b border-gray-200 bg-white shrink-0 z-10">
          <button @click="activeTab = 'gantt'" :class="activeTab === 'gantt' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'" class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2">
            <BarChart2 class="w-4 h-4" /> Gantt Graph
          </button>
          <button @click="activeTab = 'graph'" :class="activeTab === 'graph' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'" class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2">
            <GitGraph class="w-4 h-4" /> Dependency Graph
          </button>
        </div>

        <!-- 视图渲染区 -->
        <div class="flex-1 relative overflow-hidden bg-[#f7f8fa]">
          <GanttView 
            v-show="activeTab === 'gantt'" 
            :ganttData="ganttData" 
            :scheduledTasks="scheduledTasks" 
            :effectiveWorkers="effectiveWorkers"
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
    </main>

    <!-- 3. 弹窗组件 -->
    <TaskModal 
      :isOpen="isModalOpen" 
      :isEditing="isEditing" 
      :initialData="editingTask" 
      :tasks="tasks"
      @close="isModalOpen = false"
      @save="saveTask"
      @delete="deleteTask"
    />

    <ProjectModal
      :isOpen="isProjectModalOpen"
      :project="currentProject"
      :error="projectModalError"
      @close="closeProjectModal"
      @save="saveProjectSettings"
      @delete="deleteProject"
    />
  </div>
</template>

<script setup lang="ts">
import WorkerModeSelector from './components/WorkerModeSelector.vue'
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { Activity, BarChart2, GitGraph, Pencil } from 'lucide-vue-next'

// 引入拆分好的子组件
import TaskSidebar from './components/TaskSidebar.vue'
import TaskModal from './components/TaskModal.vue'
import ProjectModal from './components/ProjectModal.vue'
import GanttView from './components/GanttView.vue'
import DependencyView from './components/DependencyView.vue'

// ==========================================
// 状态管理
// ==========================================
const projects = ref<any[]>([])
const currentProjectId = ref<string | null>(null)
const currentProject = ref<any>(null)
const tasks = ref<any[]>([])

const report = ref<any>(null)
const ganttData = ref<any[]>([])
const scheduledTasks = ref<any[]>([])
const mermaidCode = ref('')
const activeTab = ref('gantt')
const workerMode = ref('infinite')
const customWorkerCount = ref(2)
const loading = ref(false)
const globalError = ref('')

const timeMarkers = ref<any[]>([])
const globalSpan = ref(0)

const isModalOpen = ref(false)
const isEditing = ref(false)
const editingTask = ref<any>(null)
const isProjectModalOpen = ref(false)
const projectModalError = ref('')

// Prevents the task watcher from re-saving events while a project is loaded.
let suppressTaskSave = false
// Ignores stale project-load responses when the user switches quickly.
let projectLoadToken = 0

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

const applyProject = (project: any) => {
  currentProject.value = project
  report.value = project.report || null
  const index = projects.value.findIndex(p => p.prid === project.prid)
  if (index >= 0) projects.value[index] = { ...projects.value[index], ...project }
  else projects.value.unshift(project)
}

const setTasksFromProject = async (project: any) => {
  suppressTaskSave = true
  try {
    tasks.value = project.events || []
    await nextTick()
  } finally {
    suppressTaskSave = false
  }
}

const createProject = async (title: string) => {
  const res = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  })
  if (!res.ok) throw new Error(await readApiError(res))

  const project = await res.json()
  projects.value = [project, ...projects.value.filter(p => p.prid !== project.prid)]
  projectLoadToken += 1
  currentProjectId.value = project.prid
  applyProject(project)
  await setTasksFromProject(project)
  await runSchedule()
  return project
}

const fetchProjects = async () => {
  const res = await fetch('/api/projects')
  if (!res.ok) throw new Error(await readApiError(res))
  projects.value = await res.json()

  if (projects.value.length === 0) {
    await createProject('Default Project')
    return
  }

  currentProjectId.value = projects.value[0].prid
  await loadProjectData()
}

const createNewProject = async () => {
  globalError.value = ''
  try {
    await createProject(`Project ${projects.value.length + 1}`)
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}

const loadProjectData = async () => {
  const prid = currentProjectId.value
  if (!prid) return
  const token = ++projectLoadToken
  globalError.value = ''
  try {
    const res = await fetch(`/api/projects/${prid}`)
    if (!res.ok) throw new Error(await readApiError(res))

    const project = await res.json()
    if (token !== projectLoadToken || currentProjectId.value !== prid) return
    applyProject(project)
    await setTasksFromProject(project)
    await runSchedule()
  } catch (error) {
    if (token === projectLoadToken) {
      globalError.value = errorMessage(error)
    }
  }
}

onMounted(() => {
  fetchProjects().catch(error => { globalError.value = errorMessage(error) })
})

// ==========================================
// 核心业务逻辑
// ==========================================
const handleTasksUpdate = (newTasks: any[]) => { tasks.value = newTasks }

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

const openNewModal = () => { isEditing.value = false; editingTask.value = null; isModalOpen.value = true }
const openEditModal = (task: any) => { isEditing.value = true; editingTask.value = task; isModalOpen.value = true }

const effectiveWorkers = computed(() => {
  if (workerMode.value === 'infinite') return 'infinite'
  if (workerMode.value === '1') return '1'
  return customWorkerCount.value.toString()
})

const persistProjectEvents = async () => {
  const prid = currentProjectId.value
  if (!prid) return
  const res = await fetch(`/api/projects/${prid}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ events: tasks.value })
  })
  if (!res.ok) throw new Error(await readApiError(res))
  const project = await res.json()
  if (currentProjectId.value === prid) applyProject(project)
}

// 90 -> "1h 30m", matching the backend's feasibility report.
const formatMinutes = (total: number) => {
  const sign = total < 0 ? '-' : ''
  const minutes = Math.abs(total)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h && m) return `${sign}${h}h ${m}m`
  if (h) return `${sign}${h}h`
  return `${sign}${m}m`
}

const runSchedule = async () => {
  const prid = currentProjectId.value
  if (!prid) return
  loading.value = true
  globalError.value = ''

  try {
    // Start from the persisted CPM report; finite modes override it below.
    report.value = currentProject.value?.report || null

    const graphRes = await fetch(`/api/projects/${prid}/graph?format=mermaid`)
    if (!graphRes.ok) throw new Error(await readApiError(graphRes))
    const graph = await graphRes.json()
    if (currentProjectId.value !== prid) return
    mermaidCode.value = graph.content

    if (workerMode.value === 'infinite') {
      const ganttRes = await fetch(`/api/projects/${prid}/gantt`)
      if (!ganttRes.ok) throw new Error(await readApiError(ganttRes))
      const rawGantt = await ganttRes.json()
      if (currentProjectId.value !== prid) return
      scheduledTasks.value = []

      if (rawGantt.length === 0) {
        ganttData.value = []
        timeMarkers.value = []
        globalSpan.value = 0
        return
      }

      // 这部分复杂的百分比计算，为了配合组件化，直接在这里算好给 GanttView
      const minTime = Math.min(...rawGantt.map((t: any) => new Date(t.start).getTime()))
      const maxTime = Math.max(...rawGantt.map((t: any) => new Date(t.end).getTime()))
      globalSpan.value = maxTime - minTime || 1

      ganttData.value = rawGantt.map((task: any) => {
        const tStart = new Date(task.start).getTime()
        const tEnd = new Date(task.end).getTime()
        return {
          id: task.eid, name: task.description, start: task.start, end: task.end,
          leftPct: ((tStart - minTime) / globalSpan.value) * 100,
          widthPct: Math.max(((tEnd - tStart) / globalSpan.value) * 100, 1),
          custom_class: task.status === 'critical' ? 'bg-orange-400' : (task.status === 'overdue' ? 'bg-red-400' : 'bg-blue-500')
        }
      })

      // 计算底部时间刻度
      const markerCount = 5
      const markers = []
      for (let i = 0; i < markerCount; i++) {
        const timeVal = minTime + (globalSpan.value * (i / (markerCount - 1)))
        markers.push({ time: new Date(timeVal).toISOString() })
      }
      timeMarkers.value = markers
      return
    }

    const w = workerMode.value === 'custom' ? customWorkerCount.value : 1
    const schedRes = await fetch(`/api/projects/${prid}/schedule?workers=${w}`)
    if (!schedRes.ok) throw new Error(await readApiError(schedRes))
    const schedData = await schedRes.json()
    if (currentProjectId.value !== prid) return

    const eids = Object.keys(schedData.start)
    ganttData.value = []
    if (eids.length === 0) {
      scheduledTasks.value = []
      timeMarkers.value = []
      globalSpan.value = 0
      return
    }

    // Schedule start/end are offsets from the project origin. Convert them to
    // absolute times so the timeline shows real dates and bars stay inside
    // the visible span.
    const originMs = Date.parse(currentProject.value?.origin)
    const hasOrigin = Number.isFinite(originMs)
    const startTimes: Record<string, number> = {}
    const endTimes: Record<string, number> = {}
    eids.forEach(eid => {
      startTimes[eid] = (hasOrigin ? originMs : 0) + schedData.start[eid] * 60000
      endTimes[eid] = (hasOrigin ? originMs : 0) + schedData.end[eid] * 60000
    })

    const minT = Math.min(...eids.map(eid => startTimes[eid]))
    const maxT = Math.max(...eids.map(eid => endTimes[eid]))
    globalSpan.value = maxT - minT || 1

    const eventsByEid = new Map<string, any>(
      (currentProject.value?.events || []).map((e: any) => [e.eid, e] as [string, any])
    )
    const statuses: Record<string, string> = {}

    scheduledTasks.value = eids.map(eid => {
      const s = startTimes[eid] - minT
      const e = endTimes[eid] - minT
      const info = schedData.tasks[eid] || { description: eid, status: 'normal' }

      // Re-evaluate overdue against the resource-constrained finish time.
      let status = info.status
      if (hasOrigin) {
        const deadlineMs = Date.parse(eventsByEid.get(eid)?.deadline)
        if (Number.isFinite(deadlineMs) && endTimes[eid] > deadlineMs) {
          status = 'overdue'
        }
      }
      statuses[eid] = status

      return {
        id: eid, name: info.description,
        start: new Date(startTimes[eid]).toISOString(),
        end: new Date(endTimes[eid]).toISOString(),
        leftPct: (s / globalSpan.value) * 100,
        widthPct: Math.max(((e - s) / globalSpan.value) * 100, 1),
        workerId: schedData.assignments[eid],
        custom_class: status === 'critical' ? 'bg-indigo-500' : (status === 'overdue' ? 'bg-red-500' : 'bg-emerald-500')
      }
    })

    // Header stats must describe the active (resource-constrained) schedule,
    // not the unlimited-worker CPM report.
    const statusList = Object.values(statuses)
    report.value = {
      ...(currentProject.value?.report || {}),
      makespan: schedData.makespan,
      makespan_human: formatMinutes(schedData.makespan),
      critical_count: statusList.filter(s => s === 'critical').length,
      overdue_count: statusList.filter(s => s === 'overdue').length
    }

    const markerCount = 5
    const markers = []
    for (let i = 0; i < markerCount; i++) {
      const timeVal = minT + (globalSpan.value * (i / (markerCount - 1)))
      markers.push({ time: new Date(timeVal).toISOString() })
    }
    timeMarkers.value = markers
  } catch (error) {
    globalError.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

watch(tasks, async () => {
  if (suppressTaskSave || !currentProjectId.value) return
  globalError.value = ''
  try {
    await persistProjectEvents()
    await runSchedule()
  } catch (error) {
    globalError.value = errorMessage(error)
  }
}, { deep: true })

watch(workerMode, () => {
  runSchedule()
})

watch(customWorkerCount, () => {
  if (workerMode.value === 'custom') runSchedule()
})

// ==========================================
// Project settings
// ==========================================
const openProjectModal = () => {
  projectModalError.value = ''
  isProjectModalOpen.value = true
}

const closeProjectModal = () => {
  isProjectModalOpen.value = false
  projectModalError.value = ''
}

const saveProjectSettings = async (payload: any) => {
  if (!currentProjectId.value) return
  projectModalError.value = ''
  try {
    const res = await fetch(`/api/projects/${currentProjectId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, events: tasks.value })
    })
    if (!res.ok) throw new Error(await readApiError(res))

    applyProject(await res.json())
    isProjectModalOpen.value = false
    await runSchedule()
  } catch (error) {
    projectModalError.value = errorMessage(error)
  }
}

const deleteProject = async () => {
  if (!currentProjectId.value) return
  const title = currentProject.value?.title || 'this project'
  if (!confirm(`Delete "${title}"? This cannot be undone.`)) return

  projectModalError.value = ''
  try {
    const res = await fetch(`/api/projects/${currentProjectId.value}`, { method: 'DELETE' })
    if (!res.ok && res.status !== 404) throw new Error(await readApiError(res))

    isProjectModalOpen.value = false
    currentProjectId.value = null
    currentProject.value = null
    report.value = null
    ganttData.value = []
    scheduledTasks.value = []
    mermaidCode.value = ''
    timeMarkers.value = []
    globalSpan.value = 0

    await fetchProjects()
  } catch (error) {
    projectModalError.value = errorMessage(error)
    globalError.value = errorMessage(error)
  }
}
</script>