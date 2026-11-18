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
      <div class="flex items-center gap-4 text-sm text-gray-500">
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
            <button 
              @click="openModal()"
              class="flex items-center gap-1 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 px-2.5 py-1.5 rounded text-sm font-medium transition-colors"
            >
              <Plus class="w-4 h-4" /> New
            </button>
            <button 
              @click="runSchedule"
              :disabled="loading || tasks.length === 0"
              class="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50"
            >
              <Play class="w-3.5 h-3.5" />
              {{ loading ? 'Running...' : 'Run' }}
            </button>
          </div>
        </div>
        
        <!-- Task List -->
        <div class="flex-1 overflow-y-auto p-4 bg-[#fafafa] flex flex-col gap-2">
          <div v-if="tasks.length === 0" class="text-center text-gray-400 mt-10 text-sm">
            No tasks yet. Click "New" to add one.
          </div>
          
          <div 
            v-for="task in tasks" 
            :key="task.eid"
            @click="openModal(task)"
            class="bg-white p-3 border border-gray-200 rounded-lg shadow-sm hover:border-blue-400 cursor-pointer transition-colors group flex justify-between items-center"
          >
            <div>
              <div class="flex items-center gap-2">
                <span class="font-semibold text-gray-800 text-sm">{{ task.eid }}</span>
                <span class="text-gray-500 text-xs">{{ task.description }}</span>
              </div>
              <div class="text-xs text-gray-400 mt-1 font-mono">
                {{ task.start.substring(0, 16).replace('T', ' ') }} ~ {{ task.duration }} mins
              </div>
            </div>
            <div class="text-xs text-gray-400 opacity-0 group-hover:opacity-100">
              <Edit2 class="w-4 h-4" />
            </div>
          </div>
        </div>

        <!-- Hidden JSON Preview for debugging -->
        <details class="border-t border-gray-200 bg-white p-2 text-xs">
          <summary class="text-gray-500 cursor-pointer hover:text-gray-800">Show Generated JSON</summary>
          <pre class="mt-2 p-2 bg-gray-50 rounded overflow-auto max-h-40">{{ generatedJson }}</pre>
        </details>
      </aside>

      <!-- Right: Visualized Results -->
      <section class="flex-1 flex flex-col bg-white overflow-hidden relative">
        <!-- View Shift: Tab -->
        <div class="flex items-center px-4 border-b border-gray-200 bg-white shrink-0 z-10">
          <button @click="activeTab = 'gantt'" :class="activeTab === 'gantt' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'" class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2">
            <BarChart2 class="w-4 h-4" /> Gantt Graph
          </button>
          <button @click="activeTab = 'graph'" :class="activeTab === 'graph' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'" class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2">
            <GitGraph class="w-4 h-4" /> Dependency Graph
          </button>
        </div>

        <!-- Renderer -->
        <div class="flex-1 relative overflow-hidden bg-[#f7f8fa]">
          
          <!-- Empty State -->
          <div v-if="!ganttData.length && !loading" class="absolute inset-0 flex flex-col items-center justify-center text-gray-400">
            <MonitorPlay class="w-16 h-16 mb-4 opacity-20" />
            <p>Add tasks and click Run to visualize</p>
          </div>

          <!-- Custom Gantt -->
          <div v-show="activeTab === 'gantt' && ganttData.length > 0" class="absolute inset-0 p-6 overflow-auto">
            <div class="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
              <h2 class="text-base font-semibold mb-6 text-gray-800">Task Timeline</h2>
              <div class="flex flex-col gap-4">
                <div v-for="task in ganttData" :key="task.id" class="flex items-center text-sm">
                  <div class="w-12 font-bold text-gray-700">{{ task.id }}</div>
                  <div class="w-36 text-gray-500 font-mono text-xs">{{ formatTime(task.start) }} - {{ formatTime(task.end) }}</div>
                  <div class="flex-1 h-6 bg-gray-100 rounded-md relative overflow-hidden">
                    <div class="absolute top-0 bottom-0 rounded-md transition-all duration-500" :class="task.custom_class" :style="{ left: task.leftPct + '%', width: task.widthPct + '%' }"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Dependency Graph (Mermaid) -->
          <div :class="activeTab === 'graph' ? 'opacity-100 z-10 pointer-events-auto' : 'opacity-0 z-0 pointer-events-none'" class="absolute inset-0 p-6 overflow-auto bg-[#f7f8fa] transition-opacity duration-200">
            <div class="bg-white p-8 rounded-xl border border-gray-200 shadow-sm min-h-full flex justify-center">
              <div ref="mermaidContainer" class="mermaid w-full flex justify-center"></div>
            </div>
          </div>

        </div>
      </section>
    </main>

    <!-- Modal: Add / Edit Task -->
    <div v-if="isModalOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl w-[480px] flex flex-col overflow-hidden">
        <!-- Modal Header -->
        <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
          <h3 class="text-lg font-semibold text-gray-800">{{ isEditing ? 'Edit Task' : 'New Task' }}</h3>
          <button @click="isModalOpen = false" class="text-gray-400 hover:text-gray-600"><X class="w-5 h-5"/></button>
        </div>
        
        <!-- Modal Body -->
        <div class="p-6 flex flex-col gap-4 overflow-y-auto max-h-[70vh]">
          <div class="flex gap-4">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Task ID (e.g. A, B)</label>
              <input v-model="form.eid" type="text" :disabled="isEditing" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono" placeholder="A" />
            </div>
            <div class="flex-[2]">
              <label class="block text-xs font-medium text-gray-700 mb-1">Description</label>
              <input v-model="form.description" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm" placeholder="Frontend Development" />
            </div>
          </div>

          <div class="flex gap-4">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Duration (mins)</label>
              <input v-model.number="form.duration" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm" />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Priority (Higher runs first)</label>
              <input v-model.number="form.priority" type="number" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm" />
            </div>
          </div>

          <div class="flex gap-4">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Start Time</label>
              <input v-model="form.startStr" type="datetime-local" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm" />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-700 mb-1">Deadline</label>
              <input v-model="form.deadlineStr" type="datetime-local" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm" />
            </div>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Dependencies (Hold Ctrl/Cmd to select multiple)</label>
            <select v-model="form.dependencies" multiple class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm h-24">
              <option v-for="t in availableDependencies" :key="t.eid" :value="t.eid">
                {{ t.eid }} - {{ t.description }}
              </option>
            </select>
          </div>
        </div>

        <!-- Modal Footer -->
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
import { ref, computed, nextTick } from 'vue'
import { Activity, Play, BarChart2, GitGraph, MonitorPlay, ListTodo, Plus, Edit2, X } from 'lucide-vue-next'
import mermaid from 'mermaid'

mermaid.initialize({ startOnLoad: false, theme: 'default', flowchart: { useMaxWidth: false, htmlLabels: true, curve: 'basis' } })

// --- State ---
const tasks = ref<any[]>([])
const loading = ref(false)
const report = ref<any>(null)
const ganttData = ref<any[]>([])
const activeTab = ref('gantt')
const mermaidContainer = ref<HTMLElement | null>(null)

// --- Modal State ---
const isModalOpen = ref(false)
const isEditing = ref(false)
const form = ref({
  eid: '', description: '', duration: 60, priority: 1,
  startStr: '2026-01-01T09:00', deadlineStr: '2026-01-01T17:00', dependencies: [] as string[]
})

// 生成后端需要的 JSON 格式
const generatedJson = computed(() => {
  if (tasks.value.length === 0) return '{}'
  const payload = {
    version: 1,
    origin: "2026-01-01T09:00:00+08:00", // 固定一个 origin 方便演示
    events: tasks.value.map(t => ({
      eid: t.eid,
      description: t.description,
      duration: t.duration,
      priority: t.priority,
      start: t.start,
      deadline: t.deadline,
      dependencies: t.dependencies
    }))
  }
  return JSON.stringify(payload, null, 2)
})

// 计算可选依赖（排除自己）
const availableDependencies = computed(() => {
  return tasks.value.filter(t => t.eid !== form.value.eid)
})

// --- Helpers ---
const formatTime = (isoStr: string) => isoStr.substring(11, 16)

// --- Modal Actions ---
const openModal = (task?: any) => {
  if (task) {
    isEditing.value = true
    form.value = {
      eid: task.eid,
      description: task.description,
      duration: task.duration,
      priority: task.priority,
      startStr: task.start.substring(0, 16),
      deadlineStr: task.deadline.substring(0, 16),
      dependencies: [...task.dependencies]
    }
  } else {
    isEditing.value = false
    form.value = {
      eid: '', description: '', duration: 60, priority: 1,
      startStr: '2026-01-01T09:00', deadlineStr: '2026-01-01T17:00', dependencies: []
    }
  }
  isModalOpen.value = true
}

const saveTask = () => {
  if (!form.value.eid || !form.value.description) return alert("ID and Description are required")
  
  // 转换回 ISO 格式（补上时区和秒）
  const startIso = form.value.startStr + ':00+08:00'
  const deadlineIso = form.value.deadlineStr + ':00+08:00'

  const newTask = {
    eid: form.value.eid,
    description: form.value.description,
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
    if (tasks.value.some(t => t.eid === form.value.eid)) return alert("ID already exists")
    tasks.value.push(newTask)
  }
  isModalOpen.value = false
}

const deleteTask = () => {
  tasks.value = tasks.value.filter(t => t.eid !== form.value.eid)
  isModalOpen.value = false
}

// --- Run Scheduler ---
const runSchedule = async () => {
  loading.value = true
  try {
    // 1. 发送生成的 JSON 到后端
    const res = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: generatedJson.value
    })
    if (!res.ok) {
        const err = await res.json()
        throw new Error(err.error?.detail || 'Failed to create plan')
    }
    const data = await res.json()
    const planId = data.plan_id

    // 2. 拉取数据
    const [repRes, ganttRes, graphRes] = await Promise.all([
      fetch(`/api/plan/${planId}/report`),
      fetch(`/api/plan/${planId}/gantt`),
      fetch(`/api/plan/${planId}/graph?format=mermaid`)
    ])

    report.value = await repRes.json()
    const rawGantt = await ganttRes.json()
    const graphData = await graphRes.json()

    // 3. 计算甘特图进度条比例
    const minTime = Math.min(...rawGantt.map((t: any) => new Date(t.start).getTime()))
    const maxTime = Math.max(...rawGantt.map((t: any) => new Date(t.end).getTime()))
    const span = maxTime - minTime || 1

    ganttData.value = rawGantt.map((task: any) => {
      const tStart = new Date(task.start).getTime()
      const tEnd = new Date(task.end).getTime()
      return {
        id: task.eid,
        name: task.description,
        start: task.start,
        end: task.end,
        leftPct: ((tStart - minTime) / span) * 100,
        widthPct: Math.max(((tEnd - tStart) / span) * 100, 1),
        custom_class: task.status === 'critical' ? 'bg-orange-400' : (task.status === 'overdue' ? 'bg-red-400' : 'bg-blue-500')
      }
    })

    // 4. 渲染 Mermaid
    await nextTick()
    if (mermaidContainer.value) {
      mermaidContainer.value.innerHTML = '' 
      mermaidContainer.value.removeAttribute('data-processed')
      mermaid.render('mermaid-svg', graphData.content).then((result) => {
        if (mermaidContainer.value) mermaidContainer.value.innerHTML = result.svg
      }).catch(err => console.error("Mermaid error:", err))
    }

  } catch (error: any) {
    console.error(error)
    alert(error.message || 'Error connecting to backend')
  } finally {
    loading.value = false
  }
}
</script>

<style>
.mermaid { width: 100%; display: flex; justify-content: center; }
.mermaid svg { max-width: 100% !important; width: 100% !important; min-height: 400px; }
</style>