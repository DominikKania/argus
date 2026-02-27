<template>
  <div class="thesen-view">
    <!-- Loading State -->
    <div v-if="ampelStore.loading" class="loading-state">
      <Skeleton width="250px" height="36px" border-radius="8px" class="mb-6" />
      <Skeleton v-for="i in 3" :key="i" height="180px" border-radius="12px" class="mb-4" />
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
    <div v-else-if="!ampelStore.theses.length" class="empty-state">
      <i class="pi pi-bookmark" />
      <p>Keine offenen Thesen vorhanden.</p>
    </div>

    <!-- Data -->
    <template v-else>
      <h1 class="page-title">
        Offene Thesen
        <span class="count-badge">{{ ampelStore.theses.length }}</span>
      </h1>

      <div class="theses-grid">
        <div v-for="thesis in ampelStore.theses" :key="thesis._id" class="thesis-card">
          <div class="thesis-header">
            <p class="thesis-statement">{{ thesis.statement }}</p>
            <div class="thesis-actions">
              <button class="chat-trigger" v-tooltip.top="'Besprechen & optimieren'" @click="reviewThesis(thesis)">
                <i class="pi pi-comments" />
              </button>
            </div>
          </div>

          <div v-if="thesis.catalyst" class="catalyst">
            <span class="catalyst-label">Katalysator:</span>
            <span class="catalyst-text">{{ thesis.catalyst }}</span>
            <span v-if="thesis.catalyst_date" class="catalyst-date-badge">
              <i class="pi pi-calendar" />
              {{ thesis.catalyst_date }}
              <span v-if="daysUntil(thesis.catalyst_date) >= 0" class="catalyst-countdown" :class="{ 'countdown-soon': daysUntil(thesis.catalyst_date) <= 7 }">
                ({{ daysUntil(thesis.catalyst_date) }} Tage)
              </span>
              <span v-else class="catalyst-countdown countdown-past">
                (abgelaufen)
              </span>
            </span>
          </div>

          <div class="scenarios">
            <div v-if="thesis.expected_if_positive" class="scenario scenario-positive">
              <span class="scenario-icon">+</span>
              <p class="scenario-text">{{ thesis.expected_if_positive }}</p>
            </div>
            <div v-if="thesis.expected_if_negative" class="scenario scenario-negative">
              <span class="scenario-icon">-</span>
              <p class="scenario-text">{{ thesis.expected_if_negative }}</p>
            </div>
          </div>

          <div class="thesis-meta">
            <span class="meta-date">
              <i class="pi pi-clock" />
              Erstellt: {{ thesis.created_date }}
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useAmpelStore } from '@/stores/ampelStore'
import { useChatStore } from '@/stores/chatStore'
import type { OpenThesis } from '@/types/ampel'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'

const ampelStore = useAmpelStore()
const chatStore = useChatStore()

function reviewThesis(thesis: OpenThesis) {
  chatStore.openForThesisReview({
    thesisId: thesis._id,
    statement: thesis.statement,
    thesis: {
      statement: thesis.statement,
      catalyst: thesis.catalyst || '',
      catalyst_date: thesis.catalyst_date || '',
      expected_if_positive: thesis.expected_if_positive || '',
      expected_if_negative: thesis.expected_if_negative || '',
    },
  })
}

// Watch for refined thesis from chat
watch(
  () => chatStore.refinedThesis,
  async (refined) => {
    if (refined && chatStore.thesisReviewContext) {
      const id = chatStore.thesisReviewContext.thesisId
      const updated = await ampelStore.updateThesis(id, {
        statement: refined.statement as string,
        catalyst: refined.catalyst as string,
        catalyst_date: refined.catalyst_date as string,
        expected_if_positive: refined.expected_if_positive as string,
        expected_if_negative: refined.expected_if_negative as string,
      })
      if (updated) {
        // Update review context with new data
        chatStore.thesisReviewContext.statement = updated.statement
        chatStore.thesisReviewContext.thesis = {
          statement: updated.statement,
          catalyst: updated.catalyst || '',
          catalyst_date: updated.catalyst_date || '',
          expected_if_positive: updated.expected_if_positive || '',
          expected_if_negative: updated.expected_if_negative || '',
        }
      }
      chatStore.refinedThesis = null
    }
  },
)

const daysUntil = (dateStr: string): number => {
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  const target = new Date(dateStr)
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}

const loadData = () => {
  ampelStore.fetchTheses()
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.thesen-view {
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
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.count-badge {
  font-size: 0.875rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 8px;
  background-color: var(--p-primary-500);
  color: white;
}

.theses-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.thesis-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.thesis-header {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
}

.thesis-statement {
  font-size: 0.9375rem;
  font-weight: 500;
  line-height: 1.5;
  color: var(--p-text-color);
  margin: 0;
  flex: 1;
}

.thesis-actions {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
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

  .thesis-card:hover & { opacity: 0.6; }
  &:hover { opacity: 1 !important; color: var(--p-primary-500); background: var(--p-surface-ground); }
}

.catalyst {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.8125rem;
}

.catalyst-label {
  font-weight: 600;
  color: var(--p-text-color-secondary);
}

.catalyst-text {
  color: var(--p-text-color);
}

.catalyst-date-badge {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  background: var(--p-surface-ground);
  color: var(--p-primary-500);
  font-weight: 600;

  i { font-size: 0.75rem; }
}

.catalyst-countdown {
  font-weight: 700;

  &.countdown-soon {
    color: #f59e0b;
    :root.dark & { color: #fcd34d; }
  }

  &.countdown-past {
    color: #ef4444;
    :root.dark & { color: #fca5a5; }
  }
}

.scenarios {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.scenario {
  display: flex;
  gap: 0.625rem;
  padding: 0.625rem 0.75rem;
  border-radius: 8px;
}

.scenario-positive {
  background-color: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.15);
  :root.dark & { background-color: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.2); }
}

.scenario-negative {
  background-color: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  :root.dark & { background-color: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.2); }
}

.scenario-icon {
  font-size: 1rem;
  font-weight: 700;
  flex-shrink: 0;
  width: 1.25rem;
  text-align: center;

  .scenario-positive & { color: #059669; :root.dark & { color: #6ee7b7; } }
  .scenario-negative & { color: #dc2626; :root.dark & { color: #fca5a5; } }
}

.scenario-text {
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  margin: 0;
}

.thesis-meta {
  padding-top: 0.5rem;
  border-top: 1px solid var(--p-surface-border);
}

.meta-date {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 0.25rem;

  i { font-size: 0.625rem; }
}

// States
.loading-state {
  padding: 1rem 0;
}

.mb-6 { margin-bottom: 1.5rem; }
.mb-4 { margin-bottom: 1rem; }

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
