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

    <!-- Key Levels -->
    <div v-if="analysis.key_levels" class="key-levels">
      <h4 class="sub-title">Schlüsselmarken</h4>
      <div class="levels-grid">
        <div class="level-item level-support">
          <span class="level-label"><i class="pi pi-arrow-down" /> Unterstützung</span>
          <span class="level-value">{{ analysis.key_levels.support }}</span>
        </div>
        <div class="level-item level-resistance">
          <span class="level-label"><i class="pi pi-arrow-up" /> Widerstand</span>
          <span class="level-value">{{ analysis.key_levels.resistance }}</span>
        </div>
      </div>
      <p v-if="analysis.key_levels.pivot_note" class="pivot-note">{{ analysis.key_levels.pivot_note }}</p>
    </div>

    <!-- Risk Assessment -->
    <div v-if="analysis.risk_assessment" class="risk-assessment">
      <h4 class="sub-title">
        Risikoeinschätzung
        <span :class="['risk-badge', `risk-${analysis.risk_assessment.level}`]">{{ riskLabel }}</span>
      </h4>
      <div class="risk-lists">
        <div v-if="analysis.risk_assessment.primary_risks?.length" class="risk-list">
          <span class="risk-list-label">Risiken:</span>
          <ul>
            <li v-for="r in analysis.risk_assessment.primary_risks" :key="r">{{ r }}</li>
          </ul>
        </div>
        <div v-if="analysis.risk_assessment.mitigating_factors?.length" class="risk-list">
          <span class="risk-list-label">Positive Faktoren:</span>
          <ul>
            <li v-for="f in analysis.risk_assessment.mitigating_factors" :key="f">{{ f }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Action Triggers -->
    <div v-if="analysis.action_triggers" class="action-triggers">
      <h4 class="sub-title">Konkrete Trigger</h4>
      <div class="trigger-items">
        <div class="trigger-item trigger-buy">
          <i class="pi pi-cart-plus" />
          <div>
            <span class="trigger-label">Kaufen wenn:</span>
            <span class="trigger-text">{{ analysis.action_triggers.buy_trigger }}</span>
          </div>
        </div>
        <div class="trigger-item trigger-sell">
          <i class="pi pi-cart-minus" />
          <div>
            <span class="trigger-label">Reduzieren wenn:</span>
            <span class="trigger-text">{{ analysis.action_triggers.sell_trigger }}</span>
          </div>
        </div>
      </div>
      <div v-if="analysis.action_triggers.watch_items?.length" class="watch-items">
        <span class="watch-label"><i class="pi pi-eye" /> Beobachten:</span>
        <ul>
          <li v-for="w in analysis.action_triggers.watch_items" :key="w">{{ w }}</li>
        </ul>
      </div>
    </div>

    <!-- Historical Comparison -->
    <div v-if="analysis.historical_comparison" class="historical">
      <h4 class="sub-title">
        <i class="pi pi-history" />
        Historischer Vergleich
      </h4>
      <p class="historical-text">{{ analysis.historical_comparison }}</p>
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

const riskLabel = computed(() => {
  const map: Record<string, string> = {
    low: 'Niedrig', moderate: 'Moderat', elevated: 'Erhöht', high: 'Hoch', extreme: 'Extrem',
  }
  return map[props.analysis.risk_assessment?.level || ''] || props.analysis.risk_assessment?.level || ''
})

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

// Key Levels
.key-levels {
  margin-bottom: 1rem;
}

.levels-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 0.5rem;

  @media screen and (max-width: 480px) { grid-template-columns: 1fr; }
}

.level-item {
  padding: 0.625rem;
  border-radius: 8px;
  border: 1px solid var(--p-surface-border);
}

.level-support {
  border-left: 3px solid #16a34a;
}

.level-resistance {
  border-left: 3px solid #ef4444;
}

.level-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;

  i { font-size: 0.625rem; }
}

.level-value {
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--p-text-color);
}

.pivot-note {
  font-size: 0.8rem;
  color: var(--p-text-color-secondary);
  margin: 0;
  font-style: italic;
}

// Risk Assessment
.risk-assessment {
  margin-bottom: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
}

.risk-badge {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  text-transform: uppercase;
  margin-left: 0.5rem;

  &.risk-low {
    background: rgba(16, 185, 129, 0.12); color: #059669;
    :root.dark & { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  }
  &.risk-moderate {
    background: rgba(217, 119, 6, 0.12); color: #d97706;
    :root.dark & { background: rgba(217, 119, 6, 0.2); color: #fcd34d; }
  }
  &.risk-elevated {
    background: rgba(249, 115, 22, 0.12); color: #ea580c;
    :root.dark & { background: rgba(249, 115, 22, 0.2); color: #fdba74; }
  }
  &.risk-high, &.risk-extreme {
    background: rgba(239, 68, 68, 0.12); color: #dc2626;
    :root.dark & { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  }
}

.risk-lists {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;

  @media screen and (max-width: 480px) { grid-template-columns: 1fr; }
}

.risk-list-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  margin-bottom: 0.25rem;
}

.risk-list ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--p-text-color);

  li { margin-bottom: 0.125rem; }
}

// Action Triggers
.action-triggers {
  margin-bottom: 1rem;
}

.trigger-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.trigger-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.625rem;
  border-radius: 8px;
  border: 1px solid var(--p-surface-border);

  > i {
    font-size: 0.875rem;
    margin-top: 0.125rem;
    flex-shrink: 0;
  }

  &.trigger-buy > i { color: #16a34a; }
  &.trigger-sell > i { color: #ef4444; }
}

.trigger-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
}

.trigger-text {
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--p-text-color);
}

.watch-items {
  padding: 0.625rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
}

.watch-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  margin-bottom: 0.25rem;

  i { font-size: 0.75rem; }
}

.watch-items ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--p-text-color);

  li { margin-bottom: 0.125rem; }
}

// Historical Comparison
.historical {
  margin-bottom: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border-left: 3px solid var(--p-primary-400);
}

.historical .sub-title {
  display: flex;
  align-items: center;
  gap: 0.375rem;

  i { font-size: 0.8125rem; color: var(--p-primary-500); }
}

.historical-text {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--p-text-color-secondary);
  margin: 0;
}

</style>
