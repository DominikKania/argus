<template>
  <div class="search-view">
    <h1 class="search-title">Wissen</h1>
    <p class="search-subtitle">Stelle Fragen an dein Argus-System — Antworten basieren auf Thesen, Analysen, News und Erkenntnissen</p>

    <!-- Search Input -->
    <div class="search-bar">
      <span class="search-input-wrapper">
        <i class="pi pi-question-circle" />
        <InputText
          v-model="query"
          placeholder="z.B. Bestätigen die aktuellen News meine These?"
          class="search-input"
          @keydown.enter="doSearch"
        />
      </span>
      <Button
        label="Fragen"
        icon="pi pi-send"
        :loading="loading"
        :disabled="!query.trim()"
        @click="doSearch"
      />
    </div>

    <!-- Empty initial state -->
    <div v-if="!hasSearched && !loading" class="empty-state">
      <i class="pi pi-compass" />
      <p>Stelle eine Frage zu deinem Portfolio, deinen Thesen oder der Marktlage.</p>
      <div class="search-hints">
        <span class="hint-chip" @click="useHint('Bestätigen die aktuellen News meine offene These?')">News vs. These</span>
        <span class="hint-chip" @click="useHint('Hat sich die Marktlage seit der letzten Analyse verschlechtert?')">Marktlage-Trend</span>
        <span class="hint-chip" @click="useHint('Welche Risiken tauchen in mehreren Quellen auf?')">Risiko-Muster</span>
        <span class="hint-chip" @click="useHint('Ist mein Stop-Loss noch sinnvoll bei der aktuellen Nachrichtenlage?')">Stop-Loss Check</span>
        <span class="hint-chip" @click="useHint('Gibt es Anzeichen für eine Deeskalation bei den Zöllen?')">Zoll-Deeskalation</span>
        <span class="hint-chip" @click="useHint('Wann war die Lage zuletzt ähnlich und was ist passiert?')">Historischer Vergleich</span>
      </div>
    </div>

    <!-- Answer area -->
    <div v-if="hasSearched" class="answer-area">
      <!-- Loading skeleton -->
      <div v-if="loading && !answer" class="loading-answer">
        <Skeleton width="100%" height="1rem" border-radius="6px" class="mb-2" />
        <Skeleton width="90%" height="1rem" border-radius="6px" class="mb-2" />
        <Skeleton width="95%" height="1rem" border-radius="6px" class="mb-2" />
        <Skeleton width="70%" height="1rem" border-radius="6px" />
      </div>

      <!-- Streamed answer -->
      <div v-if="answer" class="answer-card">
        <div class="answer-header">
          <i class="pi pi-sparkles" />
          <span>Antwort</span>
        </div>
        <div class="answer-text" v-html="renderedAnswer" />
      </div>

      <!-- Sources (collapsible) -->
      <div v-if="Object.keys(sources).length > 0" class="sources-section">
        <button class="sources-toggle" @click="showSources = !showSources">
          <i :class="showSources ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
          <span>Quellen ({{ totalSources }} Belege)</span>
        </button>

        <div v-if="showSources" class="sources-list">
          <!-- Theses -->
          <div v-if="sources.theses?.length" class="source-group">
            <h4 class="source-group-title"><i class="pi pi-bookmark" /> Thesen</h4>
            <div v-for="item in sources.theses" :key="item.id" class="source-item">
              <span class="source-similarity" :class="distanceClass(item.distance)">{{ similarityLabel(item.distance) }}</span>
              <p class="source-text">{{ truncate(item.document, 200) }}</p>
            </div>
          </div>

          <!-- Analyses -->
          <div v-if="sources.analyses?.length" class="source-group">
            <h4 class="source-group-title"><i class="pi pi-chart-bar" /> Analysen</h4>
            <div v-for="item in sources.analyses" :key="item.id" class="source-item">
              <div class="source-meta">
                <span class="source-similarity" :class="distanceClass(item.distance)">{{ similarityLabel(item.distance) }}</span>
                <span v-if="item.metadata?.date" class="source-date">{{ item.metadata.date }}</span>
                <span v-if="item.metadata?.overall" class="source-rating" :class="`rating-${item.metadata.overall?.toLowerCase()}`">{{ item.metadata.overall }}</span>
              </div>
              <p class="source-text">{{ truncate(item.document, 250) }}</p>
            </div>
          </div>

          <!-- Lessons -->
          <div v-if="sources.lessons?.length" class="source-group">
            <h4 class="source-group-title"><i class="pi pi-lightbulb" /> Erkenntnisse</h4>
            <div v-for="item in sources.lessons" :key="item.id" class="source-item">
              <span class="source-similarity" :class="distanceClass(item.distance)">{{ similarityLabel(item.distance) }}</span>
              <p class="source-text">{{ truncate(item.document, 200) }}</p>
            </div>
          </div>

          <!-- Research -->
          <div v-if="sources.research?.length" class="source-group">
            <h4 class="source-group-title"><i class="pi pi-file-edit" /> Research</h4>
            <div v-for="item in sources.research" :key="item.id" class="source-item">
              <div class="source-meta">
                <span class="source-similarity" :class="distanceClass(item.distance)">{{ similarityLabel(item.distance) }}</span>
                <span v-if="item.metadata?.title" class="source-topic">{{ item.metadata.title }}</span>
              </div>
              <p class="source-text">{{ truncate(item.document, 250) }}</p>
            </div>
          </div>

          <!-- News -->
          <div v-if="sources.news?.length" class="source-group">
            <h4 class="source-group-title"><i class="pi pi-megaphone" /> News</h4>
            <div v-for="item in sources.news" :key="item.id" class="source-item">
              <div class="source-meta">
                <span class="source-similarity" :class="distanceClass(item.distance)">{{ similarityLabel(item.distance) }}</span>
                <span v-if="item.metadata?.topic" class="source-topic">{{ item.metadata.topic }}</span>
                <span v-if="item.metadata?.date" class="source-date">{{ item.metadata.date }}</span>
              </div>
              <p class="source-text">{{ truncate(item.document, 200) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Skeleton from 'primevue/skeleton'
import { API_ENDPOINTS } from '@/config/apiEndpoints'

interface SearchResult {
  id: string
  document: string
  metadata: Record<string, string> | null
  distance?: number
}

interface Sources {
  theses?: SearchResult[]
  analyses?: SearchResult[]
  lessons?: SearchResult[]
  research?: SearchResult[]
  news?: SearchResult[]
}

const query = ref('')
const loading = ref(false)
const hasSearched = ref(false)
const answer = ref('')
const sources = ref<Sources>({})
const showSources = ref(false)

const totalSources = computed(() => {
  const s = sources.value
  return (s.theses?.length || 0) + (s.analyses?.length || 0) +
         (s.lessons?.length || 0) + (s.research?.length || 0) + (s.news?.length || 0)
})

const renderedAnswer = computed(() => {
  // Simple markdown-like rendering
  return answer.value
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n- /g, '<br>- ')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
})

async function doSearch() {
  const q = query.value.trim()
  if (!q) return

  loading.value = true
  hasSearched.value = true
  answer.value = ''
  sources.value = {}
  showSources.value = false

  try {
    const response = await fetch(`/api${API_ENDPOINTS.KNOWLEDGE_ASK}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q }),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No reader')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)

        if (data === '[DONE]') break

        try {
          const parsed = JSON.parse(data)
          if (parsed.type === 'sources') {
            sources.value = parsed.data || {}
          } else if (parsed.error) {
            answer.value += `\n\nFehler: ${parsed.error}`
          } else {
            // It's a text chunk
            answer.value += parsed
          }
        } catch {
          // Plain text chunk
          answer.value += data
        }
      }
    }
  } catch (err) {
    console.error('Knowledge ask failed:', err)
    answer.value = 'Fehler beim Generieren der Antwort. Bitte versuche es erneut.'
  } finally {
    loading.value = false
  }
}

function useHint(hint: string) {
  query.value = hint
  doSearch()
}

function truncate(text: string, max: number): string {
  if (!text || text.length <= max) return text
  return text.slice(0, max) + '...'
}

function similarityLabel(distance?: number): string {
  if (distance === undefined) return ''
  const sim = Math.round((1 - distance) * 100)
  return `${sim}%`
}

function distanceClass(distance?: number): string {
  if (distance === undefined) return ''
  if (distance < 0.3) return 'dist-high'
  if (distance < 0.6) return 'dist-medium'
  return 'dist-low'
}
</script>

<style lang="scss" scoped>
.search-view {
  padding: 1.5rem;
  max-width: 900px;

  @media screen and (max-width: 640px) {
    padding: 1rem;
  }
}

.search-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--p-text-color);
  margin: 0 0 0.25rem 0;
}

.search-subtitle {
  font-size: 0.8125rem;
  color: var(--p-text-color-secondary);
  margin: 0 0 1.5rem 0;
}

// Search Bar
.search-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;

  @media screen and (max-width: 640px) {
    flex-direction: column;
  }
}

.search-input-wrapper {
  flex: 1;
  position: relative;

  i {
    position: absolute;
    left: 0.875rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--p-text-color-secondary);
    z-index: 1;
  }
}

.search-input {
  width: 100%;
  padding-left: 2.5rem;
  font-size: 0.9375rem;
}

// Hint chips
.search-hints {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 1rem;
}

.hint-chip {
  padding: 0.375rem 0.875rem;
  border-radius: 20px;
  font-size: 0.8125rem;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  color: var(--p-text-color-secondary);
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: var(--p-primary-color);
    color: var(--p-primary-color);
  }
}

// Answer
.answer-area {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.answer-card {
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--p-primary-200);
  background: var(--p-surface-card);

  :root.dark & {
    border-color: var(--p-primary-800);
  }
}

.answer-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-primary-color);

  i { font-size: 0.875rem; }
}

.answer-text {
  font-size: 0.875rem;
  line-height: 1.7;
  color: var(--p-text-color);

  :deep(p) {
    margin: 0 0 0.75rem 0;
    &:last-child { margin-bottom: 0; }
  }

  :deep(strong) {
    font-weight: 600;
    color: var(--p-text-color);
  }
}

.loading-answer {
  padding: 1.25rem 1.5rem;
  border-radius: 12px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

.mb-2 { margin-bottom: 0.5rem; }

// Sources
.sources-section {
  border-radius: 10px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  overflow: hidden;
}

.sources-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.75rem 1.25rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  transition: color 0.15s;

  &:hover { color: var(--p-text-color); }

  i { font-size: 0.75rem; }
}

.sources-list {
  padding: 0 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.source-group-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0 0 0.5rem 0;
  display: flex;
  align-items: center;
  gap: 0.375rem;

  i { font-size: 0.75rem; color: var(--p-primary-500); }
}

.source-item {
  padding: 0.625rem 0.875rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  margin-bottom: 0.375rem;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  flex-wrap: wrap;
}

.source-similarity {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.1rem 0.375rem;
  border-radius: 4px;

  &.dist-high {
    color: #059669;
    background: rgba(16, 185, 129, 0.1);
  }
  &.dist-medium {
    color: #d97706;
    background: rgba(245, 158, 11, 0.1);
  }
  &.dist-low {
    color: var(--p-text-color-secondary);
    background: var(--p-surface-hover);
  }
}

.source-date, .source-topic {
  font-size: 0.6875rem;
  color: var(--p-text-color-secondary);
}

.source-rating {
  font-size: 0.625rem;
  font-weight: 700;
  padding: 0.05rem 0.35rem;
  border-radius: 3px;

  &.rating-green, &.rating-green_fragile {
    background: rgba(16, 185, 129, 0.12);
    color: #059669;
  }
  &.rating-yellow, &.rating-yellow_bearish {
    background: rgba(245, 158, 11, 0.12);
    color: #d97706;
  }
  &.rating-red, &.rating-red_capitulation {
    background: rgba(239, 68, 68, 0.12);
    color: #dc2626;
  }
}

.source-text {
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  margin: 0.25rem 0 0 0;
}

// Empty state
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 3rem 0;
  text-align: center;

  i { font-size: 2.5rem; color: var(--p-text-color-secondary); opacity: 0.4; }
  p { color: var(--p-text-color-secondary); margin: 0; }
}
</style>
