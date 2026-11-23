<template>
  <div class="relative" :class="compact ? 'inline-block' : 'w-full'">
    <div class="relative">
      <input
        ref="inputRef"
        :value="query"
        type="text"
        autocomplete="off"
        :placeholder="placeholder || 'Select workspace'"
        :class="[inputBaseClass, error ? 'border-red-400 bg-red-50 text-red-600' : 'border-gray-300 bg-white']"
        @focus="onFocus"
        @input="onInput"
        @blur="onBlur"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="onEnter"
        @keydown.esc.prevent="cancel"
      />
      <button
        type="button"
        class="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
        title="Choose workspace"
        @mousedown.prevent
        @click="toggle"
      >
        <ChevronDown :class="compact ? 'w-3 h-3' : 'w-4 h-4'" />
      </button>
    </div>

    <div
      v-if="open"
      class="absolute left-0 top-full z-50 mt-1 max-h-56 overflow-y-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
      :class="compact ? 'w-56' : 'w-full'"
      @mousedown.prevent
    >
      <button
        v-for="(workspace, index) in options"
        :key="workspace.wsid"
        type="button"
        class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs"
        :class="[
          index === highlighted ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-50',
          workspace.wsid === modelValue ? 'font-medium' : ''
        ]"
        @click="select(workspace)"
      >
        <span class="truncate">{{ workspace.name }}</span>
        <Check v-if="workspace.wsid === modelValue" class="w-3.5 h-3.5 shrink-0 text-blue-600" />
      </button>
      <div v-if="options.length === 0" class="px-3 py-2 text-xs italic text-gray-400">
        No workspaces found
      </div>
    </div>

    <p v-if="error" class="mt-1 text-[10px] text-red-500">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, ChevronDown } from 'lucide-vue-next'

const props = defineProps<{
  workspaces: any[]
  modelValue: string | null
  compact?: boolean
  placeholder?: string
}>()

const emit = defineEmits(['update:modelValue', 'change'])

const query = ref('')
const open = ref(false)
const error = ref('')
const filtering = ref(false)
const highlighted = ref(-1)
const inputRef = ref<HTMLInputElement | null>(null)

const currentWorkspace = computed(() =>
  (props.workspaces || []).find(w => w.wsid === props.modelValue) || null
)

const options = computed(() => {
  const list = props.workspaces || []
  if (!filtering.value) return list
  const term = query.value.trim().toLowerCase()
  if (!term) return list
  return list.filter(
    w => (w.name || '').toLowerCase().includes(term))
})

const inputBaseClass = computed(() => props.compact
  ? 'h-6 w-36 rounded border pl-2 pr-7 text-[11px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500'
  : 'w-full px-3 py-2 pr-8 border rounded-md sm:text-sm focus:outline-none focus:ring-1 focus:ring-blue-500')

watch(
  [
    () => props.modelValue,
    () => (props.workspaces || []).map(
      w => `${w.wsid}:${w.name}`).join('|')
  ],
  () => {
    if (open.value) return
    query.value = currentWorkspace.value?.name || ''
    error.value = ''
  },
  { immediate: true }
)

const findExactWorkspace = (value: string) => {
  const target = value.trim().toLowerCase()
  if (!target) return null
  return (props.workspaces || []).find(
    w => (w.name || '').trim().toLowerCase() === target) || null
}

const openDropdown = (showAll = true) => {
  open.value = true
  filtering.value = !showAll
  error.value = ''
  const index = options.value.findIndex(w => w.wsid === props.modelValue)
  highlighted.value = index >= 0 ? index : (options.value.length ? 0 : -1)
}

const onFocus = () => {
  if (!open.value) openDropdown(true)
}

const onInput = (event: Event) => {
  query.value = (event.target as HTMLInputElement).value
  open.value = true
  filtering.value = true
  error.value = ''
  highlighted.value = options.value.length ? 0 : -1
}

const select = (workspace: any) => {
  query.value = workspace.name
  error.value = ''
  open.value = false
  if (workspace.wsid !== props.modelValue) {
    emit('update:modelValue', workspace.wsid)
    emit('change', workspace)
  }
}

const validate = (): string | null => {
  const exact = findExactWorkspace(query.value)
  if (!exact) {
    error.value = 'Workspace not found'
    return null
  }

  error.value = ''
  query.value = exact.name
  if (exact.wsid !== props.modelValue) {
    emit('update:modelValue', exact.wsid)
    emit('change', exact)
  }
  return exact.wsid
}

const commit = () => {
  validate()
  open.value = false
}

const onBlur = () => commit()

const cancel = () => {
  query.value = currentWorkspace.value?.name || ''
  error.value = ''
  open.value = false
}

const toggle = () => {
  if (open.value) {
    commit()
    return
  }
  inputRef.value?.focus()
  openDropdown(true)
}

const move = (delta: number) => {
  if (!open.value) {
    openDropdown(true)
    return
  }
  if (!options.value.length) return
  highlighted.value = (
    highlighted.value + delta + options.value.length
  ) % options.value.length
}

const onEnter = () => {
  if (open.value && highlighted.value >= 0) {
    const workspace = options.value[highlighted.value]
    if (workspace) {
      select(workspace)
      return
    }
  }
  commit()
}

defineExpose({ validate })
</script>
