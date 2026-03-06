<template>
  <div class="analysten-view">
    <div class="page-header">
      <h1 class="page-title">Analystenmeinungen</h1>
      <div class="header-actions">
        <span v-if="data?.date" class="last-sync">Stand: {{ data.date }}</span>
        <button
          class="sync-btn"
          :class="{ syncing }"
          :disabled="syncing"
          @click="syncAll"
        >
          <i class="pi pi-sync" :class="{ 'pi-spin': syncing }" />
          <span>{{ syncing ? 'Sync...' : 'Aktualisieren' }}</span>
        </button>
      </div>
    </div>

    <!-- Ticker Selector -->
    <div v-if="watchlist.length" class="ticker-bar">
      <button
        v-for="item in watchlist"
        :key="item.ticker"
        class="ticker-chip"
        :class="{ active: item.ticker === selectedTicker }"
        @click="selectTicker(item.ticker)"
      >
        <span class="ticker-symbol">{{ item.ticker }}</span>
        <span class="ticker-name">{{ item.name }}</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem; color: var(--p-primary-500)" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <div class="error-box">
        <i class="pi pi-exclamation-circle" />
        <p>{{ error }}</p>
      </div>
    </div>

    <!-- Empty watchlist -->
    <div v-else-if="!watchlist.length" class="empty-state">
      <i class="pi pi-users" />
      <p>Keine Assets in der Watchlist. Füge Assets unter News oder Research hinzu.</p>
    </div>

    <!-- Data -->
    <template v-else-if="data">
      <div class="ratings-card">
        <div class="ratings-header">
          <h2 class="asset-name">{{ data.name }}</h2>
          <span class="total-badge">{{ data.total }} Analysten</span>
        </div>

        <!-- Summary Bar -->
        <div class="ratings-bar" v-if="data.total > 0">
          <div
            v-for="seg in barSegments"
            :key="seg.key"
            class="bar-segment"
            :class="seg.key"
            :style="{ width: seg.pct + '%' }"
            v-tooltip.top="seg.label + ': ' + seg.count"
          />
        </div>

        <!-- Category Breakdown -->
        <div class="categories">
          <div
            v-for="cat in categories"
            :key="cat.key"
            class="category-row"
          >
            <div class="cat-label">
              <span class="cat-dot" :class="cat.key" />
              <span>{{ cat.label }}</span>
            </div>
            <div class="cat-bar-wrapper">
              <div
                class="cat-bar-fill"
                :class="cat.key"
                :style="{ width: data.total > 0 ? (cat.count / data.total * 100) + '%' : '0%' }"
              />
            </div>
            <span class="cat-count">{{ cat.count }}</span>
          </div>
        </div>
      </div>

      <!-- Analyst News Feed -->
      <div class="analyst-feed" v-if="data.individual.length">
        <h3 class="section-title">
          <i class="pi pi-megaphone" />
          Analysten-News (letzte 3 Wochen)
        </h3>
        <div class="feed-list">
          <div
            v-for="(r, i) in data.individual"
            :key="i"
            class="feed-card"
            :class="actionClass(r.action)"
          >
            <div class="feed-header">
              <span class="feed-firm">{{ r.firm }}</span>
              <span class="feed-date">{{ formatDate(r.date) }}</span>
            </div>
            <div class="feed-body">
              <span class="action-badge" :class="actionClass(r.action)">{{ actionLabel(r.action) }}</span>
              <span class="feed-arrow" v-if="r.fromGrade">
                <span class="grade-badge faded" :class="gradeClass(r.fromGrade)">{{ r.fromGrade }}</span>
                <i class="pi pi-arrow-right" />
              </span>
              <span class="grade-badge" :class="gradeClass(r.toGrade)">{{ r.toGrade }}</span>
            </div>
            <div class="feed-targets" v-if="r.currentPriceTarget">
              <span class="target-label">Kursziel:</span>
              <span class="target-value">${{ r.currentPriceTarget }}</span>
              <template v-if="r.priorPriceTarget && r.priorPriceTarget !== r.currentPriceTarget">
                <span class="target-change" :class="r.currentPriceTarget > r.priorPriceTarget ? 'up' : 'down'">
                  {{ r.currentPriceTarget > r.priorPriceTarget ? '+' : '' }}{{ ((r.currentPriceTarget - r.priorPriceTarget) / r.priorPriceTarget * 100).toFixed(1) }}%
                </span>
                <span class="target-prior">(vorher: ${{ r.priorPriceTarget }})</span>
              </template>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="no-individual">
        Keine Analysten-News in den letzten 3 Wochen.
      </div>

      <!-- RSS Analyst News -->
      <div class="rss-news-section" v-if="analystNews.length">
        <h3 class="section-title">
          <i class="pi pi-rss" />
          Analysten-News (RSS)
        </h3>
        <div
          v-for="(item, i) in analystNews"
          :key="i"
          class="rss-news-card"
        >
          <div class="rss-news-header">
            <span class="rss-news-date">{{ formatDate(item.date) }}</span>
            <div class="rss-news-badges">
              <span class="trend-badge" :class="item.trend">{{ trendLabel(item.trend) }}</span>
              <span class="consensus-badge" :class="item.consensus_direction">{{ consensusLabel(item.consensus_direction) }}</span>
            </div>
          </div>
          <p class="rss-news-summary">{{ item.summary }}</p>
          <p class="rss-news-development" v-if="item.development">
            <strong>Neu:</strong> {{ item.development }}
          </p>
          <p class="rss-news-recurring" v-if="item.recurring">
            <strong>Bestätigt sich:</strong> {{ item.recurring }}
          </p>
          <div class="rss-headlines" v-if="item.relevant_headlines?.length">
            <div
              v-for="(h, j) in item.relevant_headlines"
              :key="j"
              class="rss-headline"
            >
              <span class="headline-sentiment" :class="h.sentiment" />
              <a v-if="h.link" :href="h.link" target="_blank" class="headline-link">{{ h.title }}</a>
              <span v-else>{{ h.title }}</span>
              <span class="headline-source">{{ h.source }}</span>
            </div>
          </div>
          <div class="rss-news-footer" v-if="item.ampel_relevance">
            <span class="ampel-label">Ampel-Relevanz:</span> {{ item.ampel_relevance }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'

interface AnalystRating {
  date: string
  firm: string
  toGrade: string
  fromGrade: string
  action: string
  currentPriceTarget?: number
  priorPriceTarget?: number
}

interface AnalystData {
  ticker: string
  name: string
  summary: {
    strongBuy: number
    buy: number
    hold: number
    sell: number
    strongSell: number
  }
  total: number
  individual: AnalystRating[]
}

interface WatchlistItem {
  ticker: string
  name: string
  category: string
}

const watchlist = ref<WatchlistItem[]>([])
const selectedTicker = ref('')
const data = ref<AnalystData | null>(null)
const analystNews = ref<any[]>([])
const loading = ref(false)
const syncing = ref(false)
const error = ref<string | null>(null)

const categories = computed(() => {
  if (!data.value) return []
  const s = data.value.summary
  return [
    { key: 'strongBuy', label: 'Strong Buy', count: s.strongBuy },
    { key: 'buy', label: 'Buy', count: s.buy },
    { key: 'hold', label: 'Hold', count: s.hold },
    { key: 'sell', label: 'Sell', count: s.sell },
    { key: 'strongSell', label: 'Strong Sell', count: s.strongSell },
  ]
})

const barSegments = computed(() => {
  if (!data.value || data.value.total === 0) return []
  return categories.value
    .filter((c) => c.count > 0)
    .map((c) => ({
      key: c.key,
      label: c.label,
      count: c.count,
      pct: (c.count / data.value!.total) * 100,
    }))
})

async function loadWatchlist() {
  try {
    watchlist.value = await ApiService.get<WatchlistItem[]>(API_ENDPOINTS.PRICES.WATCHLIST)
  } catch (err) {
    console.error(err)
  }
}

async function loadRatings(ticker: string) {
  loading.value = true
  error.value = null
  data.value = null
  analystNews.value = []
  try {
    const [ratingsData, newsData] = await Promise.all([
      ApiService.get<AnalystData>(API_ENDPOINTS.PRICES.ANALYST_RATINGS(ticker)),
      ApiService.get<any[]>(API_ENDPOINTS.PRICES.ANALYST_NEWS(ticker)),
    ])
    data.value = ratingsData
    analystNews.value = newsData
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Fehler beim Laden der Analystenmeinungen'
    console.error(err)
  } finally {
    loading.value = false
  }
}

function selectTicker(ticker: string) {
  selectedTicker.value = ticker
  loadRatings(ticker)
}

async function syncAll() {
  syncing.value = true
  try {
    await Promise.all([
      ApiService.post(API_ENDPOINTS.PRICES.ANALYST_RATINGS_SYNC, {}),
      ApiService.post(API_ENDPOINTS.PRICES.ANALYST_NEWS_SYNC, {}),
    ])
    if (selectedTicker.value) {
      await loadRatings(selectedTicker.value)
    }
  } catch (err) {
    console.error(err)
  } finally {
    syncing.value = false
  }
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function gradeClass(grade: string): string {
  const g = grade.toLowerCase()
  if (g.includes('strong buy') || g === 'strong-buy') return 'strongBuy'
  if (g.includes('buy') || g === 'outperform' || g === 'overweight' || g === 'positive') return 'buy'
  if (g.includes('hold') || g === 'neutral' || g === 'equal-weight' || g === 'market perform' || g === 'sector perform' || g === 'in-line' || g === 'peer perform') return 'hold'
  if (g.includes('strong sell') || g === 'strong-sell') return 'strongSell'
  if (g.includes('sell') || g === 'underperform' || g === 'underweight' || g === 'negative' || g === 'reduce') return 'sell'
  return 'hold'
}

function trendLabel(trend: string): string {
  const map: Record<string, string> = {
    improving: 'Verbessernd',
    stable: 'Stabil',
    deteriorating: 'Verschlechternd',
  }
  return map[trend] || trend
}

function consensusLabel(dir: string): string {
  const map: Record<string, string> = {
    bullish: 'Bullish',
    neutral: 'Neutral',
    bearish: 'Bearish',
  }
  return map[dir] || dir
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    up: 'Upgrade',
    upgrade: 'Upgrade',
    down: 'Downgrade',
    downgrade: 'Downgrade',
    main: 'Bestätigt',
    init: 'Neu',
    initiated: 'Neu',
    reit: 'Bestätigt',
  }
  return map[action.toLowerCase()] || action
}

function actionClass(action: string): string {
  const a = action.toLowerCase()
  if (a === 'upgrade' || a === 'init' || a === 'initiated') return 'upgrade'
  if (a === 'downgrade') return 'downgrade'
  return 'maintain'
}

onMounted(async () => {
  await loadWatchlist()
  if (watchlist.value.length) {
    selectTicker(watchlist.value[0].ticker)
  }
})
</script>

<style lang="scss" scoped>
.analysten-view {
  padding: 1.5rem;
  max-width: 900px;
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

.last-sync {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}

.sync-btn {
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
  font-family: inherit;

  &:hover { border-color: var(--p-primary-400); }

  &.active {
    border-color: var(--p-primary-500);
    background: rgba(59, 130, 246, 0.08);
    .ticker-symbol { color: var(--p-primary-500); }
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

// Ratings Card
.ratings-card {
  border-radius: 12px;
  padding: 1.5rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  margin-bottom: 1.5rem;
}

.ratings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.asset-name {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--p-text-color);
  margin: 0;
}

.total-badge {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  background: var(--p-surface-ground);
}

// Bar Chart
.ratings-bar {
  display: flex;
  height: 28px;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}

.bar-segment {
  transition: width 0.4s ease;
  min-width: 2px;

  &.strongBuy { background: #059669; }
  &.buy { background: #34d399; }
  &.hold { background: #fbbf24; }
  &.sell { background: #f87171; }
  &.strongSell { background: #dc2626; }
}

// Categories
.categories {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.category-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.cat-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 110px;
  flex-shrink: 0;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--p-text-color);
}

.cat-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;

  &.strongBuy { background: #059669; }
  &.buy { background: #34d399; }
  &.hold { background: #fbbf24; }
  &.sell { background: #f87171; }
  &.strongSell { background: #dc2626; }
}

.cat-bar-wrapper {
  flex: 1;
  height: 20px;
  background: var(--p-surface-ground);
  border-radius: 6px;
  overflow: hidden;
}

.cat-bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.4s ease;

  &.strongBuy { background: #059669; }
  &.buy { background: #34d399; }
  &.hold { background: #fbbf24; }
  &.sell { background: #f87171; }
  &.strongSell { background: #dc2626; }
}

.cat-count {
  width: 30px;
  text-align: right;
  font-size: 0.875rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-color);
}

// Analyst Feed
.analyst-feed {
  margin-top: 1.5rem;
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

.feed-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.feed-card {
  border-radius: 10px;
  padding: 0.75rem 1rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  transition: border-color 0.15s;

  &.upgrade { border-left: 3px solid #059669; }
  &.downgrade { border-left: 3px solid #dc2626; }
  &.maintain { border-left: 3px solid var(--p-surface-border); }
}

.feed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.375rem;
}

.feed-firm {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.feed-date {
  font-size: 0.7rem;
  color: var(--p-text-color-secondary);
}

.feed-body {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.feed-arrow {
  display: flex;
  align-items: center;
  gap: 0.375rem;

  i {
    font-size: 0.625rem;
    color: var(--p-text-color-secondary);
  }
}

.feed-targets {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.375rem;
  font-size: 0.75rem;
}

.target-label {
  color: var(--p-text-color-secondary);
}

.target-value {
  font-weight: 700;
  color: var(--p-text-color);
  font-variant-numeric: tabular-nums;
}

.target-change {
  font-weight: 600;
  font-size: 0.7rem;
  padding: 0.0625rem 0.375rem;
  border-radius: 4px;

  &.up {
    color: #059669;
    background: rgba(16, 185, 129, 0.12);
    :root.dark & { color: #6ee7b7; background: rgba(16, 185, 129, 0.2); }
  }

  &.down {
    color: #dc2626;
    background: rgba(239, 68, 68, 0.12);
    :root.dark & { color: #fca5a5; background: rgba(239, 68, 68, 0.2); }
  }
}

.target-prior {
  color: var(--p-text-color-secondary);
  font-size: 0.7rem;
}

.grade-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;

  &.strongBuy { color: #059669; background: rgba(5, 150, 105, 0.12); }
  &.buy { color: #059669; background: rgba(52, 211, 153, 0.15); }
  &.hold { color: #b45309; background: rgba(251, 191, 36, 0.15); }
  &.sell { color: #dc2626; background: rgba(248, 113, 113, 0.15); }
  &.strongSell { color: #dc2626; background: rgba(220, 38, 38, 0.12); }

  &.faded { opacity: 0.6; }

  :root.dark & {
    &.strongBuy { color: #6ee7b7; background: rgba(5, 150, 105, 0.2); }
    &.buy { color: #6ee7b7; background: rgba(52, 211, 153, 0.2); }
    &.hold { color: #fcd34d; background: rgba(251, 191, 36, 0.2); }
    &.sell { color: #fca5a5; background: rgba(248, 113, 113, 0.2); }
    &.strongSell { color: #fca5a5; background: rgba(220, 38, 38, 0.2); }
  }
}

.no-grade {
  color: var(--p-text-color-secondary);
}

.action-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;

  &.upgrade { color: #059669; background: rgba(16, 185, 129, 0.12); }
  &.downgrade { color: #dc2626; background: rgba(239, 68, 68, 0.12); }
  &.maintain { color: var(--p-text-color-secondary); background: var(--p-surface-ground); }

  :root.dark & {
    &.upgrade { color: #6ee7b7; background: rgba(16, 185, 129, 0.2); }
    &.downgrade { color: #fca5a5; background: rgba(239, 68, 68, 0.2); }
  }
}

// RSS News Section
.rss-news-section {
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.rss-news-card {
  border-radius: 12px;
  padding: 1rem 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

.rss-news-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.rss-news-date {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}

.rss-news-badges {
  display: flex;
  gap: 0.375rem;
}

.trend-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;

  &.improving { color: #059669; background: rgba(16, 185, 129, 0.12); }
  &.stable { color: var(--p-text-color-secondary); background: var(--p-surface-ground); }
  &.deteriorating { color: #dc2626; background: rgba(239, 68, 68, 0.12); }

  :root.dark & {
    &.improving { color: #6ee7b7; background: rgba(16, 185, 129, 0.2); }
    &.deteriorating { color: #fca5a5; background: rgba(239, 68, 68, 0.2); }
  }
}

.consensus-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;

  &.bullish { color: #059669; background: rgba(16, 185, 129, 0.12); }
  &.neutral { color: var(--p-text-color-secondary); background: var(--p-surface-ground); }
  &.bearish { color: #dc2626; background: rgba(239, 68, 68, 0.12); }

  :root.dark & {
    &.bullish { color: #6ee7b7; background: rgba(16, 185, 129, 0.2); }
    &.bearish { color: #fca5a5; background: rgba(239, 68, 68, 0.2); }
  }
}

.rss-news-summary {
  font-size: 0.8125rem;
  color: var(--p-text-color);
  line-height: 1.5;
  margin: 0 0 0.5rem 0;
}

.rss-news-development,
.rss-news-recurring {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  line-height: 1.5;
  margin: 0 0 0.375rem 0;

  strong {
    color: var(--p-text-color);
    font-weight: 600;
  }
}

.rss-headlines {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin: 0.5rem 0;
  padding: 0.5rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
}

.rss-headline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
}

.headline-sentiment {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &.positive { background: #10b981; }
  &.negative { background: #ef4444; }
  &.neutral { background: #a1a1aa; }
}

.headline-link {
  color: var(--p-primary-500);
  text-decoration: none;
  flex: 1;

  &:hover { text-decoration: underline; }
}

.headline-source {
  color: var(--p-text-color-secondary);
  font-size: 0.6875rem;
  flex-shrink: 0;
}

.rss-news-footer {
  font-size: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--p-surface-border);
  color: var(--p-text-color);
}

.ampel-label {
  font-weight: 600;
  color: var(--p-text-color-secondary);
}

.no-individual {
  padding: 2rem;
  text-align: center;
  color: var(--p-text-color-secondary);
  font-size: 0.875rem;
  border-radius: 12px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

// States
.loading-state {
  display: flex;
  justify-content: center;
  padding: 3rem 0;
}

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
}
</style>
