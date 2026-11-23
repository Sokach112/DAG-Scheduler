<template>
  <div class="flex items-center gap-1 bg-gray-50 p-1 rounded-lg border border-gray-200">
    <!-- Infinite -->
    <button
      @click="selectMode('infinite')"
      :class="modelValue === 'infinite' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'"
      class="px-2.5 py-1.5 rounded-md text-xs font-medium transition-all flex flex-col items-center justify-center h-[38px]"
    >
      <span>Infinite</span>
      <span class="text-[10px] text-gray-400 block -mt-0.5">(Needs ≥{{ maxConcurrency || 1 }})</span>
    </button>

    <!-- Single, generic 1 worker -->
    <button
      @click="selectMode('1')"
      :class="modelValue === '1' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'"
      class="px-2.5 py-1.5 rounded-md text-xs font-medium transition-all flex flex-col items-center justify-center h-[38px]"
    >
      <span>Single</span>
      <span class="text-[10px] text-gray-400 block -mt-0.5">(1 Worker)</span>
    </button>

    <!-- Workers N, always generic -->
    <div
      @click="selectMode('workers')"
      :class="modelValue === 'workers' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'"
      class="px-2.5 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer flex flex-col items-center justify-center h-[38px]"
    >
      <span>Workers N</span>
      <template v-if="modelValue === 'workers'">
        <input
          v-model.number="localCount"
          @click.stop
          @input="onCountChange"
          type="number" min="1"
          class="w-10 h-4 text-[10px] text-center border-b border-blue-300 focus:outline-none bg-transparent"
          placeholder="N"
        />
      </template>
      <span v-else class="text-[10px] text-gray-400 block -mt-0.5">(N Workers)</span>
    </div>

    <!-- Team, named roster -->
    <button
      @click="selectMode('team')"
      :class="modelValue === 'team' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'"
      class="px-2.5 py-1.5 rounded-md text-xs font-medium transition-all flex flex-col items-center justify-center h-[38px] max-w-[110px]"
    >
      <span>Team</span>
      <span class="text-[10px] text-gray-400 block -mt-0.5 max-w-[100px] truncate">
        {{ workers.length ? `${workers.length} members` : 'Set up team' }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: string
  count: number
  workers?: any[]
  maxConcurrency?: number
}>()

const emit = defineEmits([
  'update:modelValue',
  'update:count',
  'change'
])

const workers = computed(() => props.workers || [])

const localCount = computed({
  get: () => props.count,
  set: (val) => emit('update:count', val)
})

const selectMode = (mode: string) => {
  emit('update:modelValue', mode)
  emit('change', mode)
}

const onCountChange = () => {
  emit('change', props.modelValue)
}
</script>
