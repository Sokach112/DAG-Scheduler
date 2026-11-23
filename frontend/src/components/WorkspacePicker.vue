<template>
  <div class="flex items-start gap-1.5 text-[11px] min-w-0" @click.stop @mousedown.stop>
    <span class="text-gray-400 shrink-0 mt-1">Workspace</span>
    <WorkspaceSelect
      compact
      :workspaces="workspaces"
      :modelValue="wsid"
      @change="$emit('move', $event.wsid)"
    />
  </div>
</template>

<script setup lang="ts">
import WorkspaceSelect from './WorkspaceSelect.vue'

defineProps<{
  wsid: string | null
  workspaces: any[]
}>()

defineEmits(['move'])
</script>
