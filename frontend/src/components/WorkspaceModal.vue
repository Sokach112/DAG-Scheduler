<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-[480px] flex flex-col overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <h3 class="text-lg font-semibold text-gray-800">
          {{ isEditing ? 'Edit Workspace' : 'New Workspace' }}
        </h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600">
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 flex flex-col gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Workspace Name</label>
          <input
            v-model="form.name"
            type="text"
            class="w-full px-3 py-2 border rounded-md sm:text-sm focus:ring-blue-500"
            :class="error ? 'border-red-500' : 'border-gray-300'"
            placeholder="e.g. Engineering"
          />
          <p v-if="error" class="text-xs text-red-500 mt-1">{{ error }}</p>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Description (Optional)</label>
          <textarea
            v-model="form.description"
            rows="3"
            class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500"
            placeholder="What is this workspace for?"
          ></textarea>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end gap-3">
        <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">
          Cancel
        </button>
        <button @click="submit" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">
          {{ isEditing ? 'Save Changes' : 'Create Workspace' }}
        </button>
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

const form = ref({ name: '', description: '' })
const error = ref('')

watch([() => props.isOpen, () => props.initialData], () => {
  if (!props.isOpen) return
  error.value = ''
  form.value = {
    name: props.isEditing ? (props.initialData?.name || '') : '',
    description: props.isEditing ? (props.initialData?.description || '') : ''
  }
}, { immediate: true })

const submit = () => {
  if (!form.value.name.trim()) {
    error.value = 'Workspace name is required'
    return
  }
  error.value = ''
  emit('save', {
    name: form.value.name.trim(),
    description: form.value.description
  })
}
</script>
