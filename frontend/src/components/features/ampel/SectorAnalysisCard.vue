<template>
  <div class="sector-analysis-card">
    <h3 class="section-title">
      <i class="pi pi-th-large" />
      Sektor-Analyse
      <span class="pressure-badge" :class="pressureClass">
        {{ pressurePct }}% unter Druck
      </span>
    </h3>

    <!-- Sector bars -->
    <div class="sector-list">
      <div v-for="s in sectors" :key="s.name" class="sector-row">
        <div class="sector-header">
          <span class="sector-name">{{ s.name }}</span>
          <span class="sector-weight">{{ s.weight.toFixed(1) }}%</span>
          <span class="sector-health" :class="`health-${s.health}`">{{ healthLabel(s.health) }}</span>
        </div>

        <!-- SMA50 mini bar -->
        <div class="sector-bar-track">
          <div
            class="sector-bar-fill"
            :class="`health-${s.health}`"
            :style="{ width: s.sma50Pct + '%' }"
          />
        </div>

        <div class="sector-details">
          <span class="sector-sma">{{ s.aboveSma50 }}/{{ s.count }} SMA50</span>
          <span class="sector-puffer" :class="s.avgPuffer >= 0 ? 'val-pos' : 'val-neg'">
            Puffer {{ formatSigned(s.avgPuffer) }}%
          </span>
          <span class="sector-perf" :class="s.avgPerf >= 0 ? 'val-pos' : 'val-neg'">
            1M {{ formatSigned(s.avgPerf) }}%
          </span>
        </div>

        <!-- Tickers -->
        <div class="sector-tickers">
          <span
            v-for="t in s.tickers"
            :key="t.ticker"
            class="ticker-chip"
            :class="{ 'ticker-below': !t.aboveSma50 }"
          >
            {{ t.ticker }}
          </span>
        </div>
      </div>
    </div>

    <!-- Summary -->
    <div class="sector-summary">
      <i class="pi pi-info-circle" />
      <span v-if="pressurePct >= 70">
        Breite Schwäche: {{ pressurePct }}% des Top-Holdings-Gewichts liegt in technisch schwachen Sektoren.
      </span>
      <span v-else-if="pressurePct >= 40">
        Gemischtes Bild: {{ pressurePct }}% in schwachen, {{ 100 - pressurePct }}% in starken Sektoren.
      </span>
      <span v-else>
        Solide Breite: Nur {{ pressurePct }}% in schwachen Sektoren. Mehrheit technisch gesund.
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  holdings: {
    holdings: Array<{
      ticker: string
      name: string
      sector: string
      weight_pct: number
      price: number
      above_sma50: boolean | null
      puffer_sma50_pct: number | null
      perf_1m_pct: number
    }>
  }
}>()

interface SectorInfo {
  name: string
  weight: number
  count: number
  aboveSma50: number
  sma50Pct: number
  avgPuffer: number
  avgPerf: number
  health: 'strong' | 'moderate' | 'weak'
  tickers: Array<{ ticker: string; aboveSma50: boolean }>
}

const sectors = computed<SectorInfo[]>(() => {
  const map: Record<string, {
    weight: number; count: number; above: number;
    puffer: number; perf: number;
    tickers: Array<{ ticker: string; aboveSma50: boolean }>
  }> = {}

  for (const h of props.holdings.holdings) {
    const sector = h.sector || 'Other'
    if (!map[sector]) {
      map[sector] = { weight: 0, count: 0, above: 0, puffer: 0, perf: 0, tickers: [] }
    }
    const sd = map[sector]
    sd.weight += h.weight_pct
    sd.count += 1
    if (h.above_sma50) sd.above += 1
    sd.puffer += h.puffer_sma50_pct ?? 0
    sd.perf += h.perf_1m_pct
    sd.tickers.push({ ticker: h.ticker, aboveSma50: h.above_sma50 ?? false })
  }

  return Object.entries(map)
    .map(([name, sd]) => ({
      name,
      weight: sd.weight,
      count: sd.count,
      aboveSma50: sd.above,
      sma50Pct: sd.count > 0 ? Math.round((sd.above / sd.count) * 100) : 0,
      avgPuffer: sd.count > 0 ? sd.puffer / sd.count : 0,
      avgPerf: sd.count > 0 ? sd.perf / sd.count : 0,
      health: (sd.above === sd.count ? 'strong' : sd.above >= sd.count / 2 ? 'moderate' : 'weak') as 'strong' | 'moderate' | 'weak',
      tickers: sd.tickers,
    }))
    .sort((a, b) => b.weight - a.weight)
})

const pressurePct = computed(() => {
  const total = sectors.value.reduce((sum, s) => sum + s.weight, 0)
  if (total === 0) return 0
  const weak = sectors.value
    .filter(s => s.health === 'weak')
    .reduce((sum, s) => sum + s.weight, 0)
  return Math.round((weak / total) * 100)
})

const pressureClass = computed(() => {
  if (pressurePct.value >= 70) return 'pressure-high'
  if (pressurePct.value >= 40) return 'pressure-medium'
  return 'pressure-low'
})

function healthLabel(health: string): string {
  if (health === 'strong') return 'STARK'
  if (health === 'moderate') return 'GEMISCHT'
  return 'SCHWACH'
}

function formatSigned(v: number): string {
  return v >= 0 ? `+${v.toFixed(1)}` : v.toFixed(1)
}
</script>

<style lang="scss">
.sector-analysis-card {
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 12px;
  padding: 1.25rem;

  .section-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1rem;
    font-weight: 600;
    margin: 0 0 1rem 0;
    color: var(--p-text-color);

    i:first-child { color: var(--p-primary-500); }
  }
}

.pressure-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  margin-left: auto;

  &.pressure-high { background: rgba(239, 68, 68, 0.12); color: #ef4444; }
  &.pressure-medium { background: rgba(245, 158, 11, 0.12); color: #f59e0b; }
  &.pressure-low { background: rgba(16, 185, 129, 0.12); color: #10b981; }
}

.sector-list {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.sector-row {
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
}

.sector-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.375rem;
}

.sector-name {
  font-weight: 600;
  font-size: 0.8125rem;
  color: var(--p-text-color);
}

.sector-weight {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  font-weight: 500;
}

.sector-health {
  font-size: 0.625rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  margin-left: auto;
  text-transform: uppercase;
  letter-spacing: 0.03em;

  &.health-strong { background: rgba(16, 185, 129, 0.12); color: #10b981; }
  &.health-moderate { background: rgba(245, 158, 11, 0.12); color: #f59e0b; }
  &.health-weak { background: rgba(239, 68, 68, 0.12); color: #ef4444; }
}

// Mini SMA50 bar
.sector-bar-track {
  height: 4px;
  border-radius: 2px;
  background: var(--p-surface-200);
  margin-bottom: 0.375rem;
  overflow: hidden;

  :root.dark & { background: var(--p-surface-700); }
}

.sector-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
  min-width: 2px;

  &.health-strong { background: #10b981; }
  &.health-moderate { background: #f59e0b; }
  &.health-weak { background: #ef4444; }
}

.sector-details {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.375rem;
  flex-wrap: wrap;
}

.sector-sma, .sector-puffer, .sector-perf {
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--p-text-color-secondary);
}

.val-pos { color: #10b981 !important; }
.val-neg { color: #ef4444 !important; }

.sector-tickers {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.ticker-chip {
  font-size: 0.625rem;
  font-weight: 600;
  padding: 0.1rem 0.375rem;
  border-radius: 4px;
  background: rgba(16, 185, 129, 0.08);
  color: #10b981;

  &.ticker-below {
    background: rgba(239, 68, 68, 0.08);
    color: #ef4444;
  }
}

.sector-summary {
  margin-top: 0.875rem;
  padding: 0.625rem 0.875rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;

  i {
    color: var(--p-primary-500);
    font-size: 0.875rem;
    margin-top: 0.05rem;
  }
}
</style>
