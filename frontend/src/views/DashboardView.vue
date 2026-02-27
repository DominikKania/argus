<template>
  <div class="dashboard-view">
    <!-- Loading State -->
    <div v-if="ampelStore.loading" class="loading-state">
      <div class="header-skeleton mb-6">
        <Skeleton width="250px" height="36px" border-radius="8px" />
      </div>
      <div class="metric-grid">
        <Skeleton v-for="i in 4" :key="i" height="140px" border-radius="12px" />
      </div>
      <Skeleton height="80px" border-radius="12px" class="mt-6" />
      <Skeleton height="120px" border-radius="12px" class="mt-4" />
    </div>

    <!-- Error State -->
    <div v-else-if="ampelStore.error" class="error-state">
      <div class="error-box">
        <i class="pi pi-exclamation-circle" />
        <p>{{ ampelStore.error }}</p>
        <Button label="Erneut versuchen" icon="pi pi-refresh" severity="secondary" @click="loadData" />
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!analysis" class="empty-state">
      <i class="pi pi-inbox" />
      <p>Keine Daten vorhanden. Führe zuerst eine Ampel-Analyse durch.</p>
    </div>

    <!-- Data -->
    <template v-else>
      <h1 class="dashboard-title">Argus Dashboard</h1>

      <!-- Metric Cards -->
      <div class="metric-grid">
        <!-- Ampel Rating -->
        <div class="metric-card">
          <div class="metric-label">Ampel</div>
          <div class="metric-main">
            <span class="rating-dot" :class="ratingDotClass" />
            <span class="rating-text">{{ ratingLabel }}</span>
          </div>
          <div class="metric-sub">
            <span class="action-chip" :class="actionClass">{{ actionLabel }}</span>
          </div>
        </div>

        <!-- Kurs -->
        <div class="metric-card">
          <div class="metric-label">Kurs</div>
          <div class="metric-main">
            <span class="metric-value">{{ analysis.market.price.toFixed(2) }}€</span>
          </div>
          <div class="metric-sub">
            <span class="ath-delta" :class="{ 'near-ath': Math.abs(analysis.market.delta_ath_pct) < 2 }">
              ATH {{ analysis.market.delta_ath_pct > 0 ? '+' : '' }}{{ analysis.market.delta_ath_pct.toFixed(1) }}%
            </span>
            <span class="puffer-value" :class="{ 'puffer-warning': analysis.market.puffer_sma50_pct < 2 }">
              Puffer {{ analysis.market.puffer_sma50_pct.toFixed(1) }}%
            </span>
          </div>
        </div>

        <!-- VIX -->
        <div class="metric-card">
          <div class="metric-label">VIX</div>
          <div class="metric-main">
            <span class="metric-value">{{ analysis.market.vix.value.toFixed(1) }}</span>
            <span class="vix-direction" :class="vixDirectionClass">
              <i :class="vixDirectionIcon" />
              {{ vixDirectionLabel }}
            </span>
          </div>
          <div class="metric-sub">
            Vorwoche: {{ analysis.market.vix.prev_week.toFixed(1) }}
          </div>
        </div>

        <!-- Nächster Katalysator -->
        <div class="metric-card">
          <div class="metric-label">Nächster Katalysator</div>
          <template v-if="nextCatalyst">
            <div class="metric-main">
              <span class="catalyst-days" :class="{ 'catalyst-soon': nextCatalyst.daysUntil <= 7 }">
                {{ nextCatalyst.daysUntil }} Tage
              </span>
            </div>
            <div class="metric-sub catalyst-info">
              <i class="pi pi-calendar" />
              {{ nextCatalyst.date }}
            </div>
          </template>
          <div v-else class="metric-main">
            <span class="no-catalyst">Kein Katalysator</span>
          </div>
        </div>
      </div>

      <!-- Signal Overview -->
      <div class="signal-overview">
        <h3 class="section-title">
          <i class="pi pi-circle-fill" />
          Signale
        </h3>
        <div class="signal-row">
          <div v-for="name in signalOrder" :key="name" class="signal-item">
            <span class="signal-name">{{ signalLabels[name] }}</span>
            <span class="signal-dot" :class="`dot-${analysis.signals[name]?.mechanical}`" />
            <span class="signal-dot" :class="`dot-${analysis.signals[name]?.context}`" />
          </div>
        </div>
      </div>

      <!-- Open Theses -->
      <div v-if="ampelStore.theses.length" class="theses-preview" @click="goToTheses">
        <h3 class="section-title">
          <i class="pi pi-bookmark" />
          Offene Thesen ({{ ampelStore.theses.length }})
          <i class="pi pi-chevron-right chevron-icon" />
        </h3>
        <ul class="theses-list">
          <li v-for="thesis in ampelStore.theses.slice(0, 3)" :key="thesis._id" class="thesis-item">
            <span class="thesis-statement">{{ thesis.statement }}</span>
            <span v-if="thesis.catalyst_date" class="thesis-catalyst">
              <i class="pi pi-calendar" />
              {{ thesis.catalyst_date }}
            </span>
          </li>
        </ul>
      </div>

      <!-- Recommendation -->
      <div v-if="analysis.recommendation" class="recommendation-preview">
        <h3 class="section-title">
          <i class="pi pi-directions" />
          Empfehlung
        </h3>
        <p class="recommendation-text">{{ displayRecommendation }}</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAmpelStore } from '@/stores/ampelStore'
import { useDummyModeStore } from '@/stores/dummyModeStore'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'

const ampelStore = useAmpelStore()
const dummyModeStore = useDummyModeStore()
const router = useRouter()
const analysis = computed(() => ampelStore.latestAnalysis)

const displayRecommendation = computed(() => {
  if (dummyModeStore.isDummyMode && analysis.value?.simplified?.recommendation_detail) {
    return analysis.value.simplified.recommendation_detail
  }
  return analysis.value?.recommendation.detail || ''
})

const signalOrder = ['trend', 'volatility', 'macro', 'sentiment'] as const
const signalLabels: Record<string, string> = {
  trend: 'Trend',
  volatility: 'Vola',
  macro: 'Makro',
  sentiment: 'Sentiment',
}

const ratingMap: Record<string, { label: string; class: string }> = {
  GREEN: { label: 'GRÜN', class: 'dot-green' },
  GREEN_FRAGILE: { label: 'GRÜN (fragil)', class: 'dot-green-fragile' },
  YELLOW: { label: 'GELB', class: 'dot-yellow' },
  YELLOW_BEARISH: { label: 'GELB (bärisch)', class: 'dot-yellow' },
  RED: { label: 'ROT', class: 'dot-red' },
  RED_CAPITULATION: { label: 'ROT (Kapitulation)', class: 'dot-red' },
}

const ratingDotClass = computed(() => ratingMap[analysis.value?.rating.overall || '']?.class || '')
const ratingLabel = computed(() => ratingMap[analysis.value?.rating.overall || '']?.label || '')

const actionMap: Record<string, { label: string; class: string }> = {
  hold: { label: 'Halten', class: 'action-hold' },
  buy: { label: 'Kaufen', class: 'action-buy' },
  partial_sell: { label: 'Teilverkauf', class: 'action-sell' },
  hedge: { label: 'Absichern', class: 'action-hedge' },
  wait: { label: 'Abwarten', class: 'action-wait' },
}

const actionLabel = computed(() => actionMap[analysis.value?.recommendation.action || '']?.label || '')
const actionClass = computed(() => actionMap[analysis.value?.recommendation.action || '']?.class || '')

const vixDirectionClass = computed(() => ({
  'vix-rising': analysis.value?.market.vix.direction === 'rising',
  'vix-falling': analysis.value?.market.vix.direction === 'falling',
  'vix-flat': analysis.value?.market.vix.direction === 'flat',
}))

const vixDirectionIcon = computed(() => {
  const dir = analysis.value?.market.vix.direction
  if (dir === 'rising') return 'pi pi-arrow-up'
  if (dir === 'falling') return 'pi pi-arrow-down'
  return 'pi pi-minus'
})

const vixDirectionLabel = computed(() => {
  const dir = analysis.value?.market.vix.direction
  if (dir === 'rising') return 'steigend'
  if (dir === 'falling') return 'fallend'
  return 'stabil'
})

const nextCatalyst = computed(() => {
  // Check theses for catalyst dates
  const now = new Date()
  now.setHours(0, 0, 0, 0)

  let closest: { date: string; daysUntil: number } | null = null

  // From open theses
  for (const thesis of ampelStore.theses) {
    if (thesis.catalyst_date) {
      const d = new Date(thesis.catalyst_date)
      const diff = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
      if (diff >= 0 && (!closest || diff < closest.daysUntil)) {
        closest = { date: thesis.catalyst_date, daysUntil: diff }
      }
    }
  }

  // From current analysis thesis
  if (analysis.value?.thesis?.catalyst_date) {
    const d = new Date(analysis.value.thesis.catalyst_date)
    const diff = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
    if (diff >= 0 && (!closest || diff < closest.daysUntil)) {
      closest = { date: analysis.value.thesis.catalyst_date, daysUntil: diff }
    }
  }

  return closest
})

const goToTheses = () => {
  router.push('/thesen')
}

const loadData = () => {
  ampelStore.fetchDashboard()
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.dashboard-view {
  padding: 1.5rem;
  max-width: 1200px;
  overflow-y: auto;

  @media screen and (max-width: 640px) {
    padding: 1rem;
  }
}

.dashboard-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);
  margin: 0 0 1.5rem 0;
}

// Metric Cards Grid
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;

  @media screen and (max-width: 1024px) {
    grid-template-columns: repeat(2, 1fr);
  }

  @media screen and (max-width: 640px) {
    grid-template-columns: 1fr;
  }
}

.metric-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.metric-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-main {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.metric-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.metric-sub {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}

// Rating Dot
.rating-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;

  &.dot-green { background-color: #10b981; }
  &.dot-green-fragile {
    background-color: #10b981;
    border: 2px dashed rgba(16, 185, 129, 0.5);
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
  }
  &.dot-yellow { background-color: #f59e0b; }
  &.dot-red { background-color: #ef4444; }
}

.rating-text {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--p-text-color);
}

// Action Chip
.action-chip {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 6px;

  &.action-hold {
    background-color: rgba(16, 185, 129, 0.12);
    color: #059669;
    :root.dark & { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  }
  &.action-buy {
    background-color: rgba(59, 130, 246, 0.12);
    color: #2563eb;
    :root.dark & { background-color: rgba(59, 130, 246, 0.2); color: #93c5fd; }
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
    color: #6b7280;
    :root.dark & { background-color: rgba(107, 114, 128, 0.2); color: #d1d5db; }
  }
}

// ATH / Puffer
.ath-delta.near-ath {
  color: #10b981;
  font-weight: 600;
}

.puffer-value.puffer-warning {
  color: #f59e0b;
  font-weight: 600;
}

// VIX Direction
.vix-direction {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.8125rem;
  font-weight: 500;

  i { font-size: 0.75rem; }

  &.vix-rising { color: #ef4444; :root.dark & { color: #fca5a5; } }
  &.vix-falling { color: #10b981; :root.dark & { color: #6ee7b7; } }
  &.vix-flat { color: var(--p-text-color-secondary); }
}

// Catalyst
.catalyst-days {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);

  &.catalyst-soon {
    color: #f59e0b;
    :root.dark & { color: #fcd34d; }
  }
}

.catalyst-info {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  color: var(--p-primary-500);
  font-weight: 600;

  i { font-size: 0.75rem; }
}

.no-catalyst {
  font-size: 0.875rem;
  color: var(--p-text-color-secondary);
}

// Signal Overview
.signal-overview {
  border-radius: 12px;
  padding: 1rem 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  margin-bottom: 1.5rem;
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

.signal-row {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.signal-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.signal-name {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--p-text-color-secondary);
  min-width: 60px;
}

.signal-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;

  &.dot-green { background-color: #10b981; }
  &.dot-yellow { background-color: #f59e0b; }
  &.dot-red { background-color: #ef4444; }
}

// Theses Preview
.theses-preview {
  border-radius: 12px;
  padding: 1rem 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  margin-bottom: 1.5rem;
  cursor: pointer;
  transition: border-color 0.15s;

  &:hover {
    border-color: var(--p-primary-500);
  }

  .section-title {
    margin-bottom: 0.5rem;
  }

  .chevron-icon {
    margin-left: auto;
    font-size: 0.75rem;
    color: var(--p-text-color-secondary);
  }
}

.theses-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.thesis-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--p-surface-border);

  &:last-child { border-bottom: none; }
}

.thesis-statement {
  font-size: 0.8125rem;
  color: var(--p-text-color);
  line-height: 1.4;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thesis-catalyst {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-primary-500);
  white-space: nowrap;

  i { font-size: 0.625rem; }
}

// Recommendation Preview
.recommendation-preview {
  border-radius: 12px;
  padding: 1rem 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

.recommendation-text {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--p-text-color-secondary);
  margin: 0;
}

// States
.loading-state {
  padding: 1rem 0;
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

// Utility
.mt-6 { margin-top: 1.5rem; }
.mt-4 { margin-top: 1rem; }
.mb-6 { margin-bottom: 1.5rem; }
</style>
