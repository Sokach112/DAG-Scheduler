<template>
  <div class="flex flex-col h-screen bg-[#f7f8fa] text-[#262626] font-sans">
    
    <!-- 1. 顶部导航栏 -->
    <header class="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0 shadow-sm z-10">
      <div class="flex items-center gap-3">
        <div class="bg-blue-600 text-white p-1.5 rounded-md flex items-center justify-center">
          <Activity class="w-5 h-5" />
        </div>
        
        <!-- 项目选择器 -->
        <select 
          v-model="currentProjectId" 
          @change="loadProjectData"
          class="bg-blue-50 text-blue-700 font-semibold text-sm rounded px-2 py-1 border-none focus:ring-0 cursor-pointer"
        >
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button @click="createNewProject" class="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-2 py-1 rounded">+ New</button>
      </div>
      
      <!-- 右侧状态与模式选择 -->
      <div class="flex items-center gap-6 text-sm text-gray-500">
        <span v-if="globalError" class="text-red-500 bg-red-50 px-2 py-1 rounded border border-red-200 text-xs max-w-md truncate">
          ⚠ {{ globalError }}
        </span>
        
        <!-- 简单内联的 Worker 模式选择器 (替代组件) -->
        <div class="flex items-center gap-2 bg-gray-50 p-1 rounded-lg border border-gray-200">
          <button @click="setMode('infinite')" :class="workerMode === 'infinite' ? 'bg-white shadow text-blue-600' : 'text-gray-600'" class="px-3 py-1.5 rounded-md text-xs font-medium flex flex-col items-center h-[38px]"><span>Infinite</span><span class="text-[10px] text-gray-400">(Needs ≥{{ report?.max_concurrency || 1 }})</span></button>
          <button @click="setMode('1')" :class="workerMode === '1' ? 'bg-white shadow text-blue-600' : 'text-gray-600'" class="px-3 py-1.5 rounded-md text-xs font-medium flex flex-col items-center h-[38px]"><span>Single</span><span class="text-[10px] text-gray-400">(1 Worker)</span></button>
          <div @click="setMode('custom')" :class="workerMode === 'custom' ? 'bg-white shadow text-blue-600' : 'text-gray-600'" class="px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer flex flex-col items-center h-[38px]">
            <span>Custom</span>
            <input v-if="workerMode === 'custom'" v-model.number="customWorkerCount" @click.stop @change="runSchedule" type="number" min="1" class="w-12 h-4 text-[10px] text-center border-b bg-transparent" />
            <span v-else class="text-[10px] text-gray-400">(N Workers)</span>
          </div>
        </div>

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

const setMode = (mode: string) => {
  workerMode.value = mode
  runSchedule()
}

// 只要 tasks 变了，自动重绘
watch(tasks, () => {
  if (tasks.value.length > 0) runSchedule()
  else { report.value = null; ganttData.value = []; scheduledTasks.value = []; mermaidCode.value = '' }
}, { deep: true })

const runSchedule = async () => {
  if (tasks.value.length === 0) return
  loading.value = true
  globalError.value = ''
  
  try {
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
</script>