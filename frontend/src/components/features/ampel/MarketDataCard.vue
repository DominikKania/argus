<template>
  <div class="market-data-card">
    <h3 class="section-title">
      <i class="pi pi-chart-line" />
      Marktdaten
      <button class="chat-trigger" v-tooltip.top="'Frag den Tutor'" @click="askAbout">
        <i class="pi pi-comments" />
      </button>
    </h3>
    <!-- Kern-Daten: 2 Spalten -->
    <div class="core-grid">
      <!-- Kurs-Daten -->
      <div class="data-column">
        <h4 class="column-title">Kurs & Trend</h4>
        <div class="data-row">
          <span class="data-label">IWDA Kurs</span>
          <span class="data-value font-bold">{{ market.price.toFixed(2) }} €</span>
        </div>
        <div class="data-row">
          <span class="data-label">SMA 50</span>
          <span class="data-value">{{ market.sma50.toFixed(2) }} €</span>
        </div>
        <div class="data-row">
          <span class="data-label">SMA 200</span>
          <span class="data-value">{{ market.sma200.toFixed(2) }} €</span>
        </div>
        <div class="data-row">
          <span class="data-label">ATH</span>
          <span class="data-value">
            {{ market.ath.toFixed(2) }} €
            <span class="delta" :class="market.delta_ath_pct < -5 ? 'delta-bad' : 'delta-ok'">
              ({{ market.delta_ath_pct > 0 ? '+' : '' }}{{ market.delta_ath_pct.toFixed(1) }}%)
            </span>
          </span>
        </div>
        <div class="data-row">
          <span class="data-label">Puffer SMA50</span>
          <span class="data-value" :class="market.puffer_sma50_pct < 2 ? 'value-warn' : ''">
            {{ market.puffer_sma50_pct.toFixed(1) }}%
          </span>
        </div>
        <div class="data-row">
          <span class="data-label">Golden Cross</span>
          <span class="data-value">
            <span class="gc-badge" :class="market.golden_cross ? 'gc-yes' : 'gc-no'">
              {{ market.golden_cross ? 'Ja' : 'Nein' }}
            </span>
          </span>
        </div>
      </div>

      <!-- Makro-Daten -->
      <div class="data-column">
        <h4 class="column-title">VIX & Makro</h4>
        <div class="data-row">
          <span class="data-label">VIX</span>
          <span class="data-value" :class="vixClass">
            {{ market.vix.value.toFixed(1) }}
            <i :class="directionIcon(market.vix.direction)" class="direction-arrow" />
          </span>
        </div>
        <div class="data-row">
          <span class="data-label">VIX Vorwoche</span>
          <span class="data-value">{{ market.vix.prev_week.toFixed(1) }}</span>
        </div>
        <div class="data-row">
          <span class="data-label">US 10Y</span>
          <span class="data-value">{{ market.yields.us10y.toFixed(2) }}%</span>
        </div>
        <div class="data-row">
          <span class="data-label">US 2Y</span>
          <span class="data-value">{{ market.yields.us2y.toFixed(2) }}%</span>
        </div>
        <div class="data-row">
          <span class="data-label">Spread</span>
          <span class="data-value" :class="market.yields.spread <= 0 ? 'value-bad' : ''">
            {{ market.yields.spread.toFixed(2) }}%
            <i :class="directionIcon(market.yields.spread_direction)" class="direction-arrow" />
          </span>
        </div>
        <div class="data-row">
          <span class="data-label">Real Yield</span>
          <span class="data-value">{{ market.yields.real_yield.toFixed(2) }}%</span>
        </div>
        <div class="data-row">
          <span class="data-label">CPI</span>
          <span class="data-value">{{ market.yields.cpi.toFixed(1) }}%</span>
        </div>
      </div>
    </div>

    <!-- Erweiterte Daten: flexible Kacheln -->
    <div v-if="hasExtendedData" class="extended-section">
      <h4 class="column-title">Erweiterte Indikatoren</h4>
      <div class="extended-grid">
        <!-- Sector Rotation -->
        <div v-if="market.sector_rotation" class="ext-tile">
          <div class="ext-tile-header">
            <span class="ext-tile-label">Sektor-Rotation</span>
            <span class="ext-tile-value" :class="riskOnClass">
              {{ market.sector_rotation.risk_on_vs_off != null
                 ? formatSigned(market.sector_rotation.risk_on_vs_off) + 'pp'
                 : '-' }}
            </span>
          </div>
          <div class="sector-details">
            <div
              v-for="(data, name) in market.sector_rotation.sectors"
              :key="name"
              class="sector-item"
            >
              <span class="sector-name">{{ formatSectorName(name as string) }}</span>
              <span class="sector-perf" :class="data.perf_1m >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ formatSigned(data.perf_1m) }}%
              </span>
            </div>
          </div>
        </div>

        <!-- Regional -->
        <div v-if="market.regional" class="ext-tile">
          <div class="ext-tile-header">
            <span class="ext-tile-label">USA vs. Europa</span>
            <span class="ext-tile-value">
              {{ market.regional.usa_vs_europe != null
                 ? formatSigned(market.regional.usa_vs_europe) + 'pp'
                 : '-' }}
            </span>
          </div>
          <div class="sector-details">
            <div class="sector-item" v-if="market.regional.spy_perf_1m != null">
              <span class="sector-name">USA (SPY)</span>
              <span class="sector-perf" :class="market.regional.spy_perf_1m >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ formatSigned(market.regional.spy_perf_1m) }}%
              </span>
            </div>
            <div class="sector-item" v-if="market.regional.ezu_perf_1m != null">
              <span class="sector-name">Europa (EZU)</span>
              <span class="sector-perf" :class="market.regional.ezu_perf_1m >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ formatSigned(market.regional.ezu_perf_1m) }}%
              </span>
            </div>
          </div>
        </div>

        <!-- EUR/USD -->
        <div v-if="market.eurusd" class="ext-tile">
          <div class="ext-tile-header">
            <span class="ext-tile-label">EUR/USD</span>
            <span class="ext-tile-value">
              {{ market.eurusd.rate.toFixed(4) }}
              <i :class="directionIcon(market.eurusd.direction)" class="direction-arrow" />
            </span>
          </div>
          <div class="sector-details">
            <div class="sector-item">
              <span class="sector-name">1M Veränderung</span>
              <span class="sector-perf" :class="market.eurusd.change_1m_pct >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ formatSigned(market.eurusd.change_1m_pct) }}%
              </span>
            </div>
          </div>
        </div>

        <!-- Credit Spread -->
        <div v-if="market.credit_spread" class="ext-tile">
          <div class="ext-tile-header">
            <span class="ext-tile-label">Credit Spread</span>
            <span class="ext-tile-value" :class="creditSpreadClass">
              <template v-if="market.credit_spread.spread_proxy != null">
                {{ formatSigned(market.credit_spread.spread_proxy) }}pp
              </template>
              <template v-else>n/a</template>
              <i :class="creditSpreadIcon" class="direction-arrow" />
            </span>
          </div>
          <div class="sector-details">
            <div class="sector-item">
              <span class="sector-name">HYG (High Yield)</span>
              <span class="sector-perf" :class="(market.credit_spread.hyg_perf_1m ?? 0) >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ market.credit_spread.hyg_perf_1m != null ? formatSigned(market.credit_spread.hyg_perf_1m) + '%' : 'n/a' }}
              </span>
            </div>
            <div class="sector-item">
              <span class="sector-name">LQD (Inv. Grade)</span>
              <span class="sector-perf" :class="(market.credit_spread.lqd_perf_1m ?? 0) >= 0 ? 'perf-pos' : 'perf-neg'">
                {{ market.credit_spread.lqd_perf_1m != null ? formatSigned(market.credit_spread.lqd_perf_1m) + '%' : 'n/a' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Put/Call -->
        <div v-if="market.put_call" class="ext-tile">
          <div class="ext-tile-header">
            <span class="ext-tile-label">Put/Call Ratio</span>
            <span class="ext-tile-value">
              {{ market.put_call.ratio.toFixed(2) }}
              <span class="signal-badge" :class="'signal-' + market.put_call.signal">
                {{ market.put_call.signal }}
              </span>
            </span>
          </div>
        </div>

        <!-- Seasonality -->
        <div v-if="market.seasonality" class="ext-tile">
          <div class="ext-tile-header">
            <span class="ext-tile-label">Saisonalität</span>
            <span class="ext-tile-value">
              {{ formatSigned(market.seasonality.avg_return_pct) }}%
              <span class="signal-badge" :class="'signal-' + market.seasonality.seasonal_bias">
                {{ market.seasonality.seasonal_bias }}
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MarketData } from '@/types/ampel'
import { useChatStore } from '@/stores/chatStore'

const props = defineProps<{
  market: MarketData
}>()

const chatStore = useChatStore()

function askAbout() {
  chatStore.openWithContext(
    `Erkläre mir die aktuellen Marktdaten: IWDA bei ${props.market.price.toFixed(2)}€, VIX bei ${props.market.vix.value.toFixed(1)}, Golden Cross ${props.market.golden_cross ? 'aktiv' : 'nicht aktiv'}`
  )
}

const hasExtendedData = computed(() =>
  !!(props.market.sector_rotation || props.market.regional || props.market.put_call
     || props.market.seasonality || props.market.eurusd || props.market.credit_spread)
)

const vixClass = computed(() => {
  if (props.market.vix.value > 30) return 'value-bad'
  if (props.market.vix.value > 25) return 'value-warn'
  return ''
})

const riskOnClass = computed(() => {
  const val = props.market.sector_rotation?.risk_on_vs_off
  if (val == null) return ''
  if (val > 3) return 'value-good'
  if (val < -3) return 'value-warn'
  return ''
})

const creditSpreadClass = computed(() => {
  const val = props.market.credit_spread?.spread_proxy
  if (val == null) return ''
  if (val > 1) return 'value-good'      // narrowing = risk-on
  if (val < -1) return 'value-warn'     // widening = risk-off
  return ''
})

// Credit Spread: widening = schlecht (rot/runter), narrowing = gut (grün/rauf)
const creditSpreadIcon = computed(() => {
  const dir = props.market.credit_spread?.direction
  if (dir === 'narrowing') return 'pi pi-arrow-up'
  if (dir === 'widening') return 'pi pi-arrow-down'
  return 'pi pi-minus'
})

const directionIcon = (dir: string) => {
  if (dir === 'rising' || dir === 'widening') return 'pi pi-arrow-up'
  if (dir === 'falling' || dir === 'narrowing') return 'pi pi-arrow-down'
  return 'pi pi-minus'
}

const formatSigned = (val: number) => {
  const fixed = val.toFixed(1)
  return val > 0 ? '+' + fixed : fixed
}

const formatSectorName = (name: string) => {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
</script>

<style lang="scss" scoped>
.market-data-card {
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

  i.pi-chart-line { color: var(--p-primary-500); font-size: 1.125rem; }
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

  .market-data-card:hover & { opacity: 0.6; }
  &:hover { opacity: 1 !important; color: var(--p-primary-500); background: var(--p-surface-ground); }
}

.core-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;

  @media screen and (max-width: 640px) {
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }
}

.extended-section {
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--p-surface-border);
}

.extended-grid {
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
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.column-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.75rem 0;
}

.data-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.375rem 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  :root.dark & { border-bottom-color: rgba(255, 255, 255, 0.04); }
}

.data-label {
  font-size: 0.8125rem;
  color: var(--p-text-color-secondary);
}

.data-value {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--p-text-color);
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.delta {
  font-size: 0.75rem;
  font-weight: 400;
}

.delta-ok { color: var(--p-text-color-secondary); }
.delta-bad { color: #ef4444; }

.value-warn { color: #d97706; :root.dark & { color: #fcd34d; } }
.value-bad { color: #ef4444; :root.dark & { color: #fca5a5; } }

.direction-arrow {
  font-size: 0.6875rem;
}

.gc-badge {
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;

  &.gc-yes {
    background-color: rgba(16, 185, 129, 0.12);
    color: #059669;
    :root.dark & { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  }
  &.gc-no {
    background-color: rgba(239, 68, 68, 0.12);
    color: #dc2626;
    :root.dark & { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  }
}

.value-good { color: #059669; :root.dark & { color: #6ee7b7; } }

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
</style>
