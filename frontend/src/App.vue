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
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button @click="createNewProject" class="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-2 py-1 rounded">+ New</button>
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
          @change="runSchedule" 
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
  </div>
</template>

<script setup lang="ts">
import WorkerModeSelector from './components/WorkerModeSelector.vue'
import { ref, computed, watch, onMounted } from 'vue'
import { Activity, BarChart2, GitGraph } from 'lucide-vue-next'

// 引入拆分好的子组件
import TaskSidebar from './components/TaskSidebar.vue'
import TaskModal from './components/TaskModal.vue'
import GanttView from './components/GanttView.vue'
import DependencyView from './components/DependencyView.vue'

// ==========================================
// 状态管理
// ==========================================
const projects = ref<any[]>([])
const currentProjectId = ref<number | null>(null)
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

// ==========================================
// 项目相关逻辑 (由于还没写后端，暂时先用本地内存模拟)
// ==========================================
const fetchProjects = async () => {
  // 模拟返回一个默认项目
  projects.value = [{ id: 1, name: 'Default Project' }]
  currentProjectId.value = 1
  // 模拟拉取数据
  await loadProjectData()
}

const createNewProject = () => {
  const id = projects.value.length + 1
  projects.value.push({ id, name: `Project ${id}` })
  currentProjectId.value = id
  tasks.value = []
}

const loadProjectData = async () => {
  // 实际这里应该 fetch(`/api/projects/${currentProjectId.value}`)
  // 暂时空置，等接数据库
}

onMounted(() => { fetchProjects() })

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

watch(tasks, () => {
  if (tasks.value.length > 0) runSchedule()
  else { report.value = null; ganttData.value = []; scheduledTasks.value = []; mermaidCode.value = '' }
}, { deep: true })

watch(workerMode, () => {
  runSchedule()
})

watch(customWorkerCount, () => {
  if (workerMode.value === 'custom') runSchedule()
})

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
  if (tasks.value.length === 0) return
  loading.value = true
  globalError.value = ''
  
  try {
    const payload = JSON.stringify({ version: 1, events: tasks.value })
    const res = await fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload })
    if (!res.ok) throw new Error("Failed to calculate plan")
    const planId = (await res.json()).plan_id

    const [repRes, graphRes, planRes] = await Promise.all([
      fetch(`/api/plan/${planId}/report`),
      fetch(`/api/plan/${planId}/graph?format=mermaid`),
      fetch(`/api/plan/${planId}`)
    ])
    
    report.value = await repRes.json()
    mermaidCode.value = (await graphRes.json()).content
    // Needed to turn resource-schedule offsets into absolute times.
    const planData = await planRes.json()

    if (workerMode.value === 'infinite') {
      const ganttRes = await fetch(`/api/plan/${planId}/gantt`)
      const rawGantt = await ganttRes.json()
      
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
      scheduledTasks.value = []
      
      // 计算底部时间刻度
      const markerCount = 5
      const markers = []
      for (let i = 0; i < markerCount; i++) {
        const timeVal = minTime + (globalSpan.value * (i / (markerCount - 1)))
        markers.push({ time: new Date(timeVal).toISOString() })
      }
      timeMarkers.value = markers
      
    } else {
      const w = workerMode.value === 'custom' ? customWorkerCount.value : 1
      const schedRes = await fetch(`/api/plan/${planId}/schedule?workers=${w}`)
      const schedData = await schedRes.json()
      
      const eids = Object.keys(schedData.start)
      // Schedule start/end are offsets from the plan origin. Convert them to
      // absolute times so the timeline shows real dates and bars stay inside
      // the visible span.
      const originMs = Date.parse(planData?.origin)
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
        (planData?.events || []).map((e: any) => [e.eid, e] as [string, any])
      )
      const statuses: Record<string, string> = {}
      
      ganttData.value = []
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
        ...report.value,
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
    }
  } catch (error: any) {
    globalError.value = error.message
  } finally {
    loading.value = false
  }
}
</script>