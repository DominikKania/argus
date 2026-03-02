<template>
  <div class="recommendation-card">
    <h3 class="section-title">
      <i class="pi pi-directions" />
      Empfehlung & Eskalation
      <button class="chat-trigger" v-tooltip.top="'Frag den Tutor'" @click="askAbout">
        <i class="pi pi-comments" />
      </button>
    </h3>

    <div class="recommendation-detail">
      <p class="detail-text">{{ analysis.recommendation.detail }}</p>
    </div>

    <div v-if="analysis.rating.reasoning" class="reasoning">
      <h4 class="sub-title">Begründung</h4>
      <p class="reasoning-text">{{ analysis.rating.reasoning }}</p>
    </div>

    <div v-if="analysis.escalation_trigger" class="escalation">
      <h4 class="sub-title escalation-title">
        <i class="pi pi-exclamation-triangle" />
        Eskalations-Trigger
      </h4>
      <p class="escalation-text">{{ analysis.escalation_trigger }}</p>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Analysis } from '@/types/ampel'
import { useChatStore } from '@/stores/chatStore'

const props = defineProps<{
  analysis: Analysis
}>()

const chatStore = useChatStore()

function askAbout() {
  chatStore.openWithContext(
    `Erkläre mir die aktuelle Empfehlung: ${props.analysis.recommendation.detail}`
  )
}


</script>

<style lang="scss" scoped>
.recommendation-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin: 0 0 1rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--p-surface-border);

  i.pi-directions { color: var(--p-primary-500); font-size: 1.125rem; }
}

.chat-trigger {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 6px;
  color: var(--p-text-color-secondary);
  opacity: 0;
  transition: all 0.15s;
  font-size: 0.875rem;
  margin-left: auto;

  .recommendation-card:hover & { opacity: 0.6; }
  &:hover { opacity: 1 !important; color: var(--p-primary-500); background: var(--p-surface-ground); }
}

.sub-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.5rem 0;
}

.detail-text, .reasoning-text, .escalation-text {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--p-text-color-secondary);
  margin: 0;
}

.recommendation-detail {
  margin-bottom: 1rem;

  .detail-text {
    color: var(--p-text-color);
    font-size: 0.875rem;
  }
}

.reasoning {
  margin-bottom: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
}

.escalation {
  padding: 0.75rem;
  border-radius: 8px;
  background-color: rgba(245, 158, 11, 0.06);
  border: 1px solid rgba(245, 158, 11, 0.15);
  margin-bottom: 1rem;
  :root.dark & { background-color: rgba(245, 158, 11, 0.08); border-color: rgba(245, 158, 11, 0.2); }
}

.escalation-title {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: #d97706;
  :root.dark & { color: #fcd34d; }

  i { font-size: 0.8125rem; }
}


</style>
