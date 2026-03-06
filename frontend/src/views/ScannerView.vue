<template>
  <div class="scanner-view">
    <div class="page-header">
      <h1 class="page-title">Opportunity Scanner</h1>
      <div class="header-actions">
        <span v-if="scan?.date" class="last-scan">Scan: {{ scan.date }}</span>
        <button
          class="run-btn"
          :class="{ running: scanning }"
          :disabled="scanning"
          @click="runScan"
        >
          <i class="pi" :class="scanning ? 'pi-spin pi-spinner' : 'pi-bolt'" />
          <span>{{ scanning ? scanStatus : 'Scan starten' }}</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem; color: var(--p-primary-500)" />
    </div>

    <!-- Empty -->
    <div v-else-if="!scan" class="empty-state">
      <i class="pi pi-bolt" />
      <p>Noch kein Scan durchgefuehrt. Starte einen Scan oder fuehre die Ampel-Analyse aus.</p>
    </div>

    <!-- Scan Results -->
    <template v-else>
      <!-- Market Summary -->
      <div class="summary-card" v-if="scan.market_summary">
        <div class="summary-header">
          <i class="pi pi-globe" />
          <span>Marktumfeld</span>
        </div>
        <p class="summary-text">{{ scan.market_summary }}</p>
        <div class="summary-meta">
          <span>{{ scan.total_screened }} Aktien gescreent</span>
          <span>{{ scan.opportunities?.length || 0 }} Opportunities</span>
        </div>
      </div>

      <!-- Top Opportunities -->
      <div class="opportunities">
        <div
          v-for="(opp, i) in scan.opportunities"
          :key="opp.ticker"
          class="opp-card"
          :class="'conviction-' + opp.conviction"
        >
          <div class="opp-rank">{{ opp.rank || (i + 1) }}</div>
          <div class="opp-content">
            <div class="opp-header">
              <div class="opp-title">
                <span class="opp-ticker">{{ opp.ticker }}</span>
                <span class="opp-name">{{ opp.name }}</span>
              </div>
              <div class="opp-badges">
                <span class="conviction-badge" :class="opp.conviction">
                  {{ convictionLabel(opp.conviction) }}
                </span>
                <span class="sector-badge">{{ opp.sector }}</span>
              </div>
            </div>

            <!-- Metrics Row -->
            <div class="opp-metrics">
              <div class="metric">
                <span class="metric-label">Kurs</span>
                <span class="metric-value">${{ opp.price }}</span>
              </div>
              <div class="metric">
                <span class="metric-label">ATH-Abstand</span>
                <span class="metric-value" :class="opp.pct_from_ath < -20 ? 'deep-discount' : 'mild-discount'">
                  {{ opp.pct_from_ath }}%
                </span>
              </div>
              <div class="metric">
                <span class="metric-label">SMA50</span>
                <span class="metric-value">{{ opp.pct_vs_sma50 > 0 ? '+' : '' }}{{ opp.pct_vs_sma50 }}%</span>
              </div>
              <div class="metric">
                <span class="metric-label">Buy %</span>
                <span class="metric-value buy-pct">{{ opp.buy_pct }}%</span>
              </div>
              <div class="metric">
                <span class="metric-label">Score</span>
                <span class="metric-value score">{{ opp.score }}</span>
              </div>
            </div>

            <!-- Analyst Bar -->
            <div class="analyst-mini-bar" v-if="opp.analyst">
              <div
                class="bar-seg strongBuy"
                :style="{ width: analystPct(opp, 'strongBuy') + '%' }"
                v-if="opp.analyst.strongBuy"
              />
              <div
                class="bar-seg buy"
                :style="{ width: analystPct(opp, 'buy') + '%' }"
                v-if="opp.analyst.buy"
              />
              <div
                class="bar-seg hold"
                :style="{ width: analystPct(opp, 'hold') + '%' }"
                v-if="opp.analyst.hold"
              />
              <div
                class="bar-seg sell"
                :style="{ width: analystPct(opp, 'sell') + '%' }"
                v-if="opp.analyst.sell"
              />
              <div
                class="bar-seg strongSell"
                :style="{ width: analystPct(opp, 'strongSell') + '%' }"
                v-if="opp.analyst.strongSell"
              />
            </div>

            <!-- Research -->
            <div class="opp-research" v-if="opp.thesis">
              <div class="research-row">
                <span class="research-label">These</span>
                <span class="research-text">{{ opp.thesis }}</span>
              </div>
              <div class="research-row" v-if="opp.catalyst">
                <span class="research-label">Katalysator</span>
                <span class="research-text">{{ opp.catalyst }}</span>
              </div>
              <div class="research-row" v-if="opp.risk">
                <span class="research-label">Risiko</span>
                <span class="research-text risk-text">{{ opp.risk }}</span>
              </div>
              <div class="research-footer" v-if="opp.target_upside_pct || opp.timeframe">
                <span v-if="opp.target_upside_pct" class="upside-badge">
                  +{{ opp.target_upside_pct }}% Upside
                </span>
                <span v-if="opp.timeframe" class="timeframe-badge">
                  {{ opp.timeframe }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- All Scores (collapsed) -->
      <div class="all-scores-section" v-if="scan.all_scores?.length">
        <button class="toggle-btn" @click="showAllScores = !showAllScores">
          <i class="pi" :class="showAllScores ? 'pi-chevron-up' : 'pi-chevron-down'" />
          Alle {{ scan.all_scores.length }} bewerteten Aktien
        </button>
        <div v-if="showAllScores" class="scores-table">
          <div class="scores-header">
            <span class="col-rank">#</span>
            <span class="col-ticker">Ticker</span>
            <span class="col-score">Score</span>
            <span class="col-buy">Buy %</span>
            <span class="col-ath">ATH</span>
          </div>
          <div
            v-for="(s, i) in scan.all_scores"
            :key="s.ticker"
            class="scores-row"
            :class="{ top10: i < 10 }"
          >
            <span class="col-rank">{{ i + 1 }}</span>
            <span class="col-ticker">{{ s.ticker }}</span>
            <span class="col-score">{{ s.score }}</span>
            <span class="col-buy">{{ s.buy_pct }}%</span>
            <span class="col-ath">{{ s.pct_from_ath }}%</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'

interface Opportunity {
  ticker: string
  name: string
  sector: string
  price: number
  pct_from_ath: number
  range_20d: number
  pct_vs_sma50: number
  pct_vs_sma200: number | null
  vol_ratio: number
  analyst: { strongBuy: number; buy: number; hold: number; sell: number; strongSell: number }
  total_analysts: number
  buy_pct: number
  score: number
  market_cap: number | null
  thesis: string
  catalyst: string
  risk: string
  target_upside_pct: number | null
  timeframe: string
  conviction: string
  rank: number
}

interface ScanResult {
  date: string
  market_summary: string
  total_screened: number
  opportunities: Opportunity[]
  all_scores: { ticker: string; score: number; buy_pct: number; pct_from_ath: number }[]
  updated_at: string
}

const scan = ref<ScanResult | null>(null)
const loading = ref(false)
const scanning = ref(false)
const scanStatus = ref('')
const showAllScores = ref(false)

async function loadLatest() {
  loading.value = true
  try {
    const data = await ApiService.get<ScanResult | null>(API_ENDPOINTS.SCANNER.LATEST)
    scan.value = data
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

async function runScan() {
  if (scanning.value) return
  scanning.value = true
  scanStatus.value = 'Starte...'

  try {
    const response = await fetch('/api' + API_ENDPOINTS.SCANNER.RUN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let currentEvent = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          continue
        }
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue

        try {
          const payload = JSON.parse(raw)
          if (currentEvent === 'status' && typeof payload === 'string') {
            scanStatus.value = payload
          } else if (currentEvent === 'done') {
            scanStatus.value = 'Fertig!'
          }
        } catch {
          // ignore parse errors
        }
        currentEvent = ''
      }
    }

    // Reload latest after scan completes
    await loadLatest()
  } catch (err) {
    console.error('Scan error:', err)
    scanStatus.value = 'Fehler!'
  } finally {
    scanning.value = false
  }
}

function convictionLabel(c: string): string {
  const map: Record<string, string> = { high: 'Hoch', medium: 'Mittel', low: 'Niedrig' }
  return map[c] || c
}

function analystPct(opp: Opportunity, key: string): number {
  if (!opp.total_analysts) return 0
  return ((opp.analyst as any)[key] / opp.total_analysts) * 100
}

onMounted(() => {
  loadLatest()
})
</script>

<style lang="scss" scoped>
.scanner-view {
  padding: 1.5rem;
  max-width: 960px;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.last-scan {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}

.run-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  color: var(--p-text-color-secondary);
  font-size: 0.8125rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;

  &:hover:not(:disabled) {
    border-color: var(--p-primary-500);
    color: var(--p-primary-500);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  i { font-size: 0.875rem; }
}

// Summary
.summary-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  margin-bottom: 1.5rem;
}

.summary-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-color);

  i { color: var(--p-primary-500); }
}

.summary-text {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--p-text-color);
  margin: 0 0 0.75rem 0;
}

.summary-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}

// Opportunity Cards
.opportunities {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.opp-card {
  display: flex;
  gap: 1rem;
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  transition: border-color 0.15s;

  &.conviction-high { border-left: 4px solid #059669; }
  &.conviction-medium { border-left: 4px solid #f59e0b; }
  &.conviction-low { border-left: 4px solid var(--p-surface-border); }
}

.opp-rank {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--p-text-color-secondary);
  opacity: 0.3;
  min-width: 28px;
  text-align: center;
  padding-top: 0.125rem;
  font-variant-numeric: tabular-nums;
}

.opp-content {
  flex: 1;
  min-width: 0;
}

.opp-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
  gap: 0.75rem;
}

.opp-title {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.opp-ticker {
  font-size: 1rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.opp-name {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.opp-badges {
  display: flex;
  gap: 0.375rem;
  flex-shrink: 0;
}

.conviction-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;

  &.high {
    color: #059669;
    background: rgba(16, 185, 129, 0.12);
    :root.dark & { color: #6ee7b7; background: rgba(16, 185, 129, 0.2); }
  }
  &.medium {
    color: #b45309;
    background: rgba(245, 158, 11, 0.12);
    :root.dark & { color: #fcd34d; background: rgba(245, 158, 11, 0.2); }
  }
  &.low {
    color: var(--p-text-color-secondary);
    background: var(--p-surface-ground);
  }
}

.sector-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--p-text-color-secondary);
  background: var(--p-surface-ground);
}

// Metrics
.opp-metrics {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.625rem;
  flex-wrap: wrap;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.metric-label {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-color-secondary);
}

.metric-value {
  font-size: 0.8125rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-color);

  &.deep-discount { color: #dc2626; :root.dark & { color: #fca5a5; } }
  &.mild-discount { color: #f59e0b; :root.dark & { color: #fcd34d; } }
  &.buy-pct { color: #059669; :root.dark & { color: #6ee7b7; } }
  &.score { color: var(--p-primary-500); }
}

// Mini Analyst Bar
.analyst-mini-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.bar-seg {
  transition: width 0.4s ease;
  min-width: 1px;

  &.strongBuy { background: #059669; }
  &.buy { background: #34d399; }
  &.hold { background: #fbbf24; }
  &.sell { background: #f87171; }
  &.strongSell { background: #dc2626; }
}

// Research
.opp-research {
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
}

.research-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.375rem;
  font-size: 0.8125rem;
  line-height: 1.5;

  &:last-child { margin-bottom: 0; }
}

.research-label {
  font-weight: 600;
  color: var(--p-text-color-secondary);
  flex-shrink: 0;
  min-width: 75px;
}

.research-text {
  color: var(--p-text-color);

  &.risk-text { color: #dc2626; :root.dark & { color: #fca5a5; } }
}

.research-footer {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--p-surface-border);
}

.upside-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 700;
  color: #059669;
  background: rgba(16, 185, 129, 0.12);
  :root.dark & { color: #6ee7b7; background: rgba(16, 185, 129, 0.2); }
}

.timeframe-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--p-text-color-secondary);
  background: var(--p-surface-ground);
}

// All Scores Table
.all-scores-section {
  margin-bottom: 1.5rem;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  color: var(--p-text-color-secondary);
  font-size: 0.8125rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: var(--p-primary-400);
    color: var(--p-text-color);
  }

  i { font-size: 0.75rem; }
}

.scores-table {
  margin-top: 0.5rem;
  border-radius: 10px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  overflow: hidden;
}

.scores-header,
.scores-row {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.scores-header {
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom: 1px solid var(--p-surface-border);
  font-size: 0.6875rem;
}

.scores-row {
  color: var(--p-text-color);
  border-bottom: 1px solid var(--p-surface-border);

  &:last-child { border-bottom: none; }

  &.top10 {
    background: rgba(59, 130, 246, 0.04);
    font-weight: 600;
    :root.dark & { background: rgba(59, 130, 246, 0.08); }
  }
}

.col-rank { width: 40px; }
.col-ticker { flex: 1; font-weight: 600; }
.col-score { width: 60px; text-align: right; }
.col-buy { width: 60px; text-align: right; }
.col-ath { width: 60px; text-align: right; }

// States
.loading-state {
  display: flex;
  justify-content: center;
  padding: 3rem 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 4rem 0;
  text-align: center;

  i { font-size: 3rem; color: var(--p-text-color-secondary); opacity: 0.5; }
  p { color: var(--p-text-color-secondary); margin: 0; max-width: 400px; }
}
</style>
