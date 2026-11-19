<template>
  <div class="absolute inset-0 p-6 overflow-auto bg-[#f7f8fa]">
    <div class="bg-white p-8 rounded-xl border border-gray-200 shadow-sm min-h-full inline-block min-w-full overflow-auto">
      <div ref="mermaidContainer" class="mermaid"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import mermaid from 'mermaid'

mermaid.initialize({ 
  startOnLoad: false, 
  theme: 'default', 
  flowchart: { useMaxWidth: false, htmlLabels: true, curve: 'basis' } 
})

const props = defineProps<{ mermaidCode: string }>()
const mermaidContainer = ref<HTMLElement | null>(null)

const renderGraph = async () => {
  if (!props.mermaidCode || !mermaidContainer.value) return
  
  await nextTick()
  mermaidContainer.value.innerHTML = ''
  mermaidContainer.value.removeAttribute('data-processed')
  
  try {
    const { svg } = await mermaid.render('mermaid-svg-' + Date.now(), props.mermaidCode)
    if (mermaidContainer.value) {
      mermaidContainer.value.innerHTML = svg
    }
  } catch (err) {
    console.error("Mermaid render error:", err)
  }
}

watch(() => props.mermaidCode, renderGraph, { immediate: true })
</script>

<style scoped>
.mermaid { 
  display: flex; 
  justify-content: flex-start; 
  padding: 20px; 
}
:deep(.mermaid svg) {
  max-width: none !important;
  width: auto !important;
  height: auto !important;
}
</style>