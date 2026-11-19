<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-[480px] flex flex-col overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <h3 class="text-lg font-semibold text-gray-800">{{ isEditing ? 'Edit Task' : 'New Task' }}</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600"><X class="w-5 h-5"/></button>
      </div>
      
      <div class="p-6 flex flex-col gap-4 overflow-y-auto max-h-[70vh]">
        <!-- Description -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Description</label>
          <input v-model="form.description" type="text" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.description ? 'border-red-500' : 'border-gray-300'" placeholder="e.g. Frontend Development" />
          <p v-if="formErrors.description" class="text-xs text-red-500 mt-1">{{ formErrors.description }}</p>
        </div>

        <!-- Details -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Details (Optional)</label>
          <textarea v-model="form.details" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" placeholder="Add extra notes..."></textarea>
        </div>

        <!-- Duration -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Duration</label>
          <div class="flex gap-2 items-center">
            <div class="flex items-center border border-gray-300 rounded-md overflow-hidden flex-1 bg-white focus-within:ring-1 focus-within:ring-blue-500">
              <input v-model.number="form.durationDays" @input="updateFromDuration" type="number" min="0" class="w-full px-2 py-2 text-center text-sm focus:outline-none" />
              <span class="pr-2 text-xs text-gray-500 bg-white">d</span>
            </div>
            <div class="flex items-center border border-gray-300 rounded-md overflow-hidden flex-1 bg-white focus-within:ring-1 focus-within:ring-blue-500">
              <input v-model.number="form.durationHours" @input="updateFromDuration" type="number" min="0" max="23" class="w-full px-2 py-2 text-center text-sm focus:outline-none" />
              <span class="pr-2 text-xs text-gray-500 bg-white">h</span>
            </div>
            <div class="flex items-center border border-gray-300 rounded-md overflow-hidden flex-1 bg-white focus-within:ring-1 focus-within:ring-blue-500">
              <input v-model.number="form.durationMins" @input="updateFromDuration" type="number" min="0" max="59" class="w-full px-2 py-2 text-center text-sm focus:outline-none" />
              <span class="pr-2 text-xs text-gray-500 bg-white">m</span>
            </div>
          </div>
          <p class="text-[11px] text-gray-400 mt-1 text-right">Total: {{ form.duration }} mins</p>
        </div>

        <!-- Start & Deadline -->
        <div class="flex gap-4">
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Start Time</label>
            <input v-model="form.startStr" @input="updateFromTimes" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm focus:ring-blue-500" />
          </div>
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Deadline</label>
            <input v-model="form.deadlineStr" @input="updateFromTimes" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="formErrors.deadlineStr ? 'border-red-500 ring-1 ring-red-500' : 'border-gray-300 focus:ring-blue-500'" />
            <p v-if="formErrors.deadlineStr" class="text-xs text-red-500 mt-1 absolute">{{ formErrors.deadlineStr }}</p>
          </div>
        </div>

        <!-- Dependencies -->
        <div class="mt-2">
          <label class="block text-xs font-medium text-gray-700 mb-1">Dependencies</label>
          <div class="w-full max-h-32 overflow-y-auto border border-gray-300 rounded-md p-2 bg-gray-50 flex flex-col gap-1">
            <div v-if="availableDependencies.length === 0" class="text-xs text-gray-400 italic p-1">No other tasks available.</div>
            <label v-for="t in availableDependencies" :key="t.eid" class="flex items-center gap-2 px-2 py-1.5 hover:bg-gray-100 rounded cursor-pointer min-w-max">
              <input type="checkbox" :value="t.eid" v-model="form.dependencies" class="rounded text-blue-600 focus:ring-blue-500" />
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
          <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">Cancel</button>
          <button @click="submitForm" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{
  isOpen: boolean
  isEditing: boolean
  initialData: any
  tasks: any[]
}>()

const emit = defineEmits(['close', 'save', 'delete'])

// 包含了拆分的 duration 字段
const form = ref<any>({ 
  eid: '', description: '', details: '', 
  duration: 1439, durationDays: 0, durationHours: 23, durationMins: 59, // 默认 23h 59m
  priority: 1, startStr: '', deadlineStr: '', dependencies: [] 
})
const formErrors = ref<Record<string, string>>({})

// 获取当天的 YYYY-MM-DDT00:00 和 23:59
const getTodayString = () => {
  const today = new Date()
  const yyyy = today.getFullYear()
  const mm = String(today.getMonth() + 1).padStart(2, '0')
  const dd = String(today.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

// 把总分钟数拆解为天、时、分
const splitDuration = (mins: number) => {
  if (mins < 0) mins = 0
  form.value.durationDays = Math.floor(mins / 1440)
  form.value.durationHours = Math.floor((mins % 1440) / 60)
  form.value.durationMins = mins % 60
}

// Stored tasks keep start/deadline as ISO strings, but datetime-local
// inputs expect "YYYY-MM-DDTHH:mm".
const toDateTimeInput = (value?: string) => {
  if (!value) return ''
  return value.length >= 16 ? value.slice(0, 16) : value
}

const resetForm = (task: any) => {
  formErrors.value = {}
  if (task) {
    form.value = {
      ...task,
      startStr: toDateTimeInput(task.startStr || task.start),
      deadlineStr: toDateTimeInput(task.deadlineStr || task.deadline)
    }
    splitDuration(form.value.duration)
  } else {
    const today = getTodayString()
    form.value = {
      eid: '',
      description: '', details: '',
      duration: 1439, durationDays: 0, durationHours: 23, durationMins: 59,
      priority: 1, startStr: `${today}T00:00`, deadlineStr: `${today}T23:59`, dependencies: []
    }
  }
}

// Reset on every open: watching only initialData misses consecutive "New"
// clicks (it stays null) and would leak the previous task's values.
watch(
  [() => props.isOpen, () => props.initialData],
  ([isOpen, task]) => {
    if (isOpen) resetForm(task)
  },
  { immediate: true }
)

const availableDependencies = computed(() => {
  return props.tasks.filter(t => t.eid !== form.value.eid && t.eid !== '')
})

const updateFromDuration = () => {
  const d = form.value.durationDays || 0
  const h = form.value.durationHours || 0
  const m = form.value.durationMins || 0
  const total = d * 1440 + h * 60 + m
  
  form.value.duration = total
  
  if (form.value.startStr) {
    const start = new Date(form.value.startStr)
    start.setMinutes(start.getMinutes() + total)
    // 格式化回 YYYY-MM-DDTHH:mm
    const pad = (n: number) => String(n).padStart(2, '0')
    form.value.deadlineStr = `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}T${pad(start.getHours())}:${pad(start.getMinutes())}`
  }
}

// 当用户修改 Start/Deadline 时，自动计算 Duration
const updateFromTimes = () => {
  if (form.value.startStr && form.value.deadlineStr) {
    const start = new Date(form.value.startStr).getTime()
    const end = new Date(form.value.deadlineStr).getTime()
    if (end > start) {
      const diff = Math.floor((end - start) / 60000)
      form.value.duration = diff
      splitDuration(diff)
      formErrors.value.deadlineStr = ''
    } else {
      formErrors.value.deadlineStr = 'Must be after Start'
    }
  }
}

const submitForm = () => {
  formErrors.value = {}
  if (!form.value.description) { formErrors.value.description = 'Required'; return }
  if (!form.value.startStr || !form.value.deadlineStr) { formErrors.value.deadlineStr = 'Required'; return }
  
  const start = new Date(form.value.startStr).getTime()
  const end = new Date(form.value.deadlineStr).getTime()
  if (end <= start) { formErrors.value.deadlineStr = 'Must be after Start'; return }
  
  // 移除临时字段，只传必要的给后端
  const submitData = {
    eid: form.value.eid,
    description: form.value.description,
    details: form.value.details,
    duration: form.value.duration,
    priority: form.value.priority,
    dependencies: form.value.dependencies,
    start: form.value.startStr + ':00+08:00',
    deadline: form.value.deadlineStr + ':00+08:00'
  }
  emit('save', submitData)
}
</script>