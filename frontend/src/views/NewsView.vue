<template>
  <div class="news-view">
    <!-- Loading -->
    <div v-if="newsStore.loading && !newsStore.topics.length" class="loading-state">
      <Skeleton width="250px" height="36px" border-radius="8px" class="mb-4" />
      <div class="master-detail-skeleton">
        <Skeleton height="400px" width="280px" border-radius="12px" />
        <Skeleton height="400px" border-radius="12px" style="flex:1" />
      </div>
    </div>

    <!-- Content -->
    <template v-else>
      <div class="page-header">
        <h1 class="page-title">
          News Monitor
          <span v-if="newsStore.topics.length" class="count-badge">{{ newsStore.topics.length }}</span>
        </h1>
        <div class="header-actions">
          <Button
            label="Alle ausführen"
            icon="pi pi-play"
            size="small"
            severity="secondary"
            :loading="newsStore.running && runningAll"
            :disabled="!activeTopicsCount || newsStore.running"
            @click="runAllTopics"
          />
          <Button label="Neues Thema" icon="pi pi-plus" size="small" @click="showNewDialog = true; createError = ''; newDirection = ''" />
        </div>
      </div>

      <div class="master-detail">
        <!-- Topic List (Master) -->
        <div class="topic-list">
          <div v-if="!newsStore.topics.length" class="empty-list">
            <i class="pi pi-megaphone" />
            <p>Noch keine News-Themen.</p>
          </div>
          <button
            v-for="t in newsStore.topics"
            :key="t._id"
            class="topic-item"
            :class="{ active: newsStore.selectedTopic?._id === t._id }"
            @click="selectTopic(t)"
          >
            <span class="topic-trend-dot" :class="`trend-${t.latest_result?.trend || 'none'}`" />
            <div class="topic-item-text">
              <span class="topic-item-title">{{ t.title }}</span>
              <span class="topic-item-meta">
                <span v-if="!t.active" class="inactive-label">Inaktiv</span>
                <template v-else-if="t.latest_result">
                  {{ t.latest_result.date }}
                </template>
                <template v-else>Noch nicht analysiert</template>
              </span>
            </div>
          </button>
        </div>

        <!-- Detail Panel -->
        <div class="detail-panel" v-if="newsStore.selectedTopic">
          <div class="detail-header">
            <div class="detail-title-row">
              <h2 class="detail-title">{{ newsStore.selectedTopic.title }}</h2>
              <span
                class="active-badge"
                :class="newsStore.selectedTopic.active ? 'badge-active' : 'badge-inactive'"
                @click="toggleSelectedActive"
              >
                {{ newsStore.selectedTopic.active ? 'Aktiv' : 'Inaktiv' }}
              </span>
            </div>
            <div class="detail-actions">
              <Button
                label="Analysieren"
                icon="pi pi-play"
                size="small"
                :loading="newsStore.running && !runningAll"
                :disabled="!newsStore.selectedTopic.prompt?.trim() || newsStore.running"
                @click="runSelected"
              />
              <Button
                label="Speichern"
                icon="pi pi-save"
                size="small"
                severity="secondary"
                :disabled="!promptDirty"
                @click="savePrompt"
              />
              <Button
                icon="pi pi-comments"
                size="small"
                severity="secondary"
                text
                rounded
                v-tooltip.top="'Frag den Tutor'"
                @click="askAbout"
              />
              <Button
                icon="pi pi-trash"
                size="small"
                severity="danger"
                text
                rounded
                v-tooltip.top="'Löschen'"
                @click="deleteSelected"
              />
            </div>
          </div>

          <!-- Prompt Editor -->
          <div class="prompt-section">
            <div class="section-header">
              <label class="section-label">News-Analyse-Prompt</label>
              <div class="section-actions">
                <Button
                  label="Besprechen"
                  icon="pi pi-comments"
                  size="small"
                  severity="secondary"
                  text
                  :disabled="!editablePrompt.trim()"
                  @click="chatAboutPrompt"
                />
                <Button
                  label="Generieren"
                  icon="pi pi-sparkles"
                  size="small"
                  severity="secondary"
                  text
                  :loading="generatingPrompt"
                  @click="regeneratePrompt"
                />
              </div>
            </div>
            <textarea
              v-model="editablePrompt"
              class="prompt-editor"
              placeholder="News-Analyse-Prompt hier eingeben oder generieren lassen..."
            />
          </div>

          <!-- Latest Result -->
          <div v-if="latestResult" class="results-section">
            <div class="results-header">
              <label class="section-label">Letztes Ergebnis</label>
              <div class="results-meta">
                <span><i class="pi pi-clock" /> {{ latestResult.date }}</span>
                <span><i class="pi pi-list" /> {{ latestResult.headlines_fetched }} Headlines</span>
              </div>
            </div>

            <!-- Trend Badge -->
            <div class="trend-row">
              <span class="trend-badge" :class="`trend-badge-${latestResult.trend}`">
                <i :class="trendIcon(latestResult.trend)" />
                {{ trendLabel(latestResult.trend) }}
              </span>
            </div>

            <!-- Summary -->
            <div class="summary-box">
              {{ latestResult.summary }}
            </div>

            <!-- Development: Was ist neu? -->
            <div v-if="latestResult.development" class="development-box">
              <label class="section-label">Neue Entwicklung</label>
              <p>{{ latestResult.development }}</p>
            </div>

            <!-- Recurring: Was bestätigt sich? -->
            <div v-if="latestResult.recurring" class="recurring-box">
              <label class="section-label">Bestätigt sich</label>
              <p>{{ latestResult.recurring }}</p>
            </div>

            <!-- Relevant Headlines -->
            <div v-if="latestResult.relevant_headlines?.length" class="headlines-section">
              <label class="section-label">Relevante Headlines</label>
              <div
                v-for="(h, i) in latestResult.relevant_headlines"
                :key="i"
                class="headline-item"
              >
                <span class="headline-sentiment" :class="`sentiment-${h.sentiment}`" />
                <div class="headline-content">
                  <a v-if="h.link" :href="h.link" target="_blank" rel="noopener" class="headline-title headline-link">{{ h.title }}</a>
                  <span v-else class="headline-title">{{ h.title }}</span>
                  <span v-if="h.source" class="headline-source">{{ h.source }}</span>
                </div>
                <span class="headline-relevance" :class="`relevance-${h.relevance}`">{{ h.relevance }}</span>
              </div>
            </div>

            <!-- Triggers -->
            <div v-if="latestResult.triggers_detected?.length" class="triggers-section">
              <label class="section-label">Erkannte Trigger</label>
              <ul class="trigger-list">
                <li v-for="(trigger, i) in latestResult.triggers_detected" :key="i">{{ trigger }}</li>
              </ul>
            </div>

            <!-- Ampel Relevance -->
            <div v-if="latestResult.ampel_relevance" class="relevance-box">
              <span class="relevance-label">Relevanz für Ampel:</span>
              {{ latestResult.ampel_relevance }}
            </div>

            <!-- Deep Research -->
            <div v-if="latestResult.deep_research" class="deep-research-section">
              <button class="deep-research-toggle" @click="deepResearchOpen = !deepResearchOpen">
                <i :class="deepResearchOpen ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
                <label class="section-label">Deep Research</label>
              </button>
              <div v-if="deepResearchOpen" class="deep-research-content" v-html="renderMarkdown(latestResult.deep_research)" />
            </div>

          </div>

          <!-- Results History -->
          <div v-if="newsStore.selectedTopic.results_history?.length && newsStore.selectedTopic.results_history.length > 1" class="history-section">
            <label class="section-label">Verlauf</label>
            <div class="history-list">
              <div
                v-for="r in newsStore.selectedTopic.results_history.slice(1)"
                :key="r._id"
                class="history-item"
              >
                <span class="history-date">{{ r.date }}</span>
                <span class="trend-badge-small" :class="`trend-badge-${r.trend}`">
                  <i :class="trendIcon(r.trend)" />
                  {{ trendLabel(r.trend) }}
                </span>
                <span class="history-summary">{{ r.summary }}</span>
              </div>
            </div>
          </div>

          <!-- No results yet -->
          <div v-if="!latestResult && newsStore.selectedTopic.prompt?.trim()" class="no-results">
            <i class="pi pi-play-circle" />
            <p>Klicke "Analysieren" um die News-Analyse zu starten.</p>
          </div>
        </div>

        <!-- No selection -->
        <div v-else class="detail-panel detail-empty">
          <i class="pi pi-megaphone" />
          <p>Wähle ein Thema aus oder erstelle ein neues.</p>
        </div>
      </div>
    </template>

    <!-- New Topic Dialog -->
    <Dialog
      v-model:visible="showNewDialog"
      header="Neues News-Thema"
      :modal="true"
      :style="{ width: '500px' }"
      :closable="!creating"
    >
      <div class="new-topic-form">
        <label class="form-label">Thema</label>
        <InputText
          v-model="newTitle"
          placeholder="z.B. Zoll-Entwicklung"
          class="w-full"
          :disabled="creating"
        />
        <label class="form-label">Fokus / Richtung <small class="optional-hint">(optional)</small></label>
        <Textarea
          v-model="newDirection"
          placeholder="z.B. Auswirkungen auf MSCI World, Eskalation/De-Eskalation, Vergeltungsmaßnahmen..."
          class="w-full"
          :disabled="creating"
          rows="3"
          autoResize
        />
        <small class="form-hint">Beschreibe grob worauf der News-Prompt fokussieren soll. Die KI baut daraus einen detaillierten Analyse-Prompt.</small>
        <div v-if="createError" class="create-error">
          <i class="pi pi-exclamation-circle" />
          {{ createError }}
        </div>
      </div>
      <template #footer>
        <Button label="Abbrechen" severity="secondary" text @click="closeNewDialog" :disabled="creating" />
        <Button label="Erstellen" icon="pi pi-plus" :loading="creating" :disabled="!newTitle.trim()" @click="createNewTopic" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { marked } from 'marked'
import { useNewsStore } from '@/stores/newsStore'
import { useChatStore } from '@/stores/chatStore'
import type { NewsTopic, NewsResult } from '@/types/news'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'

const newsStore = useNewsStore()
const chatStore = useChatStore()

const showNewDialog = ref(false)
const newTitle = ref('')
const newDirection = ref('')
const creating = ref(false)
const createError = ref('')
const generatingPrompt = ref(false)
const editablePrompt = ref('')
const runningAll = ref(false)
const deepResearchOpen = ref(true)

function renderMarkdown(md: string): string {
  return marked.parse(md, { async: false }) as string
}

const activeTopicsCount = computed(() => newsStore.topics.filter((t) => t.active).length)

const latestResult = computed<NewsResult | null>(() => {
  if (!newsStore.selectedTopic) return null
  if (newsStore.selectedTopic.results_history?.length) {
    return newsStore.selectedTopic.results_history[0]
  }
  return newsStore.selectedTopic.latest_result || null
})

// Track prompt changes
const promptDirty = computed(() => {
  if (!newsStore.selectedTopic) return false
  return editablePrompt.value !== newsStore.selectedTopic.prompt
})

// Sync editable prompt when selection changes
watch(
  () => newsStore.selectedTopic,
  (topic) => {
    editablePrompt.value = topic?.prompt || ''
  },
  { immediate: true },
)

function trendIcon(trend: string) {
  switch (trend) {
    case 'improving': return 'pi pi-arrow-up'
    case 'deteriorating': return 'pi pi-arrow-down'
    default: return 'pi pi-minus'
  }
}

function trendLabel(trend: string) {
  switch (trend) {
    case 'improving': return 'Verbessernd'
    case 'deteriorating': return 'Verschlechternd'
    default: return 'Stabil'
  }
}

function selectTopic(topic: NewsTopic) {
  newsStore.selectedTopic = topic
  newsStore.fetchTopic(topic._id)
}

function closeNewDialog() {
  showNewDialog.value = false
  newTitle.value = ''
  newDirection.value = ''
  createError.value = ''
}

async function createNewTopic() {
  if (!newTitle.value.trim()) return
  creating.value = true
  createError.value = ''
  const created = await newsStore.createTopic(
    newTitle.value.trim(),
    undefined,
    newDirection.value.trim() || undefined,
  )
  creating.value = false
  if (created) {
    closeNewDialog()
  } else {
    createError.value = newsStore.error || 'Fehler beim Erstellen'
  }
}

async function regeneratePrompt() {
  if (!newsStore.selectedTopic) return
  generatingPrompt.value = true
  const prompt = await newsStore.generatePrompt(newsStore.selectedTopic.title)
  generatingPrompt.value = false
  if (prompt) {
    editablePrompt.value = prompt
  }
}

async function savePrompt() {
  if (!newsStore.selectedTopic || !promptDirty.value) return
  await newsStore.updateTopic(newsStore.selectedTopic._id, {
    prompt: editablePrompt.value,
  })
}

async function runSelected() {
  if (!newsStore.selectedTopic) return
  if (promptDirty.value) await savePrompt()
  await newsStore.runTopic(newsStore.selectedTopic._id)
}

async function runAllTopics() {
  runningAll.value = true
  await newsStore.runAll()
  runningAll.value = false
}

async function toggleSelectedActive() {
  if (!newsStore.selectedTopic) return
  await newsStore.toggleActive(newsStore.selectedTopic._id)
}

async function deleteSelected() {
  if (!newsStore.selectedTopic) return
  await newsStore.deleteTopic(newsStore.selectedTopic._id)
}

function chatAboutPrompt() {
  if (!newsStore.selectedTopic || !editablePrompt.value.trim()) return
  const t = newsStore.selectedTopic
  chatStore.openForPromptReview({
    topicId: t._id,
    topicTitle: t.title,
    prompt: editablePrompt.value,
  })
}

// Watch for refined prompt from chat
watch(
  () => chatStore.refinedPrompt,
  (refined) => {
    if (refined && chatStore.promptReviewContext) {
      editablePrompt.value = refined
      chatStore.promptReviewContext.prompt = refined
      chatStore.refinedPrompt = null
    }
  },
)

function askAbout() {
  if (!newsStore.selectedTopic) return
  const t = newsStore.selectedTopic
  let msg = `Erkläre mir das News-Thema: ${t.title}`
  if (latestResult.value?.summary) {
    msg += `\n\nLetzte Analyse: ${latestResult.value.summary}`
  }
  chatStore.openWithContext(msg)
}

onMounted(() => {
  newsStore.fetchTopics()
})
</script>

<style lang="scss" scoped>
.news-view {
  padding: 1.5rem;
  max-width: 1400px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  @media screen and (max-width: 640px) {
    padding: 1rem;
  }
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);
  margin: 0;
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

.header-actions {
  display: flex;
  gap: 0.5rem;
}

// Master-Detail Layout
.master-detail {
  display: flex;
  gap: 1rem;
  flex: 1;
  min-height: 0;

  @media screen and (max-width: 768px) {
    flex-direction: column;
  }
}

.master-detail-skeleton {
  display: flex;
  gap: 1rem;
}

// Topic List
.topic-list {
  width: 280px;
  flex-shrink: 0;
  border: 1px solid var(--p-surface-border);
  border-radius: 12px;
  background: var(--p-surface-card);
  overflow-y: auto;

  @media screen and (max-width: 768px) {
    width: 100%;
    max-height: 200px;
  }
}

.empty-list {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem 1rem;
  text-align: center;
  color: var(--p-text-color-secondary);

  i { font-size: 2rem; opacity: 0.5; }
  p { margin: 0; font-size: 0.8125rem; }
}

.topic-item {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  width: 100%;
  padding: 0.75rem 1rem;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  border-bottom: 1px solid var(--p-surface-border);
  transition: background 0.15s;

  &:hover { background: var(--p-surface-ground); }
  &.active { background: var(--p-surface-ground); border-left: 3px solid var(--p-primary-500); }
  &:last-child { border-bottom: none; }
}

.topic-trend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &.trend-improving { background: #10b981; }
  &.trend-stable { background: #3b82f6; }
  &.trend-deteriorating { background: #ef4444; }
  &.trend-none { background: #9ca3af; }
}

.topic-item-text {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  min-width: 0;
}

.topic-item-title {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--p-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topic-item-meta {
  font-size: 0.6875rem;
  color: var(--p-text-color-secondary);
}

.inactive-label {
  color: #9ca3af;
  font-style: italic;
}

// Detail Panel
.detail-panel {
  flex: 1;
  border: 1px solid var(--p-surface-border);
  border-radius: 12px;
  background: var(--p-surface-card);
  padding: 1.25rem;
  overflow-y: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;

  &.detail-empty {
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    color: var(--p-text-color-secondary);

    i { font-size: 3rem; opacity: 0.4; }
    p { margin: 0; }
  }
}

.detail-header {
  margin-bottom: 1.25rem;
  flex-shrink: 0;
}

.detail-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.detail-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin: 0;
  flex: 1;
}

.active-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.625rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
  cursor: pointer;
  transition: opacity 0.15s;

  &:hover { opacity: 0.8; }

  &.badge-active {
    background: #ecfdf5;
    color: #059669;
    :root.dark & { background: #064e3b; color: #6ee7b7; }
  }

  &.badge-inactive {
    background: #f3f4f6;
    color: #6b7280;
    :root.dark & { background: #374151; color: #9ca3af; }
  }
}

.detail-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

// Prompt Editor
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;

  .section-label { margin-bottom: 0; }
}

.section-actions {
  display: flex;
  gap: 0.25rem;
}

.section-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

.prompt-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 150px;
}

.prompt-editor {
  width: 100%;
  flex: 1;
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  padding: 0.75rem;
  font-size: 0.8125rem;
  font-family: inherit;
  line-height: 1.6;
  color: var(--p-text-color);
  background: var(--p-surface-ground);
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;

  &:focus { border-color: var(--p-primary-500); }
  &::placeholder { color: var(--p-text-color-secondary); }
}

// Results
.results-section {
  border-top: 1px solid var(--p-surface-border);
  padding-top: 1rem;
  margin-top: 1rem;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;

  .section-label { margin-bottom: 0; }
}

.results-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);

  i { font-size: 0.625rem; }
}

// Trend
.trend-row {
  margin-bottom: 0.75rem;
}

.trend-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.3rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8125rem;
  font-weight: 600;

  i { font-size: 0.75rem; }

  &.trend-badge-improving {
    background: #ecfdf5;
    color: #059669;
    :root.dark & { background: #064e3b; color: #6ee7b7; }
  }

  &.trend-badge-stable {
    background: #eff6ff;
    color: #3b82f6;
    :root.dark & { background: #1e3a5f; color: #60a5fa; }
  }

  &.trend-badge-deteriorating {
    background: #fef2f2;
    color: #ef4444;
    :root.dark & { background: #450a0a; color: #fca5a5; }
  }
}

.trend-badge-small {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.6875rem;
  font-weight: 600;
  flex-shrink: 0;

  i { font-size: 0.625rem; }

  &.trend-badge-improving {
    background: #ecfdf5;
    color: #059669;
    :root.dark & { background: #064e3b; color: #6ee7b7; }
  }

  &.trend-badge-stable {
    background: #eff6ff;
    color: #3b82f6;
    :root.dark & { background: #1e3a5f; color: #60a5fa; }
  }

  &.trend-badge-deteriorating {
    background: #fef2f2;
    color: #ef4444;
    :root.dark & { background: #450a0a; color: #fca5a5; }
  }
}

// Summary
.summary-box {
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--p-text-color);
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  margin-bottom: 1rem;
}

// Development & Recurring
.development-box, .recurring-box {
  font-size: 0.8125rem;
  line-height: 1.7;
  padding: 0.75rem;
  border-radius: 8px;
  margin-bottom: 0.75rem;

  .section-label { margin-bottom: 0.25rem; }
  p { margin: 0; color: var(--p-text-color); }
}

.development-box {
  background: rgba(245, 158, 11, 0.06);
  border-left: 3px solid #f59e0b;

  :root.dark & {
    background: rgba(245, 158, 11, 0.08);
  }

  .section-label { color: #d97706; :root.dark & { color: #fbbf24; } }
}

.recurring-box {
  background: rgba(59, 130, 246, 0.06);
  border-left: 3px solid #93c5fd;

  :root.dark & {
    background: rgba(59, 130, 246, 0.08);
  }

  .section-label { color: #3b82f6; :root.dark & { color: #93c5fd; } }
}

// Headlines
.headlines-section {
  margin-bottom: 1rem;
}

.headline-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--p-surface-border);
  font-size: 0.8125rem;

  &:last-child { border-bottom: none; }
}

.headline-sentiment {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 0.35rem;

  &.sentiment-positive { background: #10b981; }
  &.sentiment-negative { background: #ef4444; }
  &.sentiment-neutral { background: #9ca3af; }
}

.headline-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.headline-title {
  color: var(--p-text-color);
}

.headline-link {
  text-decoration: none;
  &:hover { text-decoration: underline; color: var(--p-primary-500); }
}

.headline-source {
  font-size: 0.6875rem;
  color: var(--p-text-color-secondary);
}

.headline-relevance {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  flex-shrink: 0;

  &.relevance-high { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
  &.relevance-medium { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
  &.relevance-low { background: rgba(156, 163, 175, 0.1); color: #9ca3af; }
}

// Triggers
.triggers-section {
  margin-bottom: 1rem;
}

.trigger-list {
  padding-left: 1.25rem;
  margin: 0.25rem 0 0;
  font-size: 0.8125rem;
  color: var(--p-text-color);

  li {
    margin: 0.25rem 0;
    line-height: 1.5;
  }
}

// Relevance
.relevance-box {
  padding: 0.75rem;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.15);
  font-size: 0.8125rem;
  line-height: 1.5;

  :root.dark & {
    background: rgba(16, 185, 129, 0.08);
    border-color: rgba(16, 185, 129, 0.2);
  }
}

.relevance-label {
  font-weight: 600;
  color: #059669;
  :root.dark & { color: #6ee7b7; }
}

// Deep Research
.deep-research-section {
  border-top: 1px solid var(--p-surface-border);
  padding-top: 1rem;
  margin-top: 1rem;
}

.deep-research-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  margin-bottom: 0.75rem;

  i {
    font-size: 0.75rem;
    color: var(--p-text-color-secondary);
    transition: transform 0.15s;
  }

  .section-label {
    margin-bottom: 0;
    cursor: pointer;
  }

  &:hover .section-label { color: var(--p-text-color); }
}

.deep-research-content {
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--p-text-color);
  padding: 1rem;
  border-radius: 8px;
  background: var(--p-surface-ground);

  :deep(h3) {
    font-size: 0.875rem;
    font-weight: 600;
    margin: 1rem 0 0.5rem;
    color: var(--p-text-color);

    &:first-child { margin-top: 0; }
  }

  :deep(h4) {
    font-size: 0.8125rem;
    font-weight: 600;
    margin: 0.75rem 0 0.375rem;
  }

  :deep(p) {
    margin: 0.375rem 0;
  }

  :deep(ul), :deep(ol) {
    padding-left: 1.25rem;
    margin: 0.375rem 0;
  }

  :deep(li) {
    margin: 0.25rem 0;
  }

  :deep(strong) {
    font-weight: 600;
    color: var(--p-text-color);
  }
}

// History
.history-section {
  border-top: 1px solid var(--p-surface-border);
  padding-top: 1rem;
  margin-top: 1rem;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  font-size: 0.8125rem;
}

.history-date {
  font-weight: 600;
  color: var(--p-text-color-secondary);
  flex-shrink: 0;
  font-size: 0.75rem;
}

.history-summary {
  color: var(--p-text-color);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.no-results {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem;
  text-align: center;
  color: var(--p-text-color-secondary);

  i { font-size: 2rem; opacity: 0.4; }
  p { margin: 0; font-size: 0.8125rem; }
}

// States
.loading-state {
  padding: 1rem 0;
}

.mb-4 { margin-bottom: 1rem; }

// Dialog
.new-topic-form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color);

  .optional-hint {
    font-weight: 400;
    color: var(--p-text-color-secondary);
  }
}

.form-hint {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}

.create-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.8125rem;

  :root.dark & {
    background: rgba(239, 68, 68, 0.12);
    color: #fca5a5;
  }
}

.w-full { width: 100%; }
</style>
