<template>
  <div class="ampel-view">
    <!-- Loading State -->
    <div v-if="ampelStore.loading" class="loading-state">
      <div class="header-skeleton mb-6">
        <Skeleton width="300px" height="40px" border-radius="8px" />
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <Skeleton v-for="i in 4" :key="i" height="140px" border-radius="12px" />
      </div>
      <Skeleton height="250px" border-radius="12px" class="mb-6" />
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
      <p>Keine Analyse vorhanden.</p>
    </div>

    <!-- Data -->
    <template v-else>
      <AmpelHeader :analysis="analysis" />

      <!-- Signal Cards -->
      <div class="signal-grid">
        <SignalCard
          v-for="name in signalOrder"
          :key="name"
          :name="name"
          :signal="analysis.signals[name]"
        />
      </div>

      <!-- Market Data -->
      <MarketDataCard :market="analysis.market" />

      <!-- Top Holdings -->
      <TopHoldingsCard v-if="analysis.market.top_holdings" :holdings="analysis.market.top_holdings" />

      <!-- Earnings -->
      <EarningsCard v-if="analysis.market.earnings" :earnings="analysis.market.earnings" />

      <!-- Market Context (LLM-Interpretation der erweiterten Daten) -->
      <MarketContextCard v-if="analysis.market_context" :context="analysis.market_context" />

      <!-- Sentiment Events -->
      <SentimentEvents
        v-if="analysis.sentiment_events?.length"
        :events="analysis.sentiment_events"
      />

      <!-- Thesis & Recommendation -->
      <div class="bottom-grid">
        <ThesisCard v-if="analysis.thesis" :thesis="analysis.thesis" />
        <RecommendationCard :analysis="analysis" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAmpelStore } from '@/stores/ampelStore'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import AmpelHeader from '@/components/features/ampel/AmpelHeader.vue'
import SignalCard from '@/components/features/ampel/SignalCard.vue'
import MarketDataCard from '@/components/features/ampel/MarketDataCard.vue'
import TopHoldingsCard from '@/components/features/ampel/TopHoldingsCard.vue'
import EarningsCard from '@/components/features/ampel/EarningsCard.vue'
import MarketContextCard from '@/components/features/ampel/MarketContextCard.vue'
import SentimentEvents from '@/components/features/ampel/SentimentEvents.vue'
import ThesisCard from '@/components/features/ampel/ThesisCard.vue'
import RecommendationCard from '@/components/features/ampel/RecommendationCard.vue'

const ampelStore = useAmpelStore()
const analysis = computed(() => ampelStore.latestAnalysis)
const signalOrder = ['trend', 'volatility', 'macro', 'sentiment']

const loadData = () => {
  ampelStore.fetchLatest()
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.ampel-view {
  padding: 1.5rem;
  max-width: 1200px;
  overflow-y: auto;

  @media screen and (max-width: 640px) {
    padding: 1rem;
  }
}

.signal-grid {
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

.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-top: 1.5rem;

  @media screen and (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}

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

  i {
    font-size: 2.5rem;
    color: #ef4444;
  }

  p {
    color: var(--p-text-color-secondary);
    margin: 0;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 4rem 0;
  text-align: center;

  i {
    font-size: 3rem;
    color: var(--p-text-color-secondary);
    opacity: 0.5;
  }

  p {
    color: var(--p-text-color-secondary);
    margin: 0;
  }
}

// Gap between cards
.ampel-view > :deep(.market-data-card),
.ampel-view > :deep(.top-holdings-card),
.ampel-view > :deep(.earnings-card),
.ampel-view > :deep(.market-context-card),
.ampel-view > :deep(.sentiment-events) {
  margin-bottom: 1.5rem;
}

</style>
