<template>
  <div class="prompt-kontext-view">
    <PromptModule />
  </div>
</template>

<script setup lang="ts">
import PromptModule from '@/components/features/ampel/PromptModule.vue'
</script>

<style lang="scss" scoped>
.prompt-kontext-view {
  padding: 1.5rem;
  max-width: 1200px;
  overflow-y: auto;

  @media screen and (max-width: 640px) {
    padding: 1rem;
  }
}
</style>
