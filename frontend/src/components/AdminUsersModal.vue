<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-[115]">
    <div class="bg-white rounded-xl shadow-xl w-[600px] max-h-[85vh] flex flex-col">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
        <div>
          <h3 class="text-lg font-semibold text-gray-800">Users</h3>
          <p class="text-[11px] text-gray-400">Create accounts. Workspace roles control project access.</p>
        </div>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
      </div>

      <div class="p-5 overflow-y-auto flex flex-col gap-4">
        <div class="border border-gray-200 rounded-lg p-3">
          <p class="text-xs font-semibold text-gray-700 mb-2">Create account</p>
          <div class="grid grid-cols-2 gap-2">
            <input v-model="username" placeholder="username" class="border rounded-md px-2.5 py-1.5 text-xs" />
            <input v-model="displayName" placeholder="Display name" class="border rounded-md px-2.5 py-1.5 text-xs" />
            <input v-model="password" type="password" placeholder="Initial password (8+ chars)" class="border rounded-md px-2.5 py-1.5 text-xs" />
            <label class="flex items-center gap-2 text-xs text-gray-600">
              <input v-model="isAdmin" type="checkbox" /> Administrator
            </label>
          </div>
          <div class="flex justify-end mt-2">
            <button @click="createUser" :disabled="creating" class="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-md disabled:opacity-50">
              {{ creating ? 'Creating…' : 'Create user' }}
            </button>
          </div>
          <p v-if="error" class="text-xs text-red-600 mt-2">{{ error }}</p>
        </div>

        <div class="flex flex-col gap-2">
          <p v-if="loading" class="text-xs text-gray-400 italic">Loading users…</p>
          <div v-for="user in users" :key="user.id" class="flex items-center justify-between border border-gray-200 rounded-md px-3 py-2">
            <div>
              <p class="text-xs font-medium text-gray-700">{{ user.display_name }}</p>
              <p class="text-[10px] text-gray-400">@{{ user.username }}</p>
            </div>
            <span class="text-[10px] px-1.5 py-0.5 rounded" :class="user.is_admin ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-500'">
              {{ user.is_admin ? 'admin' : 'member' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits(['close', 'created'])

const users = ref<any[]>([])
const loading = ref(false)
const creating = ref(false)
const error = ref('')
const username = ref('')
const displayName = ref('')
const password = ref('')
const isAdmin = ref(false)

const loadUsers = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/admin/users')
    if (!res.ok) throw new Error(await readError(res))
    users.value = await res.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

const readError = async (res: Response) => {
  try {
    const body = await res.json()
    return typeof body?.error?.detail === 'string'
      ? body.error.detail : `Request failed (${res.status})`
  } catch {
    return `Request failed (${res.status})`
  }
}

const createUser = async () => {
  creating.value = true
  error.value = ''
  try {
    const res = await fetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username.value.trim(),
        display_name: displayName.value.trim(),
        password: password.value,
        is_admin: isAdmin.value
      })
    })
    if (!res.ok) throw new Error(await readError(res))
    username.value = ''
    displayName.value = ''
    password.value = ''
    isAdmin.value = false
    await loadUsers()
    emit('created')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    creating.value = false
  }
}

watch(() => props.isOpen, open => {
  if (open) loadUsers()
})
</script>
