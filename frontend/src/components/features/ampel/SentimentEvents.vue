<template>
  <div class="sentiment-events">
    <h3 class="section-title">
      <i class="pi pi-megaphone" />
      Sentiment Events
    </h3>
    <div class="events-list">
      <div
        v-for="(event, index) in events"
        :key="index"
        class="event-item"
        :class="{ 'event-primary': event.is_primary }"
      >
        <div class="event-header">
          <span class="event-headline">{{ event.headline }}</span>
          <div class="event-badges">
            <span class="impact-badge" :class="impactClass(event.affects_portfolio)">
              {{ impactLabel(event.affects_portfolio) }}
            </span>
            <span class="risk-badge" :class="riskClass(event.cascade_risk)">
              {{ riskLabel(event.cascade_risk) }}
            </span>
          </div>
        </div>
        <p v-if="event.summary" class="event-summary">{{ event.summary }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SentimentEvent } from '@/types/ampel'

defineProps<{
  events: SentimentEvent[]
}>()

const impactLabel = (impact?: string) => {
  const map: Record<string, string> = { direct: 'Direkt', sector_only: 'Sektor', indirect: 'Indirekt' }
  return map[impact || ''] || impact || ''
}

const impactClass = (impact?: string) => ({
  'impact-direct': impact === 'direct',
  'impact-sector': impact === 'sector_only',
  'impact-indirect': impact === 'indirect',
})

const riskLabel = (risk?: string) => {
  const map: Record<string, string> = { low: 'Niedrig', medium: 'Mittel', high: 'Hoch' }
  return map[risk || ''] || risk || ''
}

const riskClass = (risk?: string) => ({
  'risk-low': risk === 'low',
  'risk-medium': risk === 'medium',
  'risk-high': risk === 'high',
})
</script>

<style lang="scss" scoped>
.sentiment-events {
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

.events-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.event-item {
  padding: 0.875rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid transparent;

  &.event-primary {
    border-color: var(--p-primary-300);
    :root.dark & { border-color: var(--p-primary-700); }
  }
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.375rem;

  @media screen and (max-width: 640px) {
    flex-direction: column;
    gap: 0.5rem;
  }
}

.event-headline {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-color);
  flex: 1;
}

.event-badges {
  display: flex;
  gap: 0.375rem;
  flex-shrink: 0;
}

.event-summary {
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  margin: 0;
}

.impact-badge, .risk-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  white-space: nowrap;
}

.impact-direct {
  background-color: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  :root.dark & { background-color: rgba(239, 68, 68, 0.15); color: #fca5a5; }
}
.impact-sector {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
  :root.dark & { background-color: rgba(245, 158, 11, 0.15); color: #fcd34d; }
}
.impact-indirect {
  background-color: rgba(107, 114, 128, 0.1);
  color: #4b5563;
  :root.dark & { background-color: rgba(107, 114, 128, 0.15); color: #d1d5db; }
}

.risk-low {
  background-color: rgba(16, 185, 129, 0.1);
  color: #059669;
  :root.dark & { background-color: rgba(16, 185, 129, 0.15); color: #6ee7b7; }
}
.risk-medium {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
  :root.dark & { background-color: rgba(245, 158, 11, 0.15); color: #fcd34d; }
}
.risk-high {
  background-color: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  :root.dark & { background-color: rgba(239, 68, 68, 0.15); color: #fca5a5; }
}
</style>
