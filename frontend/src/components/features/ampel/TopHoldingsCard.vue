<template>
  <div class="top-holdings-card">
    <h3 class="section-title">
      <i class="pi pi-building" />
      Top-Holdings
      <span class="health-badge" :class="healthClass">
        {{ holdings.above_sma50_count }}/{{ holdings.total_count }} über SMA50
      </span>
      <button class="chat-trigger" v-tooltip.top="'Frag den Tutor'" @click="askAbout">
        <i class="pi pi-comments" />
      </button>
    </h3>

    <!-- SMA50 Bar -->
    <div class="sma-bar">
      <div class="sma-bar-track">
        <div class="sma-bar-fill" :class="healthClass" :style="{ width: holdings.above_sma50_pct + '%' }" />
      </div>
      <span class="sma-bar-label">{{ holdings.above_sma50_pct }}% über SMA50</span>
    </div>

    <!-- Holdings Grid -->
    <div class="holdings-grid">
      <div
        v-for="h in holdings.holdings"
        :key="h.ticker"
        class="holding-tile"
        :class="{ 'holding-below': h.above_sma50 === false }"
      >
        <div class="holding-header">
          <span class="holding-ticker">{{ h.ticker }}</span>
          <span class="holding-weight">{{ h.weight_pct }}%</span>
        </div>
        <div class="holding-name">{{ h.name }}</div>
        <div class="holding-metrics">
          <span class="holding-price">${{ h.price }}</span>
          <span class="holding-perf" :class="h.perf_1m_pct >= 0 ? 'perf-up' : 'perf-down'">
            {{ formatSigned(h.perf_1m_pct) }}%
          </span>
        </div>
        <div class="holding-sma" :class="h.above_sma50 ? 'sma-above' : 'sma-below'">
          {{ h.above_sma50 ? '> SMA50' : '< SMA50' }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chatStore'

const chatStore = useChatStore()

const props = defineProps<{
  holdings: {
    holdings: Array<{
      ticker: string
      name: string
      sector: string
      weight_pct: number
      price: number
      sma50: number | null
      above_sma50: boolean | null
      perf_1m_pct: number
    }>
    above_sma50_count: number
    total_count: number
    above_sma50_pct: number
  }
}>()

const healthClass = computed(() => {
  const pct = props.holdings.above_sma50_pct
  if (pct >= 70) return 'health-strong'
  if (pct >= 40) return 'health-moderate'
  return 'health-weak'
})

function formatSigned(v: number): string {
  return v >= 0 ? `+${v.toFixed(1)}` : v.toFixed(1)
}

function askAbout() {
  const lines = props.holdings.holdings.map(h => {
    const sma = h.above_sma50 ? 'über' : 'unter'
    return `${h.name} (${h.ticker}): $${h.price}, 1M: ${formatSigned(h.perf_1m_pct)}%, ${sma} SMA50`
  })
  chatStore.openWithContext(
    `Top-Holdings Analyse:\n${props.holdings.above_sma50_count}/${props.holdings.total_count} über SMA50\n\n${lines.join('\n')}\n\nWas sagen die Top-Holdings über den Zustand meines ETF?`
  )
}
</script>

<style lang="scss">
.top-holdings-card {
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 12px;
  padding: 1.25rem;
}

.sma-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;

  .sma-bar-track {
    flex: 1;
    height: 8px;
    border-radius: 4px;
    background: var(--p-surface-200);
    overflow: hidden;

    :root.dark & { background: var(--p-surface-700); }
  }

  .sma-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;

    &.health-strong { background: #10b981; }
    &.health-moderate { background: #f59e0b; }
    &.health-weak { background: #ef4444; }
  }

  .sma-bar-label {
    font-size: 0.75rem;
    color: var(--p-text-color-secondary);
    white-space: nowrap;
    font-weight: 500;
  }
}

.holdings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.5rem;
}

.holding-tile {
  padding: 0.625rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  transition: border-color 0.15s;

  &.holding-below {
    border-color: rgba(239, 68, 68, 0.25);
    background: rgba(239, 68, 68, 0.03);

    :root.dark & {
      background: rgba(239, 68, 68, 0.06);
    }
  }
}

.holding-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.125rem;
}

.holding-ticker {
  font-weight: 700;
  font-size: 0.8125rem;
  color: var(--p-text-color);
}

.holding-weight {
  font-size: 0.6875rem;
  color: var(--p-text-color-secondary);
}

.holding-name {
  font-size: 0.6875rem;
  color: var(--p-text-color-secondary);
  margin-bottom: 0.375rem;
}

.holding-metrics {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.holding-price {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.holding-perf {
  font-size: 0.75rem;
  font-weight: 600;

  &.perf-up { color: #10b981; }
  &.perf-down { color: #ef4444; }
}

.holding-sma {
  font-size: 0.6875rem;
  font-weight: 600;
  text-align: center;
  padding: 0.125rem 0;
  border-radius: 4px;

  &.sma-above {
    color: #10b981;
    background: rgba(16, 185, 129, 0.08);
  }

  &.sma-below {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.08);
  }
}

// Reuse section-title from other cards
.top-holdings-card .section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.75rem 0;
  color: var(--p-text-color);

  i:first-child {
    color: var(--p-primary-500);
  }
}

.top-holdings-card .health-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  margin-left: auto;

  &.health-strong { background: rgba(16, 185, 129, 0.12); color: #10b981; }
  &.health-moderate { background: rgba(245, 158, 11, 0.12); color: #f59e0b; }
  &.health-weak { background: rgba(239, 68, 68, 0.12); color: #ef4444; }
}

.top-holdings-card .chat-trigger {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  color: var(--p-text-color-secondary);
  transition: color 0.15s;
  &:hover { color: var(--p-primary-500); }
}
</style>
