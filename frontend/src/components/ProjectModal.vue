<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-[480px] flex flex-col overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <h3 class="text-lg font-semibold text-gray-800">{{ isEditing ? 'Edit Project' : 'New Project' }}</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600"><X class="w-5 h-5"/></button>
      </div>
      
      <div class="p-6 flex flex-col gap-4">
        <!-- Title -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Project Title</label>
          <input v-model="form.title" type="text" class="w-full px-3 py-2 border rounded-md sm:text-sm focus:ring-blue-500" placeholder="e.g. Website Redesign" />
          <p v-if="error" class="text-xs text-red-500 mt-1">{{ error }}</p>
        </div>

        <!-- Description -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Description (Optional)</label>
          <textarea v-model="form.description" rows="3" class="w-full px-3 py-2 border rounded-md sm:text-sm focus:ring-blue-500" placeholder="Add some details about this project..."></textarea>
        </div>

        <!-- Time Bounds -->
        <div class="flex gap-4">
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Start Date</label>
            <input v-model="form.origin" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm focus:ring-blue-500" />
          </div>
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Target Date</label>
            <input v-model="form.ddl" type="datetime-local" class="w-full px-3 py-2 border rounded-md sm:text-sm focus:ring-blue-500" />
          </div>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end gap-3">
        <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">Cancel</button>
        <button @click="submit" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">{{ isEditing ? 'Save Changes' : 'Create Project' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{
  isOpen: boolean
  isEditing?: boolean
  initialData?: any
}>()

const emit = defineEmits(['close', 'save'])

const error = ref('')

const getToday = () => {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
const today = getToday()

const form = ref({
  title: '',
  description: '',
  origin: `${today}T00:00`,
  ddl: `${today}T23:59`
})

// Monitor open data and fill in the table
watch([() => props.isOpen, () => props.initialData], () => {
  if (props.isOpen) {
    error.value = ''
    if (props.isEditing && props.initialData) {
      // Edit mode
      const cutTime = (isoStr: string | null) => {
        if (!isoStr) return ''
        return isoStr.substring(0, 16)
      }
      
      form.value = {
        title: props.initialData.title,
        description: props.initialData.description || '',
        origin: cutTime(props.initialData.origin) || `${today}T00:00`,
        ddl: cutTime(props.initialData.ddl) || `${today}T23:59`
      }
    } else {
      form.value = {
        title: '',
        description: '',
        origin: `${today}T00:00`,
        ddl: `${today}T23:59`
      }
    }
  }
}, { immediate: true })

const submit = () => {
  if (!form.value.title.trim()) { error.value = 'Title is required'; return }
  
  const payload: any = {
    title: form.value.title,
    description: form.value.description
  }
  
  if (form.value.origin) {
    payload.origin = form.value.origin.length === 16 ? form.value.origin + ':00+08:00' : form.value.origin
  }
  if (form.value.ddl) {
    payload.ddl = form.value.ddl.length === 16 ? form.value.ddl + ':00+08:00' : form.value.ddl
  }

  emit('save', payload)
}
</script>