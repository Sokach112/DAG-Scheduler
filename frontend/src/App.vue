<template>
  <div class="flex flex-col h-screen bg-[#f7f8fa] text-[#262626] font-sans">
    
    <!-- 1. 顶部导航栏 -->
    <header class="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0 shadow-sm z-10">
      <div class="flex items-center gap-3">
        <div @click="currentView = 'dashboard'" class="bg-blue-600 text-white p-1.5 rounded-md flex items-center justify-center cursor-pointer hover:bg-blue-700">
          <Activity class="w-5 h-5" />
        </div>
        
        <template v-if="currentView === 'editor'">
          <button @click="currentView = 'dashboard'" class="text-sm font-medium text-gray-500 hover:text-gray-800 flex items-center gap-1">
            ← Back to Projects
          </button>
          <span class="text-gray-300">|</span>
          <span class="font-semibold text-gray-800">{{ currentProjectTitle }}</span>
        </template>
      </div>
      
      <!-- 右侧状态与模式选择 (只在编辑模式显示) -->
      <div v-if="currentView === 'editor'" class="flex items-center gap-6 text-sm text-gray-500">
        <span v-if="globalError" class="text-red-500 bg-red-50 px-2 py-1 rounded border border-red-200 text-xs max-w-md truncate">
          ⚠ {{ globalError }}
        </span>
        
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

    <!-- 2. 视图区域 -->
    <main class="flex flex-1 overflow-hidden">
      <!-- 视图 A：Dashboard -->
      <DashboardView 
        v-if="currentView === 'dashboard'" 
        @open="openProject" 
      />

      <!-- 视图 B：Editor -->
      <div v-else-if="currentView === 'editor'" class="flex flex-1 overflow-hidden">
        <TaskSidebar 
          :tasks="tasks" 
          @update:tasks="handleTasksUpdate"
          @edit="openEditModal"
          @open-new="openNewModal"
        />

        <section class="flex-1 flex flex-col bg-white overflow-hidden relative">
          <div class="flex items-center px-4 border-b border-gray-200 bg-white shrink-0 z-10">
            <button @click="activeTab = 'gantt'" :class="activeTab === 'gantt' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'" class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2">
              <BarChart2 class="w-4 h-4" /> Gantt Graph
            </button>
            <button @click="activeTab = 'graph'" :class="activeTab === 'graph' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'" class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2">
              <GitGraph class="w-4 h-4" /> Dependency Graph
            </button>
          </div>

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
      </div>
    </main>

    <!-- 3. 弹窗 -->
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
import { ref, computed, watch } from 'vue'
import { Activity, BarChart2, GitGraph } from 'lucide-vue-next'

import DashboardView from './components/DashboardView.vue'
import TaskSidebar from './components/TaskSidebar.vue'
import TaskModal from './components/TaskModal.vue'
import GanttView from './components/GanttView.vue'
import DependencyView from './components/DependencyView.vue'
import WorkerModeSelector from './components/WorkerModeSelector.vue'

// ==========================================
// 状态管理
// ==========================================
const currentView = ref<'dashboard' | 'editor'>('dashboard')
const currentProjectId = ref<string | null>(null)
const currentProjectTitle = ref('')
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
// 核心逻辑
// ==========================================

// 打开项目
const openProject = async (prid: string) => {
  loading.value = true
  try {
    const res = await fetch(`/api/projects/${prid}`)
    if (!res.ok) throw new Error("Project not found")
    const data = await res.json()
    
    currentProjectId.value = prid
    currentProjectTitle.value = data.title
    tasks.value = data.events || []
    currentView.value = 'editor'
    
    // 如果项目里已经有任务，自动触发一次渲染
    if (tasks.value.length > 0) runSchedule()
  } catch (err: any) {
    alert(err.message)
  } finally {
    loading.value = false
  }
}

// 任务变动：自动重绘 + 防抖保存
let saveTimer: any = null
const handleTasksUpdate = (newTasks: any[]) => {
  tasks.value = newTasks
  // 自动保存
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => { saveProjectToServer() }, 1000)
}

const saveProjectToServer = async () => {
  if (!currentProjectId.value) return
  try {
    await fetch(`/api/projects/${currentProjectId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events: tasks.value })
    })
  } catch (err) {
    console.error("Autosave failed:", err)
  }
}

// 任务数据改变触发图表重算
watch(tasks, () => {
  if (tasks.value.length > 0) runSchedule()
  else { report.value = null; ganttData.value = []; scheduledTasks.value = []; mermaidCode.value = '' }
}, { deep: true })

// 图表请求 (和你之前的一样)
const runSchedule = async () => {
  if (tasks.value.length === 0) return
  loading.value = true
  globalError.value = ''
  
  try {
    // 此处需要把 tasks 转成 PlanIn 格式
    const payload = JSON.stringify({ version: 1, events: tasks.value })
    const res = await fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload })
    if (!res.ok) throw new Error("Failed to calculate plan")
    const planId = (await res.json()).plan_id

    const [repRes, graphRes] = await Promise.all([
      fetch(`/api/plan/${planId}/report`),
      fetch(`/api/plan/${planId}/graph?format=mermaid`)
    ])
    
    report.value = await repRes.json()
    mermaidCode.value = (await graphRes.json()).content

    if (workerMode.value === 'infinite') {
      const ganttRes = await fetch(`/api/plan/${planId}/gantt`)
      const rawGantt = await ganttRes.json()
      
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
      
      const starts = Object.values(schedData.start) as number[]
      const ends = Object.values(schedData.end) as number[]
      const minT = Math.min(...starts) * 60000
      const maxT = Math.max(...ends) * 60000
      globalSpan.value = maxT - minT || 1
      
      ganttData.value = []
      scheduledTasks.value = Object.keys(schedData.start).map(eid => {
        const s = schedData.start[eid] * 60000
        const e = schedData.end[eid] * 60000
        const info = schedData.tasks[eid] || { description: eid, status: 'normal' }
        return {
          id: eid, name: info.description, start: new Date(minT + s).toISOString(), end: new Date(minT + e).toISOString(),
          leftPct: (s / globalSpan.value) * 100,
          widthPct: Math.max(((e - s) / globalSpan.value) * 100, 1),
          workerId: schedData.assignments[eid],
          custom_class: info.status === 'critical' ? 'bg-indigo-500' : 'bg-emerald-500'
        }
      })
      
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

// 弹窗管理
const openNewModal = () => { isEditing.value = false; editingTask.value = null; isModalOpen.value = true }
const openEditModal = (task: any) => { isEditing.value = true; editingTask.value = task; isModalOpen.value = true }
const saveTask = (taskData: any) => { /* 同你之前逻辑 */ 
  if (!taskData.eid) {
    let nextNum = tasks.value.length + 1
    let nextEid = `T${nextNum}`
    while (tasks.value.some(t => t.eid === nextEid)) { 
      nextNum++; nextEid = `T${nextNum}` 
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
const deleteTask = (eid: string) => { tasks.value = tasks.value.filter(t => t.eid !== eid); isModalOpen.value = false }

const effectiveWorkers = computed(() => {
  if (workerMode.value === 'infinite') return 'infinite'
  if (workerMode.value === '1') return '1'
  return customWorkerCount.value.toString()
})
</script>