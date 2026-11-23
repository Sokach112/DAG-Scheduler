<template>
  <div v-if="conflict" class="fixed inset-0 bg-black/50 flex items-center justify-center z-[120] p-6">
    <div class="bg-white rounded-xl shadow-xl w-[620px] max-h-[85vh] flex flex-col">
      <div class="px-6 py-4 border-b border-gray-100">
        <h3 class="text-lg font-semibold text-gray-800">Project changed in another session</h3>
        <p class="text-sm text-gray-600 mt-1">
          <strong>{{ conflict.title }}</strong> was updated after you loaded it.
          Review the conflicting fields below.
        </p>
      </div>

      <div class="p-6 overflow-y-auto flex flex-col gap-3">
        <div v-if="!conflict.conflicts.length" class="text-sm text-green-700 bg-green-50 border border-green-100 rounded-md px-3 py-2">
          No conflicting fields. Your changes can be merged automatically.
        </div>

        <div
          v-for="item in conflict.conflicts"
          :key="item.key"
          class="border border-gray-200 rounded-lg p-3"
        >
          <p class="text-xs font-semibold text-gray-700 mb-2">{{ item.label }}</p>
          <div class="grid grid-cols-2 gap-2">
            <label class="border rounded-md p-2 cursor-pointer text-xs" :class="choices[item.key] === 'mine' ? 'border-blue-400 bg-blue-50' : 'border-gray-200'">
              <input v-model="choices[item.key]" type="radio" :value="'mine'" class="mr-1" />
              <span class="font-medium">Mine</span>
              <span class="block text-gray-500 mt-1 break-words">{{ display(item.local) }}</span>
            </label>
            <label class="border rounded-md p-2 cursor-pointer text-xs" :class="choices[item.key] === 'theirs' ? 'border-blue-400 bg-blue-50' : 'border-gray-200'">
              <input v-model="choices[item.key]" type="radio" :value="'theirs'" class="mr-1" />
              <span class="font-medium">Theirs</span>
              <span class="block text-gray-500 mt-1 break-words">{{ display(item.remote) }}</span>
            </label>
          </div>
        </div>

        <p v-if="!conflict.canMerge" class="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-md p-2">
          This project is not open in the editor, so only the latest server version can be reloaded.
        </p>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex flex-wrap justify-end gap-2">
        <button @click="$emit('reload')" class="px-3 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">
          Reload theirs
        </button>
        <button
          v-if="conflict.canMerge"
          @click="$emit('overwrite')"
          class="px-3 py-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md hover:bg-red-100"
        >
          Overwrite mine
        </button>
        <button
          v-if="conflict.canMerge"
          @click="$emit('apply', choices)"
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          Apply merge
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  conflict: any
}>()

const emit = defineEmits(['apply', 'overwrite', 'reload'])

const choices = ref<Record<string, 'mine' | 'theirs'>>({})

watch(
  () => props.conflict,
  () => {
    const next: Record<string, 'mine' | 'theirs'> = {}
    for (const item of props.conflict?.conflicts || []) {
      next[item.key] = 'theirs'
    }
    choices.value = next
  },
  { immediate: true }
)

const display = (value: any) => {
  if (value === undefined || value === null) return 'Deleted / empty'
  if (typeof value === 'string') return value || 'Empty'
  if (typeof value === 'object' && value.description) {
    return `${value.description} · ${value.duration}m · ${value.start || ''}`
  }
  return JSON.stringify(value)
}
</script>
