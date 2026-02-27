<template>
  <div class="signal-card" :class="cardClass">
    <div class="signal-header">
      <span class="signal-name">{{ displayName }}</span>
      <div class="signal-dots">
        <span v-tooltip.top="'Mechanisch'" class="signal-dot" :class="dotClass(signal.mechanical)" />
        <span v-tooltip.top="'Kontext'" class="signal-dot" :class="dotClass(signal.context)" />
      </div>
    </div>
    <div class="signal-badges">
      <span class="signal-badge" :class="badgeClass(signal.mechanical)">
        {{ signal.mechanical }}
      </span>
      <i class="pi pi-arrow-right text-xs" style="color: var(--p-text-color-secondary)" />
      <span class="signal-badge" :class="badgeClass(signal.context)">
        {{ signal.context }}
      </span>
    </div>
    <p v-if="displayNote" class="signal-note">{{ displayNote }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Signal, SignalColor } from '@/types/ampel'
import { useDummyModeStore } from '@/stores/dummyModeStore'
import { useAmpelStore } from '@/stores/ampelStore'

const props = defineProps<{
  name: string
  signal: Signal
}>()

const dummyModeStore = useDummyModeStore()
const ampelStore = useAmpelStore()

const displayNote = computed(() => {
  if (dummyModeStore.isDummyMode) {
    const simplified = ampelStore.latestAnalysis?.simplified
    if (simplified?.signal_notes?.[props.name]) {
      return simplified.signal_notes[props.name]
    }
  }
  return props.signal.note
})

const nameMap: Record<string, string> = {
  trend: 'Trend',
  volatility: 'Volatilität',
  macro: 'Makro',
  sentiment: 'Sentiment',
}

const displayName = computed(() => nameMap[props.name] || props.name)

const cardClass = computed(() => {
  const ctx = props.signal.context
  return {
    'card-green': ctx === 'green',
    'card-yellow': ctx === 'yellow',
    'card-red': ctx === 'red',
  }
})

const dotClass = (color: SignalColor) => ({
  'dot-green': color === 'green',
  'dot-yellow': color === 'yellow',
  'dot-red': color === 'red',
})

const badgeClass = (color: SignalColor) => ({
  'badge-green': color === 'green',
  'badge-yellow': color === 'yellow',
  'badge-red': color === 'red',
})
</script>

<style lang="scss" scoped>
.signal-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  transition: all 0.2s ease;

  &.card-green { border-left: 4px solid #10b981; }
  &.card-yellow { border-left: 4px solid #f59e0b; }
  &.card-red { border-left: 4px solid #ef4444; }
}

.signal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.signal-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.signal-dots {
  display: flex;
  gap: 0.375rem;
}

.signal-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
  cursor: help;

  &.dot-green { background-color: #10b981; }
  &.dot-yellow { background-color: #f59e0b; }
  &.dot-red { background-color: #ef4444; }
}

.signal-badges {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.signal-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 6px;
  text-transform: uppercase;
  letter-spacing: 0.025em;

  &.badge-green {
    background-color: rgba(16, 185, 129, 0.15);
    color: #059669;
    :root.dark & {
      background-color: rgba(16, 185, 129, 0.2);
      color: #6ee7b7;
    }
  }
  &.badge-yellow {
    background-color: rgba(245, 158, 11, 0.15);
    color: #d97706;
    :root.dark & {
      background-color: rgba(245, 158, 11, 0.2);
      color: #fcd34d;
    }
  }
  &.badge-red {
    background-color: rgba(239, 68, 68, 0.15);
    color: #dc2626;
    :root.dark & {
      background-color: rgba(239, 68, 68, 0.2);
      color: #fca5a5;
    }
  }
}

.signal-note {
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  margin: 0;
}
</style>
