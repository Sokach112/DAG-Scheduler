<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-[480px] flex flex-col overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <h3 class="text-lg font-semibold text-gray-800">{{ isEditing ? 'Edit Task' : 'New Task' }}</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600"><X class="w-5 h-5"/></button>
      </div>
      
      <div class="p-6 flex flex-col gap-4 overflow-y-auto max-h-[70vh]">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Description</label>
          <input v-model="form.description" type="text" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.description ? 'border-red-500' : 'border-gray-300'" placeholder="e.g. Frontend Development" />
          <p v-if="formErrors.description" class="text-xs text-red-500 mt-1">{{ formErrors.description }}</p>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Details (Optional)</label>
          <textarea v-model="form.details" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" placeholder="Add extra notes..."></textarea>
        </div>

        <div class="flex gap-4">
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Duration (e.g. 2h 30m)</label>
            <input v-model="form.durationStr" @change="parseDuration" type="text" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.durationStr ? 'border-red-500' : 'border-gray-300'" />
            <p class="text-[11px] text-gray-400 mt-1">Total: {{ form.duration }} mins</p>
          </div>
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Priority</label>
            <input v-model.number="form.priority" type="number" class="w-full px-3 py-2 border rounded-md sm:text-sm" />
          </div>
        </div>

        <div class="flex gap-4">
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Start Time</label>
            <input v-model="form.startStr" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm" />
          </div>
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Deadline</label>
            <input v-model="form.deadlineStr" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.deadlineStr ? 'border-red-500' : 'border-gray-300'" />
            <p v-if="formErrors.deadlineStr" class="text-xs text-red-500 mt-1">{{ formErrors.deadlineStr }}</p>
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Dependencies</label>
          <div class="w-full max-h-32 overflow-y-auto border border-gray-300 rounded-md p-2 bg-gray-50 flex flex-col gap-1">
            <div v-if="availableDependencies.length === 0" class="text-xs text-gray-400 italic">No other tasks.</div>
            <label v-for="t in availableDependencies" :key="t.eid" class="flex items-center gap-2 px-2 py-1.5 hover:bg-gray-100 rounded cursor-pointer min-w-max">
              <input type="checkbox" :value="t.eid" v-model="form.dependencies" class="rounded text-blue-600" />
              <span class="text-xs font-semibold text-gray-600 shrink-0">{{ t.eid }}</span>
              <span class="text-xs text-gray-800 truncate max-w-[150px]">{{ t.description }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-between items-center">
        <button v-if="isEditing" @click="$emit('delete', form.eid)" class="text-red-500 hover:text-red-700 text-sm font-medium">Delete</button>
        <div v-else></div>
        <div class="flex gap-3">
          <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md">Cancel</button>
          <button @click="submitForm" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{
  isOpen: boolean
  isEditing: boolean
  initialData: any
  tasks: any[]
}>()

const emit = defineEmits(['close', 'save', 'delete'])

const form = ref({ eid: '', description: '', details: '', duration: 60, durationStr: '1h', priority: 1, startStr: '', deadlineStr: '', dependencies: [] })
const formErrors = ref<Record<string, string>>({})

// 监听传入数据
watch(() => props.initialData, (newVal) => {
  if (newVal) form.value = { ...newVal }
}, { immediate: true })

const availableDependencies = computed(() => props.tasks.filter(t => t.eid !== form.value.eid))

// 时间联动
watch([() => form.value.startStr, () => form.value.deadlineStr], ([s, e]) => {
  if (s && e) {
    const diff = new Date(e).getTime() - new Date(s).getTime()
    if (diff > 0) {
      form.value.duration = Math.floor(diff / 60000)
      form.value.durationStr = minsToStr(form.value.duration)
    }
  }
})

const minsToStr = (mins: number) => {
  const d = Math.floor(mins / 1440), h = Math.floor((mins % 1440) / 60), m = mins % 60
  return `${d > 0 ? d + 'd ' : ''}${h > 0 ? h + 'h ' : ''}${m > 0 ? m + 'm' : ''}`.trim() || '0m'
}

const parseDuration = () => {
  const str = form.value.durationStr.toLowerCase()
  let total = 0
  const d = str.match(/(\d+)\s*d/), h = str.match(/(\d+)\s*h/), m = str.match(/(\d+)\s*m/)
  if (d) total += parseInt(d[1]) * 1440
  if (h) total += parseInt(h[1]) * 60
  if (m) total += parseInt(m[1])
  if (total > 0) form.value.duration = total
}

const submitForm = () => {
  formErrors.value = {}
  if (!form.value.description) { formErrors.value.description = 'Required'; return }
  if (new Date(form.value.deadlineStr) <= new Date(form.value.startStr)) { formErrors.value.deadlineStr = 'Must be after start'; return }
  
  // 补全时区
  const submitData = {
    ...form.value,
    start: form.value.startStr + ':00+08:00',
    deadline: form.value.deadlineStr + ':00+08:00'
  }
  emit('save', submitData)
}
</script>