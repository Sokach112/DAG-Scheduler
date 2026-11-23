<template>
  <div class="absolute inset-0 p-6 overflow-auto bg-[#f7f8fa]">
    <div class="bg-white p-6 rounded-xl border border-gray-200 shadow-sm min-w-[800px]">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-base font-semibold text-gray-800">
          {{ effectiveWorkers === 'infinite'
              ? 'Task Timeline (Infinite)'
              : `Resource Schedule (${workerRows.length} ${workerRows.length === 1 ? 'Worker' : 'Workers'})` }}
        </h2>
        <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">Global Span</span>
      </div>

      <p v-if="capabilityFallbacks?.length" class="text-[11px] text-amber-600 -mt-4 mb-4">
        Capability fallback used for {{ (capabilityFallbacks || []).join(', ') }}: no active capable worker was available.
      </p>

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
          <div v-for="row in workerRows" :key="String(row.id)" class="flex items-center text-sm group">
            <div class="w-48 shrink-0 pr-4 font-semibold text-gray-600 truncate" :title="row.name">{{ row.name }}</div>
            <div class="flex-1 relative h-10 bg-gray-50 rounded border border-gray-100">
              <div 
                v-for="task in scheduledTasks.filter(t => t.workerId === row.id)"
                :key="task.id"
                class="absolute top-1 bottom-1 rounded shadow-sm text-[11px] text-white flex items-center px-2 overflow-hidden"
                :class="task.custom_class"
                :style="{ left: task.leftPct + '%', width: task.widthPct + '%' }"
                :title="`${task.name} (${task.startLabel || task.start.substring(11,16)} - ${task.endLabel || task.end.substring(11,16)})`"
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
              {{ mark.label || (globalSpan > 1440 * 60000 ? mark.time.substring(5, 10) : mark.time.substring(11, 16)) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  ganttData: any[]
  scheduledTasks: any[]
  effectiveWorkers: string
  workerRows?: any[]
  capabilityFallbacks?: string[]
  timeMarkers: any[]
  globalSpan: number
  loading: boolean
}>(), {
  workerRows: () => []
})
</script>