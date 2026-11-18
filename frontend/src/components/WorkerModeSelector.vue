<template>
  <div class="flex items-center gap-2 bg-gray-50 p-1 rounded-lg border border-gray-200">
    <!-- Infinite -->
    <button 
      @click="setMode('infinite')" 
      :class="modelValue === 'infinite' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'" 
      class="px-3 py-1.5 rounded-md text-xs font-medium transition-all flex flex-col items-center justify-center h-[38px]"
    >
      <span>Infinite</span>
      <span class="text-[10px] text-gray-400 block -mt-0.5">(Needs ≥{{ maxConcurrency || 1 }})</span>
    </button>
    
    <!-- Single -->
    <button 
      @click="setMode('1')" 
      :class="modelValue === '1' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'" 
      class="px-3 py-1.5 rounded-md text-xs font-medium transition-all flex flex-col items-center justify-center h-[38px]"
    >
      <span>Single</span>
      <span class="text-[10px] text-gray-400 block -mt-0.5">(1 Worker)</span>
    </button>

    <!-- Custom -->
    <div 
      @click="setMode('custom')" 
      :class="modelValue === 'custom' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-100'" 
      class="px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer flex flex-col items-center justify-center h-[38px]"
    >
      <span>Custom</span>
      <input 
        v-if="modelValue === 'custom'"
        v-model.number="customCount"
        @click.stop
        @change="triggerChange"
        type="number" min="1"
        class="w-12 h-4 text-[10px] text-center border-b border-blue-300 focus:outline-none bg-transparent"
        placeholder="N"
      />
      <span v-else class="text-[10px] text-gray-400 block -mt-0.5">(N Workers)</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: string
  count: number
  maxConcurrency?: number
}>()

const emit = defineEmits(['update:modelValue', 'update:count', 'change'])

const modelValue = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const customCount = computed({
  get: () => props.count,
  set: (val) => emit('update:count', val)
})

const setMode = (mode: string) => {
  modelValue.value = mode
  emit('change')
}

const triggerChange = () => {
  emit('change')
}
</script>