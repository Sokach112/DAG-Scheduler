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
      
      <!-- Left: JSON Input -->
      <aside class="w-[35%] min-w-[320px] max-w-[500px] bg-white border-r border-gray-200 flex flex-col shadow-sm">
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/50">
          <h2 class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Code class="w-4 h-4 text-gray-400" />
            Plan JSON Data
          </h2>
          <button 
            @click="createPlan"
            :disabled="loading"
            class="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50"
          >
            <Play class="w-3.5 h-3.5" />
            {{ loading ? 'Running...' : 'Run' }}
          </button>
        </div>
        
        <div class="flex-1 p-4 bg-[#fafafa]">
          <textarea 
            v-model="jsonInput"
            class="w-full h-full p-4 border border-gray-300 rounded-lg shadow-inner focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-[13px] leading-relaxed resize-none bg-white"
            spellcheck="false"
          ></textarea>
        </div>
      </aside>

      <!-- Right: Visualized Results -->
      <section class="flex-1 flex flex-col bg-white overflow-hidden">
        <!-- View Shift: Tab -->
        <div class="flex items-center px-4 border-b border-gray-200 bg-white shrink-0 justify-between">
          <div class="flex items-center">
            <button 
              @click="activeTab = 'gantt'" 
              :class="activeTab === 'gantt' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
              class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2"
            >
              <BarChart2 class="w-4 h-4" /> Gantt Chart
            </button>
            <button 
              @click="activeTab = 'graph'" 
              :class="activeTab === 'graph' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
              class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2"
            >
              <GitGraph class="w-4 h-4" /> Dependency Graph
            </button>
          </div>
          <!-- Workers Selector -->
          <div class="flex items-center gap-2 text-sm text-gray-600">
            <span class="flex items-center gap-1"><Users class="w-4 h-4" /> Workers:</span>
            <select 
              v-model="workers" 
              class="border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option :value="1">1</option>
              <option :value="2">2</option>
              <option :value="3">3</option>
              <option :value="4">4</option>
              <option :value="5">5</option>
            </select>
          </div>
        </div>

        <!-- Renderer -->
        <div class="flex-1 overflow-auto p-6 bg-[#f7f8fa]">
          <!-- Empty State -->
          <div v-if="!ganttData.length && !loading" class="h-full flex flex-col items-center justify-center text-gray-400">
            <MonitorPlay class="w-16 h-16 mb-4 opacity-20" />
            <p>Paste JSON and click Run to visualize</p>
          </div>

          <!-- Gantt -->
          <div v-show="activeTab === 'gantt' && ganttData.length > 0" class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
            <div ref="ganttWrapper"></div> <!-- 使用 div 而不是直接绑在 svg 上，避免渲染冲突 -->
          </div>

          <!-- Dependency -->
          <div v-show="activeTab === 'graph'" class="bg-white p-8 rounded-xl border border-gray-200 shadow-sm flex justify-center min-h-full">
            <div ref="mermaidContainer" class="mermaid w-full flex justify-center overflow-x-auto"></div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Activity, Play, BarChart2, GitGraph, Code, MonitorPlay, Users } from 'lucide-vue-next'
import Gantt from 'frappe-gantt'
import mermaid from 'mermaid'

// Initialize Mermaid
mermaid.initialize({ 
  startOnLoad: false, 
  theme: 'default',
  flowchart: { useMaxWidth: false, htmlLabels: true, curve: 'basis' } 
})

const jsonInput = ref(`{
  "version": 1,
  "origin": "2026-01-01T09:00:00+08:00",
  "events": [
    {"eid": "A", "description": "Demand Analysis", "duration": 30, "priority": 1, "start": "2026-01-01T09:00:00+08:00", "deadline": "2026-01-01T15:00:00+08:00", "dependencies": []},
    {"eid": "B", "description": "System Design", "duration": 60, "priority": 2, "start": "2026-01-01T09:00:00+08:00", "deadline": "2026-01-01T15:00:00+08:00", "dependencies": ["A"]},
    {"eid": "C", "description": "Frontend Development", "duration": 120, "priority": 3, "start": "2026-01-01T09:00:00+08:00", "deadline": "2026-01-01T18:00:00+08:00", "dependencies": ["B"]},
    {"eid": "D", "description": "Backend Development", "duration": 150, "priority": 3, "start": "2026-01-01T09:00:00+08:00", "deadline": "2026-01-01T18:00:00+08:00", "dependencies": ["B"]},
    {"eid": "E", "description": "Joint Debugging", "duration": 45, "priority": 4, "start": "2026-01-01T09:00:00+08:00", "deadline": "2026-01-01T20:00:00+08:00", "dependencies": ["C", "D"]}
  ]
}`)

const loading = ref(false)
const report = ref<any>(null)
const ganttData = ref<any[]>([])
const activeTab = ref('gantt')
const workers = ref(1)
const ganttWrapper = ref<HTMLElement | null>(null) // 改为 HTMLDivElement
const mermaidContainer = ref<HTMLElement | null>(null)
let ganttInstance: any = null

const createPlan = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: jsonInput.value
    })
    if (!res.ok) throw new Error(await res.text())
    const planId = (await res.json()).plan_id

    const [repRes, ganttRes, graphRes] = await Promise.all([
      fetch(`/api/plan/${planId}/report`),
      fetch(`/api/plan/${planId}/gantt`),
      fetch(`/api/plan/${planId}/graph?format=mermaid`)
    ])

    report.value = await repRes.json()
    const rawGantt = await ganttRes.json()
    const graphData = await graphRes.json()

    ganttData.value = rawGantt.map((task: any) => ({
      id: task.eid,
      name: task.description,
      start: task.start.substring(0, 19).replace('T', ' '),
      end: task.end.substring(0, 19).replace('T', ' '),
      progress: 100,
      custom_class: task.status === 'critical' ? 'bar-critical' : (task.status === 'overdue' ? 'bar-overdue' : 'bar-normal')
    }))

    await nextTick()

    if (ganttWrapper.value && ganttData.value.length > 0) {
      ganttWrapper.value.innerHTML = ''
      ganttInstance = new Gantt(ganttWrapper.value, ganttData.value, {
        view_mode: 'Hour',
        language: 'en', // 确保强制英文
        custom_popup_html: null,
        scroll_to: ganttData.value[0]?.start
      })
    }

    if (mermaidContainer.value) {
      mermaidContainer.value.innerHTML = graphData.content
      mermaidContainer.value.removeAttribute('data-processed')
      await mermaid.run({ nodes: [mermaidContainer.value] })
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
.gantt-container { background-color: white !important; }
.gantt .grid-header { fill: #f8fafc !important; stroke: #e2e8f0 !important; }
.gantt .grid-row { fill: #ffffff !important; }
.gantt .grid-row:nth-child(even) { fill: #f8fafc !important; }
.gantt .row-line { stroke: #e2e8f0 !important; }
.gantt .tick { stroke: #e2e8f0 !important; }
.gantt .tick.thick { stroke: #cbd5e1 !important; }
.gantt .today-highlight { fill: #eff6ff !important; }

.bar-critical .bar { fill: #f59e0b !important; }
.bar-critical .bar-progress { fill: #d97706 !important; }
.bar-overdue .bar { fill: #ef4444 !important; }
.bar-overdue .bar-progress { fill: #dc2626 !important; }
.bar-normal .bar { fill: #3b82f6 !important; }
.bar-normal .bar-progress { fill: #2563eb !important; }

.gantt .bar-label { fill: #fff !important; font-weight: 500; }
.mermaid svg { max-width: 100% !important; width: 100% !important; min-height: 400px; }
</style>