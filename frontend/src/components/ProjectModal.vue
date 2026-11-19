<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-[520px] flex flex-col overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <h3 class="text-lg font-semibold text-gray-800">Project Settings</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600"><X class="w-5 h-5"/></button>
      </div>

      <div class="p-6 flex flex-col gap-4 overflow-y-auto max-h-[70vh]">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Title</label>
          <input v-model="form.title" type="text" class="w-full px-3 py-2 border rounded-md sm:text-sm" :class="titleError ? 'border-red-500' : 'border-gray-300'" placeholder="Project title" />
          <p v-if="titleError" class="text-xs text-red-500 mt-1">{{ titleError }}</p>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Description</label>
          <textarea v-model="form.description" rows="3" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" placeholder="Project notes..."></textarea>
        </div>

        <div class="flex gap-4">
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Origin</label>
            <input v-model="form.origin" type="datetime-local" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" />
          </div>
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Project Deadline</label>
            <input v-model="form.ddl" type="datetime-local" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" />
          </div>
        </div>
        <p class="text-[11px] text-gray-400 -mt-2">
          Origin is the scheduling time base; leave it empty to auto-detect. The project deadline is reserved for global overdue checks.
        </p>

        <p v-if="error" class="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{{ error }}</p>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-between items-center">
        <button @click="$emit('delete')" class="text-red-500 hover:text-red-700 text-sm font-medium">Delete</button>
        <div class="flex gap-3">
          <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">Cancel</button>
          <button @click="submit" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">Save</button>
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
  project: any
  error?: string
}>()

const emit = defineEmits(['close', 'save', 'delete'])

const form = ref({ title: '', description: '', origin: '', ddl: '' })
const titleError = ref('')

const toInput = (value?: string) => {
  if (!value) return ''
  return value.length >= 16 ? value.slice(0, 16) : value
}

const reset = () => {
  form.value = {
    title: props.project?.title || '',
    description: props.project?.description || '',
    origin: toInput(props.project?.origin),
    ddl: toInput(props.project?.ddl)
  }
  titleError.value = ''
}

watch([() => props.isOpen, () => props.project], ([open]) => {
  if (open) reset()
}, { immediate: true })

const submit = () => {
  if (!form.value.title.trim()) {
    titleError.value = 'Title is required'
    return
  }
  titleError.value = ''
  emit('save', {
    title: form.value.title.trim(),
    description: form.value.description,
    origin: form.value.origin ? form.value.origin + ':00+08:00' : null,
    ddl: form.value.ddl ? form.value.ddl + ':00+08:00' : null
  })
}
</script>
