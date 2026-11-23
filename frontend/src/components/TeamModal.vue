<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-[440px] flex flex-col max-h-[90vh]">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <div>
          <h3 class="text-lg font-semibold text-gray-800">Team members</h3>
          <p class="text-[11px] text-gray-400">Only Team mode uses these names.</p>
        </div>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600">
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 flex flex-col gap-2 overflow-y-auto" @keydown.enter="onEnter">
        <div v-for="(worker, index) in form.workers" :key="worker.wid" class="flex items-center gap-2">
          <span class="w-5 text-[11px] text-gray-400 text-right">{{ index + 1 }}</span>
          <input
            v-model="worker.name"
            type="text"
            placeholder="Worker name"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500"
          />
          <label class="flex items-center gap-1 text-[10px] text-gray-500 shrink-0">
            <input
              type="checkbox"
              :checked="isActive(worker.wid)"
              @change="toggleActive(worker.wid, $event)"
              class="rounded text-blue-600 focus:ring-blue-500"
            />
            Active
          </label>
          <button type="button" @click="removeWorker(index)" class="p-1.5 text-gray-400 hover:text-red-500" title="Remove worker">
            <X class="w-4 h-4" />
          </button>
        </div>

        <p v-if="form.workers.length === 0" class="text-xs italic text-gray-400">
          No team members yet. Add names such as Alice, Bob, or Carol.
        </p>

        <button type="button" @click="addWorker" class="mt-1 self-start text-xs font-medium text-blue-600 hover:text-blue-700">
          + Add worker
        </button>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end gap-3">
        <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">Cancel</button>
        <button @click="save" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">Save team</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { isSubmitEnter } from '../utils/keyboard'

const props = defineProps<{
  isOpen: boolean
  workers?: any[]
  activeWorkerIds?: string[]
}>()

const emit = defineEmits(['close', 'save'])

const form = ref<{ workers: any[]; activeIds: string[] }>({
  workers: [],
  activeIds: []
})

const newWorkerId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID().slice(0, 8)
  }
  return `w${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

const addWorker = () => {
  form.value.workers.push({ wid: newWorkerId(), name: '' })
}

const removeWorker = (index: number) => {
  const removed = form.value.workers[index]
  form.value.workers.splice(index, 1)
  if (removed) {
    form.value.activeIds = form.value.activeIds.filter(
      id => id !== removed.wid)
    if (form.value.activeIds.length === 0 && form.value.workers.length) {
      form.value.activeIds = [form.value.workers[0].wid]
    }
  }
}

const isActive = (wid: string) => form.value.activeIds.includes(wid)

const toggleActive = (wid: string, event: Event) => {
  const checked = (event.target as HTMLInputElement).checked
  if (!checked && form.value.activeIds.length === 1) {
    ;(event.target as HTMLInputElement).checked = true
    return
  }
  form.value.activeIds = checked
    ? [...form.value.activeIds, wid]
    : form.value.activeIds.filter(id => id !== wid)
}

watch(
  [() => props.isOpen, () => props.workers],
  () => {
    if (!props.isOpen) return
    const workers = (props.workers || []).map(
      (worker: any) => ({ wid: worker.wid, name: worker.name }))
    const rosterIds = workers.map((worker: any) => worker.wid)
    const saved = (props.activeWorkerIds || []).filter(
      wid => rosterIds.includes(wid))
    form.value = {
      workers,
      activeIds: saved.length ? saved : rosterIds
    }
  },
  { immediate: true, deep: true }
)

const onEnter = (event: KeyboardEvent) => {
  if (!isSubmitEnter(event)) return
  event.preventDefault()
  save()
}

const save = () => {
  const workers = form.value.workers
    .map((worker: any) => ({
      wid: worker.wid,
      name: (worker.name || '').trim()
    }))
    .filter((worker: any) => worker.name)
  const active = form.value.activeIds.filter(
    wid => workers.some((worker: any) => worker.wid === wid))
  emit('save', {
    workers,
    active_worker_ids: active.length ? active : workers.map(w => w.wid)
  })
}
</script>
