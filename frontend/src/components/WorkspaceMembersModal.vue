<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-[115]">
    <div class="bg-white rounded-xl shadow-xl w-[580px] max-h-[85vh] flex flex-col">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
        <div>
          <h3 class="text-lg font-semibold text-gray-800">Workspace members</h3>
          <p class="text-[11px] text-gray-400">Owners can add members and change roles.</p>
        </div>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
      </div>

      <div class="p-5 overflow-y-auto flex flex-col gap-4">
        <div class="border border-gray-200 rounded-lg p-3">
          <div class="flex gap-2">
            <select v-model="selectedUser" class="flex-1 border rounded-md px-2 py-1.5 text-xs bg-white">
              <option value="">Select user</option>
              <option v-for="user in availableUsers" :key="user.id" :value="user.id">
                {{ user.display_name }} (@{{ user.username }})
              </option>
            </select>
            <select v-model="selectedRole" class="border rounded-md px-2 py-1.5 text-xs bg-white">
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
              <option value="owner">Owner</option>
            </select>
            <button @click="addMember" :disabled="!selectedUser || saving" class="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-md disabled:opacity-50">
              Add
            </button>
          </div>
          <p v-if="error" class="text-xs text-red-600 mt-2">{{ error }}</p>
        </div>

        <p v-if="loading" class="text-xs text-gray-400 italic">Loading members…</p>
        <div v-for="member in members" :key="member.id" class="flex items-center justify-between border border-gray-200 rounded-md px-3 py-2">
          <div>
            <p class="text-xs font-medium text-gray-700">{{ member.display_name }}</p>
            <p class="text-[10px] text-gray-400">@{{ member.username }}</p>
          </div>
          <div class="flex items-center gap-2">
            <select
              :value="member.role"
              @change="updateRole(member, ($event.target as HTMLSelectElement).value)"
              class="border rounded-md px-2 py-1 text-[11px] bg-white"
            >
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
              <option value="owner">Owner</option>
            </select>
            <button @click="removeMember(member)" class="p-1.5 text-gray-400 hover:text-red-500" title="Remove member">
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Trash2 } from 'lucide-vue-next'

const props = defineProps<{
  isOpen: boolean
  wsid: string | null
}>()

const emit = defineEmits(['close', 'changed'])

const members = ref<any[]>([])
const users = ref<any[]>([])
const selectedUser = ref('')
const selectedRole = ref('editor')
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const availableUsers = computed(() => {
  const memberIds = new Set(members.value.map(m => m.id))
  return users.value.filter(u => !memberIds.has(u.id))
})

const readError = async (res: Response) => {
  try {
    const body = await res.json()
    return typeof body?.error?.detail === 'string'
      ? body.error.detail : `Request failed (${res.status})`
  } catch {
    return `Request failed (${res.status})`
  }
}

const load = async () => {
  if (!props.wsid) return
  loading.value = true
  error.value = ''
  try {
    const [memberRes, userRes] = await Promise.all([
      fetch(`/api/workspaces/${props.wsid}/members`),
      fetch('/api/users')
    ])
    if (!memberRes.ok) throw new Error(await readError(memberRes))
    if (!userRes.ok) throw new Error(await readError(userRes))
    members.value = await memberRes.json()
    users.value = await userRes.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

const addMember = async () => {
  saving.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/workspaces/${props.wsid}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: selectedUser.value, role: selectedRole.value })
    })
    if (!res.ok) throw new Error(await readError(res))
    selectedUser.value = ''
    await load()
    emit('changed')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

const updateRole = async (member: any, role: string) => {
  error.value = ''
  try {
    const res = await fetch(
      `/api/workspaces/${props.wsid}/members/${member.id}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role })
      })
    if (!res.ok) throw new Error(await readError(res))
    await load()
    emit('changed')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

const removeMember = async (member: any) => {
  error.value = ''
  try {
    const res = await fetch(
      `/api/workspaces/${props.wsid}/members/${member.id}`,
      { method: 'DELETE' })
    if (!res.ok) throw new Error(await readError(res))
    await load()
    emit('changed')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

watch(() => props.isOpen, open => {
  if (open) load()
})
</script>
