<template>
  <div class="flex flex-col h-screen bg-[#f7f8fa] text-[#262626] font-sans">
    
    <!-- Top Navigator -->
    <header class="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0 shadow-sm z-10">
      <div class="flex items-center gap-3">
        <div class="bg-blue-600 text-white p-1.5 rounded-md flex items-center justify-center">
          <Activity class="w-5 h-5" />
        </div>
        <h1 class="text-lg font-semibold text-gray-800 tracking-tight">DAG Scheduler</h1>
        <span class="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full border border-gray-200">Visual Console</span>
      </div>
      
      <div class="flex items-center gap-6 text-sm text-gray-500">
        <!-- Global Error Hint -->
        <span v-if="globalError" class="text-red-500 bg-red-50 px-2 py-1 rounded border border-red-200 text-xs max-w-md truncate">
          ⚠ {{ globalError }}
        </span>

        <!-- Mode select -->
        <div class="flex items-center gap-2 bg-gray-50 p-1 rounded-lg border border-gray-200">
          <!-- Infinite mode -->
          <button @click="setMode('infinite')" :class="workerMode === 'infinite' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'" class="px-3 py-1.5 rounded-md text-xs font-medium transition-all flex flex-col items-center justify-center h-[38px]">
            <span>Infinite</span>
            <span v-if="report?.max_concurrency" class="text-[10px] text-gray-400 block -mt-0.5">(Needs ≥{{ report.max_concurrency }})</span>
            <span v-else class="text-[10px] text-gray-400 block -mt-0.5">(CPM Limit)</span>
          </button>
          
          <!-- Single mode -->
          <button @click="setMode('1')" :class="workerMode === '1' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'" class="px-3 py-1.5 rounded-md text-xs font-medium transition-all flex flex-col items-center justify-center h-[38px]">
            <span>Single</span>
            <span class="text-[10px] text-gray-400 block -mt-0.5">(1 Worker)</span>
          </button>

          <!-- Custom mode -->
          <div @click="setMode('custom')" :class="workerMode === 'custom' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'" class="px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer flex flex-col items-center justify-center h-[38px]">
            <span>Custom</span>
            <input 
              v-if="workerMode === 'custom'"
              v-model.number="customWorkerCount"
              @click.stop
              @change="runSchedule"
              type="number" min="1"
              class="w-12 h-4 text-[10px] text-center border-b border-blue-300 focus:outline-none bg-transparent"
              placeholder="N"
            />
            <span v-else class="text-[10px] text-gray-400 block -mt-0.5">(N Workers)</span>
          </div>
        </div>

        <span>Makespan: <strong class="text-gray-900">{{ report?.makespan_human || '--' }}</strong></span>
        <span>Critical: <strong class="text-orange-500">{{ report?.critical_count || 0 }}</strong></span>
        <span>Overdue: <strong :class="report?.overdue_count > 0 ? 'text-red-500' : 'text-gray-900'">{{ report?.overdue_count || 0 }}</strong></span>
      </div>
    </header>

    <!-- Main Body -->
    <main class="flex flex-1 overflow-hidden">
      
      <!-- Left: Task List & Controls -->
      <aside class="w-[35%] min-w-[360px] max-w-[500px] bg-white border-r border-gray-200 flex flex-col shadow-sm">
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/50">
          <h2 class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <ListTodo class="w-4 h-4 text-gray-400" />
            Task List ({{ tasks.length }})
          </h2>
          <div class="flex gap-2">
            <button @click="openModal()" class="flex items-center gap-1 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 px-2.5 py-1.5 rounded text-sm font-medium transition-colors">
              <Plus class="w-4 h-4" /> New
            </button>
            <!-- 自动计算状态指示器 -->
            <div class="flex items-center px-3 py-1.5 text-sm font-medium">
              <span v-if="loading" class="flex items-center gap-1.5 text-blue-600">
                <div class="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                Updating...
              </span>
              <span v-else class="flex items-center gap-1.5 text-green-600">
                <div class="w-2 h-2 rounded-full bg-green-500"></div> Live
              </span>
            </div>
          </div>
        </div>
        
        <!-- Task List -->
        <div class="flex-1 overflow-y-auto p-4 bg-[#fafafa] flex flex-col gap-2">
          <div v-if="tasks.length === 0" class="text-center text-gray-400 mt-10 text-sm">No tasks yet.</div>
          <div v-for="task in tasks" :key="task.eid" @click="openModal(task)" class="bg-white p-3 border border-gray-200 rounded-lg shadow-sm hover:border-blue-400 cursor-pointer group flex justify-between items-center">
            <div class="w-full min-w-0 overflow-hidden">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-gray-800 text-sm truncate break-all">{{ task.description }}</span>
                <span class="text-gray-500 text-xs shrink-0">{{ task.eid }}</span>
              </div>
              <div class="text-xs text-gray-400 mt-1 font-mono truncate">{{ task.start.substring(0, 16).replace('T', ' ') }} ~ {{ task.deadline.substring(0, 16).replace('T', ' ') }}</div>
            </div>
            <Edit2 class="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 shrink-0 ml-2" />
          </div>
        </div>
      </aside>

      <!-- Right: Visualized Results -->
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
          <!-- Empty State -->
          <div v-if="!ganttData.length && !scheduledTasks.length && !loading" class="absolute inset-0 flex flex-col items-center justify-center text-gray-400">
            <MonitorPlay class="w-16 h-16 mb-4 opacity-20" />
            <p>Add tasks to visualize</p>
          </div>

          <!-- Gantt View -->
          <div v-show="activeTab === 'gantt' && (ganttData.length > 0 || scheduledTasks.length > 0)" class="absolute inset-0 p-6 overflow-auto">
            <div class="bg-white p-6 rounded-xl border border-gray-200 shadow-sm min-w-[800px]">
              <div class="flex items-center justify-between mb-6">
                <h2 class="text-base font-semibold text-gray-800">
                  {{ effectiveWorkers === 'infinite' 
                      ? 'Task Timeline (Infinite)' 
                      : `Resource Schedule (${effectiveWorkers} Workers)` }}
                </h2>
                <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">Global Span</span>
              </div>

              <div class="flex flex-col gap-4 relative">
                <!-- Mode A: Infinite -->
                <template v-if="effectiveWorkers === 'infinite'">
                  <div v-for="task in ganttData" :key="task.id" class="flex items-center text-sm group">
                    <div class="w-48 shrink-0 pr-4 overflow-hidden">
                      <span class="text-gray-600 font-medium truncate block break-all" :title="task.name">{{ task.name }}</span>
                    </div>
                    <div class="flex-1 relative h-8 bg-gray-50 rounded border border-gray-100">
                      <div class="absolute top-0 bottom-0 rounded shadow-sm text-[11px] text-white flex items-center px-2 overflow-hidden" :class="task.custom_class" :style="{ left: task.leftPct + '%', width: task.widthPct + '%' }">
                        <span v-if="task.widthPct > 15" class="w-full truncate break-all block">{{ task.name }}</span>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- Mode B: Resource Constrained (Workers) -->
                <template v-else>
                  <div v-for="wId in parseInt(effectiveWorkers)" :key="wId" class="flex items-center text-sm group">
                    <div class="w-48 shrink-0 pr-4 font-semibold text-gray-600">Worker {{ wId - 1 }}</div>
                    <div class="flex-1 relative h-10 bg-gray-50 rounded border border-gray-100">
                      <div 
                        v-for="task in scheduledTasks.filter(t => t.workerId === wId - 1)" 
                        :key="task.id"
                        class="absolute top-1 bottom-1 rounded shadow-sm text-[11px] text-white flex items-center px-2 overflow-hidden"
                        :class="task.custom_class"
                        :style="{ left: task.leftPct + '%', width: task.widthPct + '%' }"
                        :title="`${task.name} (${task.start.substring(11,16)} - ${task.end.substring(11,16)})`"
                      >
                        <span v-if="task.widthPct > 10" class="w-full truncate break-all block">{{ task.name }}</span>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- Bottom Timeline -->
                <div class="flex mt-2 border-t border-gray-200 pt-2">
                  <div class="w-48 shrink-0 pr-4"></div>
                  <div class="flex-1 flex justify-between text-xs text-gray-400 font-mono">
                    <span v-for="mark in timeMarkers" :key="mark.time">
                      {{ globalSpan > 1440 * 60000 ? mark.time.substring(5, 10) : mark.time.substring(11, 16) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Dependency Graph -->
          <div :class="activeTab === 'graph' ? 'opacity-100 z-10 pointer-events-auto' : 'opacity-0 z-0 pointer-events-none'" class="absolute inset-0 p-6 overflow-auto bg-[#f7f8fa] transition-opacity duration-200">
            <div class="bg-white p-8 rounded-xl border border-gray-200 shadow-sm min-h-full inline-block min-w-full overflow-auto">
              <div ref="mermaidContainer" class="mermaid"></div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- Modal -->
    <div v-if="isModalOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl w-[480px] flex flex-col overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
          <h3 class="text-lg font-semibold text-gray-800">{{ isEditing ? 'Edit Task' : 'New Task' }}</h3>
          <button @click="isModalOpen = false" class="text-gray-400 hover:text-gray-600"><X class="w-5 h-5"/></button>
        </div>
        
        <div class="p-6 flex flex-col gap-4 overflow-y-auto max-h-[70vh]">
          <!-- Description -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Description</label>
            <input v-model="form.description" type="text" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.description ? 'border-red-500 focus:ring-red-500' : 'border-gray-300 focus:ring-blue-500'" placeholder="e.g. Frontend Development" />
            <p v-if="formErrors.description" class="text-xs text-red-500 mt-1">{{ formErrors.description }}</p>
          </div>

          <!-- Details -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Details (Optional)</label>
            <textarea v-model="form.details" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" placeholder="Add extra notes..."></textarea>
          </div>

          <!-- Duration & Priority -->
          <div class="flex gap-4">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Duration (e.g. 2h 30m)</label>
              <input v-model="form.durationStr" @change="parseDuration" type="text" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.durationStr ? 'border-red-500 focus:ring-red-500' : 'border-gray-300 focus:ring-blue-500'" />
              <p class="text-[11px] text-gray-400 mt-1">Total: {{ form.duration }} mins</p>
              <p v-if="formErrors.durationStr" class="text-xs text-red-500">{{ formErrors.durationStr }}</p>
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Priority</label>
              <input v-model.number="form.priority" type="number" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.priority ? 'border-red-500 focus:ring-red-500' : 'border-gray-300 focus:ring-blue-500'" />
              <p v-if="formErrors.priority" class="text-xs text-red-500 mt-1">{{ formErrors.priority }}</p>
            </div>
          </div>

          <!-- Start Time & Deadline -->
          <div class="flex gap-4">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Start Time</label>
              <input v-model="form.startStr" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.startStr ? 'border-red-500 focus:ring-red-500' : 'border-gray-300 focus:ring-blue-500'" />
              <p v-if="formErrors.startStr" class="text-xs text-red-500 mt-1">{{ formErrors.startStr }}</p>
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Deadline</label>
              <input v-model="form.deadlineStr" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.deadlineStr ? 'border-red-500 focus:ring-red-500' : 'border-gray-300 focus:ring-blue-500'" />
              <p v-if="formErrors.deadlineStr" class="text-xs text-red-500 mt-1">{{ formErrors.deadlineStr }}</p>
            </div>
          </div>

          <!-- Dependencies -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Dependencies</label>
            <div class="w-full max-h-32 overflow-y-auto overflow-x-auto border border-gray-300 rounded-md p-2 bg-gray-50 flex flex-col gap-1">
              <div v-if="availableDependencies.length === 0" class="text-xs text-gray-400 italic p-1">
                No other tasks available to depend on.
              </div>
              <label 
                v-for="t in availableDependencies" 
                :key="t.eid" 
                class="flex items-center gap-2 px-2 py-1.5 hover:bg-gray-100 rounded cursor-pointer transition-colors min-w-max"
              >
                <input 
                  type="checkbox" 
                  :value="t.eid" 
                  v-model="form.dependencies"
                  class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 shrink-0"
                />
                <span class="text-xs font-semibold text-gray-600 shrink-0">{{ t.eid }}</span>
                <span class="text-xs text-gray-800 flex-1 truncate max-w-[150px]" :title="t.description">{{ t.description }}</span>
                <span class="text-[10px] text-gray-400 ml-auto shrink-0">
                  {{ t.start.substring(5, 16).replace('T', ' ') }} ~ {{ t.deadline.substring(5, 16).replace('T', ' ') }}
                </span>
              </label>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-between items-center">
          <button v-if="isEditing" @click="deleteTask" class="text-red-500 hover:text-red-700 text-sm font-medium">Delete</button>
          <div v-else></div>
          <div class="flex gap-3">
            <button @click="isModalOpen = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">Cancel</button>
            <button @click="saveTask" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">Save</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { Activity, Play, BarChart2, GitGraph, MonitorPlay, ListTodo, Plus, Edit2, X } from 'lucide-vue-next'
import mermaid from 'mermaid'

mermaid.initialize({ 
  startOnLoad: false, 
  theme: 'default', 
  flowchart: { useMaxWidth: false, htmlLabels: true, curve: 'basis' } 
})

// --- State ---
const tasks = ref<any[]>([])
const loading = ref(false)
const globalError = ref('') 
const report = ref<any>(null)
const ganttData = ref<any[]>([])
const scheduledTasks = ref<any[]>([])
const activeTab = ref('gantt')
const workerMode = ref('infinite') 
const customWorkerCount = ref(2)   
const mermaidContainer = ref<HTMLElement | null>(null)
const timeMarkers = ref<any[]>([])
const minTime = ref(0)
const maxTime = ref(0)
const globalSpan = ref(0)

const effectiveWorkers = computed(() => {
  if (workerMode.value === 'infinite') return 'infinite'
  if (workerMode.value === '1') return '1'
  return (customWorkerCount.value || 1).toString()
})

const setMode = (mode: string) => {
  workerMode.value = mode
  runSchedule()
}

// --- Modal State ---
const isModalOpen = ref(false)
const isEditing = ref(false)
const formErrors = ref<Record<string, string>>({})
const form = ref({
  eid: '', description: '', details: '', duration: 60, durationStr: '1h', priority: 1,
  startStr: '2026-01-01T09:00', deadlineStr: '2026-01-01T10:00', dependencies: [] as string[]
})

watch([() => form.value.startStr, () => form.value.deadlineStr], ([newStart, newEnd]) => {
  if (newStart && newEnd) {
    const start = new Date(newStart).getTime()
    const end = new Date(newEnd).getTime()
    if (end > start) {
      const mins = Math.floor((end - start) / 60000)
      form.value.duration = mins
      form.value.durationStr = minsToStr(mins)
      formErrors.value.deadlineStr = '' 
    }
  }
})

// 防抖触发器
let debounceTimer: any = null
const debouncedRun = () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    runSchedule()
  }, 600) // 600ms 防抖，让用户连续编辑时不要频繁发请求
}

// 监听任务列表变动，自动重绘
watch(tasks, () => {
  if (tasks.value.length > 0) debouncedRun()
  else { ganttData.value = []; scheduledTasks.value = []; report.value = null }
}, { deep: true })

const minsToStr = (mins: number) => {
  if (mins <= 0) return '0m'
  const d = Math.floor(mins / 1440)
  const h = Math.floor((mins % 1440) / 60)
  const m = mins % 60
  let str = ''
  if (d > 0) str += `${d}d `
  if (h > 0) str += `${h}h `
  if (m > 0) str += `${m}m`
  return str.trim() || '0m'
}

const parseDuration = () => {
  const str = form.value.durationStr.toLowerCase()
  let totalMins = 0
  const dMatch = str.match(/(\d+)\s*d/)
  const hMatch = str.match(/(\d+)\s*h/)
  const mMatch = str.match(/(\d+)\s*m/)
  if (dMatch) totalMins += parseInt(dMatch[1]) * 1440
  if (hMatch) totalMins += parseInt(hMatch[1]) * 60
  if (mMatch) totalMins += parseInt(mMatch[1])
  if (totalMins > 0) {
    form.value.duration = totalMins
    if (form.value.startStr) {
      const start = new Date(form.value.startStr)
      start.setMinutes(start.getMinutes() + totalMins)
      form.value.deadlineStr = start.toISOString().substring(0, 16)
      formErrors.value.durationStr = ''
    }
  } else {
    form.value.durationStr = form.value.duration + 'm'
  }
}

const generatedJson = computed(() => {
  if (tasks.value.length === 0) return '{}'
  return JSON.stringify({
    version: 1,
    origin: "2026-01-01T09:00:00+08:00",
    events: tasks.value.map(t => ({ 
      eid: t.eid, 
      description: t.description, 
      details: t.details, 
      duration: t.duration, 
      priority: t.priority, 
      start: t.start, 
      deadline: t.deadline, 
      dependencies: t.dependencies }))
  }, null, 2)
})

const availableDependencies = computed(() => tasks.value.filter(t => t.eid !== form.value.eid))

const openModal = (task?: any) => {
  formErrors.value = {}
  if (task) {
    isEditing.value = true
    form.value = { 
      ...task, 
      details: task.details || '',
      durationStr: minsToStr(task.duration), 
      startStr: task.start.substring(0, 16), 
      deadlineStr: task.deadline.substring(0, 16), 
      dependencies: [...task.dependencies] 
    }
  } else {
    isEditing.value = false
    let nextNum = tasks.value.length + 1
    let nextEid = `T${nextNum}`
    while (tasks.value.some(t => t.eid === nextEid)) { 
      nextNum++
      nextEid = `T${nextNum}` 
    }

    form.value = { 
      eid: nextEid, 
      description: '', 
      details: '',
      duration: 60, 
      durationStr: '1h', 
      priority: 1, 
      startStr: '2026-01-01T09:00', 
      deadlineStr: '2026-01-01T10:00', 
      dependencies: [] 
    }
  }
  isModalOpen.value = true
}

// 表单校验与保存
const saveTask = () => {
  formErrors.value = {}
  let valid = true

  if (!form.value.description.trim()) {
    formErrors.value.description = 'Description is required'
    valid = false
  }
  
  if (form.value.duration < 0) {
    formErrors.value.durationStr = 'Duration cannot be negative'
    valid = false
  }

  const start = new Date(form.value.startStr).getTime()
  const end = new Date(form.value.deadlineStr).getTime()
  if (end <= start) {
    formErrors.value.deadlineStr = 'Deadline must be after Start time'
    valid = false
  }

  if (!valid) return

  const startIso = form.value.startStr + ':00+08:00'
  const deadlineIso = form.value.deadlineStr + ':00+08:00'
  const newTask = { 
    eid: form.value.eid, 
    description: form.value.description, 
    details: form.value.details,
    duration: form.value.duration, 
    priority: form.value.priority, 
    start: startIso, 
    deadline: deadlineIso, 
    dependencies: form.value.dependencies 
  }

  if (isEditing.value) {
    const idx = tasks.value.findIndex(t => t.eid === form.value.eid)
    if (idx !== -1) tasks.value[idx] = newTask
  } else {
    tasks.value.push(newTask)
  }
  isModalOpen.value = false
}

const deleteTask = () => {
  tasks.value = tasks.value.filter(t => t.eid !== form.value.eid)
  isModalOpen.value = false
}

const runSchedule = async () => {
  if (tasks.value.length === 0) return
  loading.value = true
  globalError.value = ''
  
  try {
    const res = await fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: generatedJson.value })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.error?.detail || 'Failed to create plan')
    }
    const planId = (await res.json()).plan_id

    const [repRes, graphRes] = await Promise.all([
      fetch(`/api/plan/${planId}/report`),
      fetch(`/api/plan/${planId}/graph?format=mermaid`)
    ])
    report.value = await repRes.json()
    const graphData = await graphRes.json()

    if (effectiveWorkers.value === 'infinite') {
      const ganttRes = await fetch(`/api/plan/${planId}/gantt`)
      const rawGantt = await ganttRes.json()
      
      minTime.value = Math.min(...rawGantt.map((t: any) => new Date(t.start).getTime()))
      maxTime.value = Math.max(...rawGantt.map((t: any) => new Date(t.end).getTime()))
      globalSpan.value = maxTime.value - minTime.value || 1

      ganttData.value = rawGantt.map((task: any) => {
        const tStart = new Date(task.start).getTime()
        const tEnd = new Date(task.end).getTime()
        return {
          id: task.eid, name: task.description, start: task.start, end: task.end,
          leftPct: ((tStart - minTime.value) / globalSpan.value) * 100,
          widthPct: Math.max(((tEnd - tStart) / globalSpan.value) * 100, 1),
          custom_class: task.status === 'critical' ? 'bg-orange-400' : (task.status === 'overdue' ? 'bg-red-400' : 'bg-blue-500')
        }
      })
      scheduledTasks.value = []
    } else {
      const schedRes = await fetch(`/api/plan/${planId}/schedule?workers=${effectiveWorkers.value}`)
      const schedData = await schedRes.json()
      
      const starts = Object.values(schedData.start) as number[]
      const ends = Object.values(schedData.end) as number[]
      minTime.value = Math.min(...starts) * 60000
      maxTime.value = Math.max(...ends) * 60000
      globalSpan.value = maxTime.value - minTime.value || 1

      scheduledTasks.value = Object.keys(schedData.start).map(eid => {
        const s = schedData.start[eid] * 60000
        const e = schedData.end[eid] * 60000
        const info = schedData.tasks[eid] || { description: eid, status: 'normal' }
        return {
          id: eid, name: info.description, start: new Date(minTime.value + s).toISOString(), end: new Date(minTime.value + e).toISOString(),
          leftPct: (s / globalSpan.value) * 100,
          widthPct: Math.max(((e - s) / globalSpan.value) * 100, 1),
          workerId: schedData.assignments[eid],
          custom_class: info.status === 'critical' ? 'bg-indigo-500' : 'bg-emerald-500'
        }
      })
      ganttData.value = []
    }

    const markerCount = 5
    const markers = []
    for (let i = 0; i < markerCount; i++) {
      const timeVal = minTime.value + (globalSpan.value * (i / (markerCount - 1)))
      markers.push({ time: new Date(timeVal).toISOString() })
    }
    timeMarkers.value = markers

    await nextTick()
    if (mermaidContainer.value) {
      mermaidContainer.value.innerHTML = '' 
      mermaidContainer.value.removeAttribute('data-processed')
      mermaid.render('mermaid-svg', graphData.content).then((result) => {
        if (mermaidContainer.value) mermaidContainer.value.innerHTML = result.svg
      }).catch(err => {
        console.error("Mermaid error:", err)
        globalError.value = 'Failed to render dependency graph'
      })
    }
  } catch (error: any) {
    console.error(error)
    globalError.value = error.message || 'Error during scheduling'
  } finally {
    loading.value = false
  }
}
</script>

<style>
.mermaid { 
  display: flex; 
  justify-content: flex-start; 
  padding: 20px; 
}
.mermaid svg {
  max-width: none !important;
  width: auto !important;
  height: auto !important;
}
</style>