<template>
  <div class="kurse-view">
    <!-- Loading -->
    <div v-if="pricesStore.loading && !pricesStore.prices.length" class="loading-state">
      <Skeleton width="250px" height="36px" border-radius="8px" class="mb-4" />
      <Skeleton height="300px" border-radius="12px" />
      <Skeleton height="200px" border-radius="12px" class="mt-4" />
    </div>

    <!-- Error -->
    <div v-else-if="pricesStore.error" class="error-state">
      <div class="error-box">
        <i class="pi pi-exclamation-circle" />
        <p>{{ pricesStore.error }}</p>
        <Button label="Erneut versuchen" icon="pi pi-refresh" severity="secondary" @click="loadData" />
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="!pricesStore.watchlist.length" class="empty-state">
      <i class="pi pi-chart-line" />
      <p>Keine Watchlist vorhanden. Füge Ticker hinzu:</p>
      <code>python argus.py watchlist add NVDA</code>
    </div>

    <!-- Data -->
    <template v-else>
      <h1 class="page-title">Kurse</h1>

      <!-- Ticker Selector -->
      <div class="ticker-bar">
        <button
          v-for="item in pricesStore.watchlist"
          :key="item.ticker"
          class="ticker-chip"
          :class="{ active: item.ticker === pricesStore.selectedTicker }"
          @click="selectTicker(item.ticker)"
        >
          <span class="ticker-symbol">{{ item.ticker }}</span>
          <span class="ticker-name">{{ item.name }}</span>
        </button>
      </div>

      <!-- Chart -->
      <div class="chart-card" v-if="pricesStore.prices.length">
        <div class="chart-header">
          <div class="chart-title">
            <span class="chart-ticker">{{ pricesStore.selectedTicker }}</span>
            <span class="chart-price" v-if="latestPrice">{{ latestPrice.close.toFixed(2) }}€</span>
            <span class="chart-change" :class="changeClass" v-if="priceChange !== null">
              {{ priceChange > 0 ? '+' : '' }}{{ priceChange.toFixed(2) }}%
            </span>
          </div>
          <div class="period-selector">
            <button
              v-for="p in periods"
              :key="p.value"
              class="period-btn"
              :class="{ active: p.value === selectedPeriod }"
              @click="changePeriod(p.value)"
            >
              {{ p.label }}
            </button>
          </div>
        </div>
        <canvas ref="chartCanvas" height="300"></canvas>
      </div>

      <!-- Price Table -->
      <div class="table-card" v-if="pricesStore.prices.length">
        <h3 class="section-title">
          <i class="pi pi-list" />
          Kursdaten
        </h3>
        <div class="table-wrapper">
          <table class="price-table">
            <thead>
              <tr>
                <th>Datum</th>
                <th class="num">Open</th>
                <th class="num">High</th>
                <th class="num">Low</th>
                <th class="num">Close</th>
                <th class="num">Volume</th>
                <th class="num">SMA50</th>
                <th class="num">SMA200</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in reversedPrices" :key="row.date">
                <td>{{ formatDate(row.date) }}</td>
                <td class="num">{{ row.open.toFixed(2) }}</td>
                <td class="num">{{ row.high.toFixed(2) }}</td>
                <td class="num">{{ row.low.toFixed(2) }}</td>
                <td class="num" :class="closeClass(row)">{{ row.close.toFixed(2) }}</td>
                <td class="num vol">{{ formatVolume(row.volume) }}</td>
                <td class="num">{{ row.sma50?.toFixed(2) ?? '-' }}</td>
                <td class="num">{{ row.sma200?.toFixed(2) ?? '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from 'vue'
import { usePricesStore } from '@/stores/pricesStore'
import { Chart, registerables } from 'chart.js'
import type { PriceEntry } from '@/types/prices'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'

Chart.register(...registerables)

const pricesStore = usePricesStore()
const chartCanvas = ref<HTMLCanvasElement | null>(null)
let chartInstance: Chart | null = null

const periods = [
  { label: '1W', value: 5 },
  { label: '1M', value: 22 },
  { label: '6M', value: 132 },
  { label: '1Y', value: 252 },
]
const selectedPeriod = ref(132)

const latestPrice = computed(() => {
  const p = pricesStore.prices
  return p.length ? p[p.length - 1] : null
})

const priceChange = computed(() => {
  const p = pricesStore.prices
  if (p.length < 2) return null
  const first = p[0].close
  const last = p[p.length - 1].close
  return ((last - first) / first) * 100
})

const changeClass = computed(() => ({
  'change-positive': (priceChange.value ?? 0) > 0,
  'change-negative': (priceChange.value ?? 0) < 0,
}))

const reversedPrices = computed(() => [...pricesStore.prices].reverse())

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })
}

function formatVolume(vol: number) {
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`
  if (vol >= 1_000) return `${Math.round(vol / 1_000)}K`
  return String(vol)
}

function closeClass(row: PriceEntry) {
  if (row.sma50 && row.close > row.sma50) return 'above-sma'
  if (row.sma50 && row.close < row.sma50) return 'below-sma'
  return ''
}

function selectTicker(ticker: string) {
  pricesStore.fetchPrices(ticker, selectedPeriod.value)
}

function changePeriod(days: number) {
  selectedPeriod.value = days
  pricesStore.fetchPrices(pricesStore.selectedTicker, days)
}

function renderChart() {
  if (!chartCanvas.value || !pricesStore.prices.length) return

  if (chartInstance) {
    chartInstance.destroy()
  }

  const data = pricesStore.prices
  const labels = data.map(d => formatDate(d.date))
  const isDark = document.documentElement.classList.contains('dark')
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'
  const textColor = isDark ? '#a1a1aa' : '#71717a'

  chartInstance = new Chart(chartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Close',
          data: data.map(d => d.close),
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.08)',
          fill: true,
          borderWidth: 2,
          pointRadius: 0,
          pointHitRadius: 10,
          tension: 0.3,
        },
        {
          label: 'SMA50',
          data: data.map(d => d.sma50 ?? null),
          borderColor: '#f59e0b',
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
          tension: 0.3,
        },
        {
          label: 'SMA200',
          data: data.map(d => d.sma200 ?? null),
          borderColor: '#ef4444',
          borderWidth: 1.5,
          borderDash: [8, 4],
          pointRadius: 0,
          fill: false,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index',
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            color: textColor,
            usePointStyle: true,
            pointStyle: 'line',
            font: { size: 11 },
            padding: 16,
          },
        },
        tooltip: {
          backgroundColor: isDark ? '#27272a' : '#fff',
          titleColor: isDark ? '#e4e4e7' : '#18181b',
          bodyColor: isDark ? '#a1a1aa' : '#52525b',
          borderColor: isDark ? '#3f3f46' : '#e4e4e7',
          borderWidth: 1,
          padding: 10,
          displayColors: true,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2) ?? '-'}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor, font: { size: 10 }, maxTicksLimit: 10 },
        },
        y: {
          grid: { color: gridColor },
          ticks: { color: textColor, font: { size: 10 } },
        },
      },
    },
  })
}

watch(() => pricesStore.prices, () => {
  nextTick(renderChart)
})

function loadData() {
  pricesStore.fetchAll()
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.kurse-view {
  padding: 1.5rem;
  max-width: 1200px;
  overflow-y: auto;

  @media screen and (max-width: 640px) {
    padding: 1rem;
  }
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);
  margin: 0 0 1.5rem 0;
}

// Ticker Bar
.ticker-bar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.ticker-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0.5rem 1rem;
  border-radius: 10px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: var(--p-primary-400);
  }

  &.active {
    border-color: var(--p-primary-500);
    background: rgba(59, 130, 246, 0.08);

    .ticker-symbol {
      color: var(--p-primary-500);
    }
  }
}

.ticker-symbol {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.ticker-name {
  font-size: 0.6875rem;
  color: var(--p-text-color-secondary);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// Chart Card
.chart-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  margin-bottom: 1.5rem;

  canvas {
    width: 100% !important;
    height: 300px !important;
  }
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.chart-title {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.chart-ticker {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.chart-price {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.chart-change {
  font-size: 0.8125rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;

  &.change-positive {
    color: #059669;
    background: rgba(16, 185, 129, 0.12);
    :root.dark & { color: #6ee7b7; background: rgba(16, 185, 129, 0.2); }
  }

  &.change-negative {
    color: #dc2626;
    background: rgba(239, 68, 68, 0.12);
    :root.dark & { color: #fca5a5; background: rgba(239, 68, 68, 0.2); }
  }
}

.period-selector {
  display: flex;
  gap: 0.25rem;
  background: var(--p-surface-ground);
  border-radius: 8px;
  padding: 0.2rem;
}

.period-btn {
  padding: 0.3rem 0.75rem;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--p-text-color-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    color: var(--p-text-color);
  }

  &.active {
    background: var(--p-surface-card);
    color: var(--p-primary-500);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  }
}

// Table Card
.table-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin: 0 0 0.75rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;

  i { color: var(--p-primary-500); font-size: 0.875rem; }
}

.table-wrapper {
  overflow-x: auto;
}

.price-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;

  th, td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--p-surface-border);
    white-space: nowrap;
  }

  th {
    font-weight: 600;
    color: var(--p-text-color-secondary);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  td {
    color: var(--p-text-color);
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .vol {
    color: var(--p-text-color-secondary);
  }

  .above-sma {
    color: #10b981;
    font-weight: 600;
  }

  .below-sma {
    color: #ef4444;
    font-weight: 600;
  }

  tbody tr:hover {
    background: var(--p-surface-hover);
  }
}

// States
.loading-state { padding: 1rem 0; }
.mb-4 { margin-bottom: 1rem; }
.mt-4 { margin-top: 1rem; }

.error-state {
  display: flex;
  justify-content: center;
  padding: 3rem 0;
}

.error-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  text-align: center;

  i { font-size: 2.5rem; color: #ef4444; }
  p { color: var(--p-text-color-secondary); margin: 0; }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 4rem 0;
  text-align: center;

  i { font-size: 3rem; color: var(--p-text-color-secondary); opacity: 0.5; }
  p { color: var(--p-text-color-secondary); margin: 0; }
  code {
    font-size: 0.8125rem;
    background: var(--p-surface-card);
    padding: 0.5rem 1rem;
    border-radius: 8px;
    border: 1px solid var(--p-surface-border);
  }
}
</style>
