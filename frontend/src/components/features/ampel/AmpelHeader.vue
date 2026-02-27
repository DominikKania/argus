<template>
  <div class="ampel-header">
    <div class="header-left">
      <div class="date-info">
        <h1 class="date-title">{{ analysis.date }}</h1>
        <span v-if="analysis.weekday" class="weekday">{{ analysis.weekday }}</span>
      </div>
      <div class="rating-badge" :class="ratingColorClass">
        <span class="rating-label">{{ ratingLabel }}</span>
      </div>
      <span class="score-info">{{ analysis.rating.mechanical_score }}/4 Signale</span>
    </div>
    <div class="header-right">
      <div class="action-chip" :class="actionColorClass">
        <i :class="actionIcon" />
        <span>{{ actionLabel }}</span>
      </div>
      <div v-if="analysis.crash_rule_active" class="crash-warning">
        <i class="pi pi-exclamation-triangle" />
        <span>Crash-Rule aktiv</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Analysis, OverallRating, ActionType } from '@/types/ampel'

const props = defineProps<{
  analysis: Analysis
}>()

const ratingMap: Record<OverallRating, { label: string; css: string }> = {
  GREEN: { label: 'GRÜN', css: 'rating-green' },
  GREEN_FRAGILE: { label: 'GRÜN (fragil)', css: 'rating-green-fragile' },
  YELLOW: { label: 'GELB', css: 'rating-yellow' },
  YELLOW_BEARISH: { label: 'GELB (bärisch)', css: 'rating-yellow' },
  RED: { label: 'ROT', css: 'rating-red' },
  RED_CAPITULATION: { label: 'ROT (Kapitulation)', css: 'rating-red' },
}

const actionMap: Record<ActionType, { label: string; icon: string; css: string }> = {
  hold: { label: 'Halten', icon: 'pi pi-pause-circle', css: 'action-hold' },
  buy: { label: 'Kaufen', icon: 'pi pi-arrow-up', css: 'action-buy' },
  partial_sell: { label: 'Teilverkauf', icon: 'pi pi-arrow-down', css: 'action-sell' },
  hedge: { label: 'Absichern', icon: 'pi pi-shield', css: 'action-hedge' },
  wait: { label: 'Abwarten', icon: 'pi pi-clock', css: 'action-wait' },
}

const rating = computed(() => ratingMap[props.analysis.rating.overall] || ratingMap.YELLOW)
const action = computed(() => actionMap[props.analysis.recommendation.action] || actionMap.hold)

const ratingLabel = computed(() => rating.value.label)
const ratingColorClass = computed(() => rating.value.css)
const actionLabel = computed(() => action.value.label)
const actionIcon = computed(() => action.value.icon)
const actionColorClass = computed(() => action.value.css)
</script>

<style lang="scss" scoped>
.ampel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.date-info {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.date-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);
  margin: 0;
}

.weekday {
  font-size: 0.875rem;
  color: var(--p-text-color-secondary);
}

.score-info {
  font-size: 0.8125rem;
  color: var(--p-text-color-secondary);
}

.rating-badge {
  padding: 0.375rem 1rem;
  border-radius: 8px;
  font-weight: 700;
  font-size: 0.875rem;
  letter-spacing: 0.025em;

  &.rating-green {
    background-color: rgba(16, 185, 129, 0.15);
    color: #059669;
    :root.dark & { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  }
  &.rating-green-fragile {
    background-color: rgba(16, 185, 129, 0.1);
    color: #059669;
    border: 1px dashed #10b981;
    :root.dark & { background-color: rgba(16, 185, 129, 0.15); color: #6ee7b7; border-color: #6ee7b7; }
  }
  &.rating-yellow {
    background-color: rgba(245, 158, 11, 0.15);
    color: #d97706;
    :root.dark & { background-color: rgba(245, 158, 11, 0.2); color: #fcd34d; }
  }
  &.rating-red {
    background-color: rgba(239, 68, 68, 0.15);
    color: #dc2626;
    :root.dark & { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.action-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 1rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;

  &.action-hold {
    background-color: rgba(99, 102, 241, 0.12);
    color: #4f46e5;
    :root.dark & { background-color: rgba(99, 102, 241, 0.2); color: #a5b4fc; }
  }
  &.action-buy {
    background-color: rgba(16, 185, 129, 0.12);
    color: #059669;
    :root.dark & { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  }
  &.action-sell {
    background-color: rgba(239, 68, 68, 0.12);
    color: #dc2626;
    :root.dark & { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  }
  &.action-hedge {
    background-color: rgba(245, 158, 11, 0.12);
    color: #d97706;
    :root.dark & { background-color: rgba(245, 158, 11, 0.2); color: #fcd34d; }
  }
  &.action-wait {
    background-color: rgba(107, 114, 128, 0.12);
    color: #4b5563;
    :root.dark & { background-color: rgba(107, 114, 128, 0.2); color: #d1d5db; }
  }
}

.crash-warning {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 8px;
  background-color: rgba(239, 68, 68, 0.15);
  color: #dc2626;
  font-weight: 600;
  font-size: 0.8125rem;
  animation: pulse-warning 2s infinite;
  :root.dark & { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }
}

@keyframes pulse-warning {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
</style>
