<template>
  <div class="recommendation-card">
    <h3 class="section-title">
      <i class="pi pi-directions" />
      Empfehlung & Eskalation
    </h3>

    <div class="recommendation-detail">
      <p class="detail-text">{{ displayDetail }}</p>
    </div>

    <div v-if="displayReasoning" class="reasoning">
      <h4 class="sub-title">Begründung</h4>
      <p class="reasoning-text">{{ displayReasoning }}</p>
    </div>

    <div v-if="displayEscalation" class="escalation">
      <h4 class="sub-title escalation-title">
        <i class="pi pi-exclamation-triangle" />
        Eskalations-Trigger
      </h4>
      <p class="escalation-text">{{ displayEscalation }}</p>
    </div>

    <div v-if="analysis.beller_check?.triggered" class="beller-check">
      <h4 class="sub-title">Beller-Check</h4>
      <div class="beller-info">
        <span class="beller-badge" :class="bellerClass">
          {{ bellerLabel }}
        </span>
        <span v-if="analysis.beller_check.trigger_type" class="beller-type">
          {{ analysis.beller_check.trigger_type }}
        </span>
      </div>
      <p v-if="displayBellerReasoning" class="beller-reasoning">
        {{ displayBellerReasoning }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Analysis } from '@/types/ampel'
import { useDummyModeStore } from '@/stores/dummyModeStore'

const props = defineProps<{
  analysis: Analysis
}>()

const dummyModeStore = useDummyModeStore()
const s = computed(() => dummyModeStore.isDummyMode ? props.analysis.simplified : null)

const displayDetail = computed(() =>
  s.value?.recommendation_detail || props.analysis.recommendation.detail
)
const displayReasoning = computed(() =>
  s.value?.rating_reasoning || props.analysis.rating.reasoning
)
const displayEscalation = computed(() =>
  s.value?.escalation_trigger || props.analysis.escalation_trigger
)
const displayBellerReasoning = computed(() =>
  s.value?.beller_check_reasoning || props.analysis.beller_check?.reasoning
)

const bellerLabel = computed(() => {
  const map: Record<string, string> = { beller: 'Beller', beisser: 'Beisser', unclear: 'Unklar' }
  return map[props.analysis.beller_check?.classification || ''] || ''
})

const bellerClass = computed(() => ({
  'beller-beller': props.analysis.beller_check?.classification === 'beller',
  'beller-beisser': props.analysis.beller_check?.classification === 'beisser',
  'beller-unclear': props.analysis.beller_check?.classification === 'unclear',
}))
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

  i { color: var(--p-primary-500); font-size: 1.125rem; }
}

.sub-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.5rem 0;
}

.detail-text, .reasoning-text, .escalation-text, .beller-reasoning {
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

.beller-check {
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
}

.beller-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.beller-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 6px;
}

.beller-beller {
  background-color: rgba(16, 185, 129, 0.15);
  color: #059669;
  :root.dark & { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
}
.beller-beisser {
  background-color: rgba(239, 68, 68, 0.15);
  color: #dc2626;
  :root.dark & { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }
}
.beller-unclear {
  background-color: rgba(245, 158, 11, 0.15);
  color: #d97706;
  :root.dark & { background-color: rgba(245, 158, 11, 0.2); color: #fcd34d; }
}

.beller-type {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}
</style>
