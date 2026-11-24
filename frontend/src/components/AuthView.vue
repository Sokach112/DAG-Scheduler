<template>
  <div class="min-h-screen bg-[#f7f8fa] flex items-center justify-center p-6">
    <div class="w-full max-w-sm bg-white border border-gray-200 rounded-xl shadow-sm p-7">
      <div class="flex items-center gap-2 mb-6">
        <div class="bg-blue-600 text-white p-1.5 rounded-md">
          <Activity class="w-5 h-5" />
        </div>
        <div>
          <p class="font-bold text-gray-800 tracking-tight">DAG Scheduler</p>
          <p class="text-[11px] text-gray-400">
            {{ needsSetup ? 'First-time setup' : 'Sign in to continue' }}
          </p>
        </div>
      </div>

      <h1 class="text-xl font-semibold text-gray-800">
        {{ needsSetup ? 'Create the administrator account' : 'Welcome back' }}
      </h1>
      <p class="text-xs text-gray-500 mt-1">
        {{ needsSetup
          ? 'This account will own existing workspaces and manage users.'
          : 'Use the account provided by your administrator.' }}
      </p>

      <form class="mt-5 flex flex-col gap-3" @submit.prevent="submit">
        <label class="text-xs text-gray-600">
          Username
          <input
            v-model="username"
            autocomplete="username"
            class="mt-1 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="username"
          />
        </label>

        <label v-if="needsSetup" class="text-xs text-gray-600">
          Display name
          <input
            v-model="displayName"
            class="mt-1 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Your name"
          />
        </label>

        <label class="text-xs text-gray-600">
          Password
          <input
            v-model="password"
            type="password"
            :autocomplete="needsSetup ? 'new-password' : 'current-password'"
            class="mt-1 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="At least 8 characters"
          />
        </label>

        <label v-if="needsSetup" class="text-xs text-gray-600">
          Confirm password
          <input
            v-model="confirmPassword"
            type="password"
            autocomplete="new-password"
            class="mt-1 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Repeat password"
          />
        </label>

        <p v-if="error || localError" class="text-xs text-red-600">{{ error || localError }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="mt-2 w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {{ loading ? 'Please wait…' : (needsSetup ? 'Create admin account' : 'Sign in') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Activity } from 'lucide-vue-next'

const props = defineProps<{
  needsSetup: boolean
  loading: boolean
  error: string
}>()

const emit = defineEmits(['submit'])

const username = ref('')
const displayName = ref('')
const password = ref('')
const confirmPassword = ref('')
const localError = ref('')

const submit = () => {
  localError.value = ''
  if (!username.value.trim()) {
    localError.value = 'Username is required.'
    return
  }
  if (password.value.length < 8) {
    localError.value = 'Password must be at least 8 characters.'
    return
  }
  if (props.needsSetup && password.value !== confirmPassword.value) {
    localError.value = 'Passwords do not match.'
    return
  }
  emit('submit', {
    username: username.value.trim(),
    displayName: displayName.value.trim(),
    password: password.value
  })
}
</script>
