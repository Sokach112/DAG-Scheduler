<template>
  <aside class="w-[35%] min-w-[360px] max-w-[500px] bg-white border-r border-gray-200 flex flex-col shadow-sm">
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/50">
      <!-- 左边：全选和标题 -->
      <div class="flex items-center gap-3">
        <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" class="rounded text-blue-600 w-4 h-4 cursor-pointer" />
        <h2 class="text-sm font-medium text-gray-700 flex items-center gap-2">
          <ListTodo class="w-4 h-4 text-gray-400" /> Task List ({{ tasks.length }})
        </h2>
      </div>
      
      <!-- 右边：按钮组 (加上 shrink-0 防止挤压) -->
      <div class="flex gap-2 items-center shrink-0">
        <button v-if="selectedEids.length > 0" @click="batchDelete" class="flex items-center gap-1 bg-red-50 text-red-600 border border-red-200 px-2 py-1.5 rounded text-sm">
          <Trash2 class="w-4 h-4" /> Delete ({{ selectedEids.length }})
        </button>
        
        <input type="file" ref="fileInput" @change="importJson" accept=".json" class="hidden" />
        <button @click="fileInput?.click()" class="p-1.5 border rounded hover:bg-gray-50 text-gray-600" title="Import JSON">
          <Upload class="w-4 h-4" />
        </button>
        <button @click="exportJson" class="p-1.5 border rounded hover:bg-gray-50 text-gray-600" title="Export JSON">
          <Download class="w-4 h-4" />
        </button>
        
        <!-- 修复：使用 flex items-center gap-1 并加上 whitespace-nowrap 确保换行不被压扁 -->
        <button @click="$emit('open-new')" class="flex items-center gap-1 px-3 py-1.5 border border-gray-300 rounded text-sm font-medium hover:bg-gray-50 text-gray-700 whitespace-nowrap shrink-0">
          <Plus class="w-4 h-4" /> New
        </button>
      </div>
    </div>
    
    <div class="flex-1 overflow-y-auto p-4 bg-[#fafafa] flex flex-col gap-2">
      <div v-for="task in tasks" :key="task.eid" @click="$emit('edit', task)" class="bg-white p-3 border rounded-lg shadow-sm hover:border-blue-400 cursor-pointer flex items-start gap-3" :class="selectedEids.includes(task.eid) ? 'border-blue-400 bg-blue-50/30' : 'border-gray-200'">
        <div @click.stop class="pt-0.5">
          <input type="checkbox" :value="task.eid" :checked="selectedEids.includes(task.eid)" @change="toggleSelect(task.eid)" class="rounded text-blue-600 w-4 h-4" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="font-semibold text-gray-800 text-sm truncate">{{ task.description }}</span>
            <span class="text-gray-500 text-xs shrink-0">{{ task.eid }}</span>
          </div>
          <div class="text-xs text-gray-400 mt-1 font-mono truncate">{{ task.start.substring(0, 16).replace('T', ' ') }} ~ {{ task.deadline.substring(0, 16).replace('T', ' ') }}</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ListTodo, Trash2, Upload, Download, Plus } from 'lucide-vue-next'

const props = defineProps<{ tasks: any[] }>()
const emit = defineEmits(['edit', 'open-new', 'update:tasks'])

const fileInput = ref<HTMLInputElement | null>(null)
const selectedEids = ref<string[]>([])
const isAllSelected = computed(() => props.tasks.length > 0 && selectedEids.value.length === props.tasks.length)

const toggleSelectAll = () => {
  selectedEids.value = isAllSelected.value ? [] : props.tasks.map(t => t.eid)
}
const toggleSelect = (eid: string) => {
  const idx = selectedEids.value.indexOf(eid)
  idx > -1 ? selectedEids.value.splice(idx, 1) : selectedEids.value.push(eid)
}
const batchDelete = () => {
  if (!confirm(`Delete ${selectedEids.value.length} tasks?`)) return
  emit('update:tasks', props.tasks.filter(t => !selectedEids.value.includes(t.eid)))
  selectedEids.value = []
}

const exportJson = () => {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ version: 1, events: props.tasks }, null, 2))
  const a = document.createElement('a')
  a.href = dataStr
  a.download = `plan-${new Date().toISOString().slice(0,10)}.json`
  a.click()
}
const importJson = (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (ev) => {
    try {
      const data = JSON.parse(ev.target?.result as string)
      if (data.events) emit('update:tasks', data.events)
    } catch (err) { alert("Invalid JSON") }
  }
  reader.readAsText(file)
}
</script>