<template>
  <div class="absolute inset-0 p-6 overflow-auto bg-[#f7f8fa]">
    <div class="bg-white p-6 rounded-xl border border-gray-200 shadow-sm min-w-[800px]">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-base font-semibold text-gray-800">
          {{ effectiveWorkers === 'infinite' 
              ? 'Task Timeline (Infinite)' 
              : effectiveWorkers === '1' ? `Resource Schedule (1 Worker)`
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
</template>

<script setup lang="ts">
defineProps<{
  ganttData: any[]
  scheduledTasks: any[]
  effectiveWorkers: string
  timeMarkers: any[]
  globalSpan: number
  loading: boolean
}>()
</script>