<template>
  <div class="earnings-card">
    <h3 class="section-title">
      <i class="pi pi-dollar" />
      Unternehmensgewinne
      <span class="health-badge" :class="'health-' + earnings.earnings_health">
        {{ healthLabel }}
      </span>
      <button class="chat-trigger" v-tooltip.top="'Frag den Tutor'" @click="askAbout">
        <i class="pi pi-comments" />
      </button>
    </h3>

    <!-- Headline Metrics -->
    <div class="core-grid">
      <div class="metric-tile">
        <span class="metric-label">Beat Rate</span>
        <span class="metric-value" :class="beatRateClass">
          {{ earnings.beat_rate }}
          <span class="metric-sub">({{ earnings.beat_rate_pct.toFixed(0) }}%)</span>
        </span>
      </div>
      <div class="metric-tile">
        <span class="metric-label">Ø Surprise</span>
        <span class="metric-value" :class="earnings.avg_surprise_pct >= 0 ? 'value-good' : 'value-bad'">
          {{ formatSigned(earnings.avg_surprise_pct) }}%
        </span>
      </div>
      <div class="metric-tile">
        <span class="metric-label">FWD EPS Growth</span>
        <span class="metric-value" :class="fwdGrowthClass" v-if="earnings.fwd_eps_growth_0y != null">
          {{ formatSigned(earnings.fwd_eps_growth_0y * 100) }}%
        </span>
        <span class="metric-value metric-na" v-else>n/a</span>
      </div>
      <div class="metric-tile">
        <span class="metric-label">Revisionen (30d)</span>
        <span class="metric-value" :class="revisionClass">
          {{ formatSigned(earnings.net_revisions_30d) }}
          <i :class="revisionIcon" class="direction-arrow" />
        </span>
      </div>
    </div>

    <!-- Sector Breakdown -->
    <div v-if="earnings.by_sector && Object.keys(earnings.by_sector).length" class="extended-section">
      <h4 class="column-title">Sektoren</h4>
      <div class="sector-grid">
        <div v-for="(data, sector) in earnings.by_sector" :key="sector" class="ext-tile">
          <div class="ext-tile-header">
            <span class="ext-tile-label">{{ sector }}</span>
            <span class="ext-tile-value" :class="data.beat_rate_pct >= 75 ? 'value-good' : data.beat_rate_pct < 60 ? 'value-bad' : ''">
              {{ data.beat_rate_pct.toFixed(0) }}%
            </span>
          </div>
          <div class="sector-details">
            <div class="sector-item">
              <span class="sector-name">Beat Rate</span>
              <span class="sector-perf">{{ data.beat_rate }}</span>
            </div>
            <div class="sector-item">
              <span class="sector-name">Surprise</span>
              <span class="sector-perf" :class="data.avg_surprise_pct >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ formatSigned(data.avg_surprise_pct) }}%
              </span>
            </div>
            <div class="sector-item" v-if="data.fwd_eps_growth != null">
              <span class="sector-name">FWD Growth</span>
              <span class="sector-perf" :class="data.fwd_eps_growth >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ formatSigned(data.fwd_eps_growth * 100) }}%
              </span>
            </div>
            <div class="sector-item">
              <span class="sector-name">Revisionen</span>
              <span class="sector-perf">
                <span class="signal-badge" :class="'signal-' + revisionSignal(data.revision_direction)">
                  {{ data.revision_direction }}
                </span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Earnings Calendar -->
    <div v-if="earnings.upcoming?.length || earnings.recently_reported?.length" class="extended-section">
      <h4 class="column-title">Kalender</h4>
      <div class="calendar-grid">
        <!-- Upcoming -->
        <div v-if="earnings.upcoming?.length" class="calendar-column">
          <span class="calendar-subtitle">Anstehend</span>
          <div v-for="e in earnings.upcoming" :key="e.ticker + e.date" class="calendar-item">
            <span class="cal-ticker">{{ e.ticker }}</span>
            <span class="cal-sector">{{ e.sector }}</span>
            <span class="cal-date">{{ formatDate(e.date) }}</span>
          </div>
        </div>
        <!-- Recently Reported -->
        <div v-if="earnings.recently_reported?.length" class="calendar-column">
          <span class="calendar-subtitle">Kürzlich gemeldet</span>
          <div v-for="e in earnings.recently_reported" :key="e.ticker + e.date" class="calendar-item">
            <span class="cal-ticker">{{ e.ticker }}</span>
            <span class="cal-surprise" :class="(e.surprise_pct ?? 0) >= 0 ? 'perf-pos' : 'perf-neg'">
              {{ e.surprise_pct != null ? formatSigned(e.surprise_pct) + '%' : '' }}
            </span>
            <span class="cal-date">{{ formatDate(e.date) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EarningsData } from '@/types/ampel'
import { useChatStore } from '@/stores/chatStore'

const props = defineProps<{
  earnings: EarningsData
}>()

const chatStore = useChatStore()

function askAbout() {
  chatStore.openWithContext(
    `Erkläre mir die aktuellen Unternehmensgewinne: Beat Rate ${props.earnings.beat_rate} (${props.earnings.beat_rate_pct}%), Earnings Health "${props.earnings.earnings_health}", Revisionen ${props.earnings.revision_direction}. Was bedeutet das für mein MSCI World ETF?`
  )
}

const healthLabel = computed(() => {
  const map: Record<string, string> = {
    strong: 'Stark',
    moderate: 'Moderat',
    weak: 'Schwach',
    deteriorating: 'Verschlechtert',
  }
  return map[props.earnings.earnings_health] || props.earnings.earnings_health
})

const beatRateClass = computed(() => {
  if (props.earnings.beat_rate_pct >= 75) return 'value-good'
  if (props.earnings.beat_rate_pct < 60) return 'value-bad'
  return 'value-warn'
})

const fwdGrowthClass = computed(() => {
  const v = props.earnings.fwd_eps_growth_0y
  if (v == null) return ''
  if (v > 0.10) return 'value-good'
  if (v < 0.05) return 'value-bad'
  return 'value-warn'
})

const revisionClass = computed(() => {
  if (props.earnings.revision_direction === 'rising') return 'value-good'
  if (props.earnings.revision_direction === 'falling') return 'value-bad'
  return ''
})

const revisionIcon = computed(() => {
  if (props.earnings.revision_direction === 'rising') return 'pi pi-arrow-up'
  if (props.earnings.revision_direction === 'falling') return 'pi pi-arrow-down'
  return 'pi pi-minus'
})

function revisionSignal(dir: string) {
  if (dir === 'rising') return 'bullish'
  if (dir === 'falling') return 'bearish'
  return 'neutral'
}

const formatSigned = (val: number) => {
  const fixed = val.toFixed(1)
  return val > 0 ? '+' + fixed : fixed
}

const formatDate = (dateStr: string) => {
  const d = new Date(dateStr)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })
}
</script>

<style lang="scss" scoped>
.earnings-card {
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

  i.pi-dollar { color: var(--p-primary-500); font-size: 1.125rem; }
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

  .earnings-card:hover & { opacity: 0.6; }
  &:hover { opacity: 1 !important; color: var(--p-primary-500); background: var(--p-surface-ground); }
}

.health-badge {
  font-size: 0.6875rem;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;

  &.health-strong {
    background-color: rgba(16, 185, 129, 0.12);
    color: #059669;
    :root.dark & { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  }
  &.health-moderate {
    background-color: rgba(217, 119, 6, 0.12);
    color: #d97706;
    :root.dark & { background-color: rgba(217, 119, 6, 0.2); color: #fcd34d; }
  }
  &.health-weak {
    background-color: rgba(239, 68, 68, 0.12);
    color: #dc2626;
    :root.dark & { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  }
  &.health-deteriorating {
    background-color: rgba(239, 68, 68, 0.2);
    color: #dc2626;
    :root.dark & { background-color: rgba(239, 68, 68, 0.3); color: #fca5a5; }
  }
}

.core-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;

  @media screen and (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }
  @media screen and (max-width: 480px) {
    grid-template-columns: 1fr;
  }
}

.metric-tile {
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  text-align: center;
}

.metric-label {
  display: block;
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.metric-value {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--p-text-color);
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.metric-sub {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--p-text-color-secondary);
}

.metric-na {
  color: var(--p-text-color-secondary);
  font-weight: 400;
}

.extended-section {
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--p-surface-border);
}

.column-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.75rem 0;
}

.sector-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;

  @media screen and (max-width: 960px) {
    grid-template-columns: repeat(2, 1fr);
  }
  @media screen and (max-width: 640px) {
    grid-template-columns: 1fr;
  }
}

.ext-tile {
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid transparent;
  transition: border-color 0.15s;

  &:hover { border-color: var(--p-surface-border); }
}

.ext-tile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.ext-tile-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
}

.ext-tile-value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.sector-details {
  padding: 0.25rem 0;
}

.sector-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.125rem 0;
  font-size: 0.75rem;
}

.sector-name {
  color: var(--p-text-color-secondary);
}

.sector-perf {
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.perf-pos { color: #059669; :root.dark & { color: #6ee7b7; } }
.perf-neg { color: #ef4444; :root.dark & { color: #fca5a5; } }
.value-good { color: #059669; :root.dark & { color: #6ee7b7; } }
.value-warn { color: #d97706; :root.dark & { color: #fcd34d; } }
.value-bad { color: #ef4444; :root.dark & { color: #fca5a5; } }

.direction-arrow {
  font-size: 0.6875rem;
}

.signal-badge {
  font-size: 0.6875rem;
  padding: 0.0625rem 0.375rem;
  border-radius: 4px;
  font-weight: 600;
  text-transform: capitalize;

  &.signal-bullish {
    background-color: rgba(16, 185, 129, 0.12);
    color: #059669;
    :root.dark & { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  }
  &.signal-bearish {
    background-color: rgba(239, 68, 68, 0.12);
    color: #dc2626;
    :root.dark & { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  }
  &.signal-neutral {
    background-color: rgba(107, 114, 128, 0.12);
    color: #6b7280;
    :root.dark & { background-color: rgba(107, 114, 128, 0.2); color: #d1d5db; }
  }
}

// Calendar
.calendar-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;

  @media screen and (max-width: 640px) {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
}

.calendar-subtitle {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  margin-bottom: 0.5rem;
}

.calendar-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  font-size: 0.8125rem;

  :root.dark & { border-bottom-color: rgba(255, 255, 255, 0.04); }
}

.cal-ticker {
  font-weight: 600;
  color: var(--p-text-color);
  min-width: 3.5rem;
}

.cal-sector {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  flex: 1;
}

.cal-surprise {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex: 1;
}

.cal-date {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
