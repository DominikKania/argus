<template>
  <div class="thesis-card">
    <h3 class="section-title">
      <i class="pi pi-lightbulb" />
      These
    </h3>
    <p class="thesis-statement">{{ thesis.statement }}</p>
    <div v-if="thesis.catalyst" class="catalyst">
      <span class="catalyst-label">Katalysator:</span>
      <span class="catalyst-text">{{ thesis.catalyst }}</span>
      <span v-if="thesis.catalyst_date" class="catalyst-date">
        <i class="pi pi-calendar" />
        {{ thesis.catalyst_date }}
      </span>
    </div>
    <div class="scenarios">
      <div v-if="thesis.expected_if_positive" class="scenario scenario-positive">
        <span class="scenario-icon">+</span>
        <p class="scenario-text">{{ thesis.expected_if_positive }}</p>
      </div>
      <div v-if="thesis.expected_if_negative" class="scenario scenario-negative">
        <span class="scenario-icon">-</span>
        <p class="scenario-text">{{ thesis.expected_if_negative }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Thesis } from '@/types/ampel'

defineProps<{
  thesis: Thesis
}>()
</script>

<style lang="scss" scoped>
.thesis-card {
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

.thesis-statement {
  font-size: 0.9375rem;
  font-weight: 500;
  line-height: 1.5;
  color: var(--p-text-color);
  margin: 0 0 1rem 0;
}

.catalyst {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  font-size: 0.8125rem;
}

.catalyst-label {
  font-weight: 600;
  color: var(--p-text-color-secondary);
}

.catalyst-text {
  color: var(--p-text-color);
}

.catalyst-date {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  background: var(--p-surface-ground);
  color: var(--p-primary-500);
  font-weight: 600;

  i { font-size: 0.75rem; }
}

.scenarios {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.scenario {
  display: flex;
  gap: 0.625rem;
  padding: 0.625rem 0.75rem;
  border-radius: 8px;
}

.scenario-positive {
  background-color: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.15);
  :root.dark & { background-color: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.2); }
}

.scenario-negative {
  background-color: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  :root.dark & { background-color: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.2); }
}

.scenario-icon {
  font-size: 1rem;
  font-weight: 700;
  flex-shrink: 0;
  width: 1.25rem;
  text-align: center;

  .scenario-positive & { color: #059669; :root.dark & { color: #6ee7b7; } }
  .scenario-negative & { color: #dc2626; :root.dark & { color: #fca5a5; } }
}

.scenario-text {
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  margin: 0;
}
</style>
