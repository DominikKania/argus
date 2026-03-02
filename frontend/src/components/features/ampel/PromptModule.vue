<template>
  <div class="prompt-module">
    <h3 class="module-title">
      <i class="pi pi-database" />
      Prompt-Kontext
    </h3>

    <!-- ── Research-Kontext ──────────────────────────────── -->
    <div class="module-section">
      <button class="section-header" @click="sections.research = !sections.research">
        <i :class="sections.research ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
        <i class="pi pi-book section-icon" />
        <span>Research-Kontext</span>
        <span v-if="researches" class="badge">{{ researches.length }}</span>
        <i v-if="loadingResearch" class="pi pi-spin pi-spinner spinner" />
      </button>

      <div v-if="sections.research" class="section-body">
        <div v-if="errorResearch" class="status-msg error">
          <i class="pi pi-exclamation-triangle" /> {{ errorResearch }}
        </div>
        <div v-else-if="researches && researches.length === 0" class="status-msg">
          Keine abgeschlossenen Researches vorhanden.
        </div>
        <template v-else-if="researches">
          <div v-for="r in researches" :key="r._id" class="context-item">
            <button class="item-header" @click="toggleExpand('r-' + r._id)">
              <i :class="expanded['r-' + r._id] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
              <span class="item-title">{{ r.title }}</span>
              <span v-if="r.last_run_date" class="item-date">{{ r.last_run_date }}</span>
            </button>
            <div v-if="r.relevance_summary" class="item-summary">
              {{ r.relevance_summary }}
            </div>
            <div v-if="expanded['r-' + r._id] && r.synthesis" class="item-detail">
              <div v-html="renderMarkdown(r.synthesis)" />
            </div>
            <div v-else-if="expanded['r-' + r._id] && !r.synthesis" class="item-empty">
              Keine Synthese vorhanden — Research erneut ausführen.
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- ── News-Kontext ──────────────────────────────────── -->
    <div class="module-section">
      <button class="section-header" @click="sections.news = !sections.news">
        <i :class="sections.news ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
        <i class="pi pi-megaphone section-icon" />
        <span>News-Kontext</span>
        <span v-if="newsTopics" class="badge">{{ newsTopics.length }}</span>
        <i v-if="loadingNews" class="pi pi-spin pi-spinner spinner" />
      </button>

      <div v-if="sections.news" class="section-body">
        <div v-if="errorNews" class="status-msg error">
          <i class="pi pi-exclamation-triangle" /> {{ errorNews }}
        </div>
        <div v-else-if="newsTopics && newsTopics.length === 0" class="status-msg">
          Keine News-Analysen vorhanden.
        </div>
        <template v-else-if="newsTopics">
          <div v-for="n in newsTopics" :key="n.topic + n.date" class="context-item">
            <button class="item-header" @click="toggleExpand('n-' + n.topic)">
              <i :class="expanded['n-' + n.topic] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
              <span class="item-title">{{ n.title || n.topic }}</span>
              <span :class="['trend-badge', `trend-${n.trend}`]">{{ trendLabel(n.trend) }}</span>
              <span v-if="n.date" class="item-date">{{ n.date }}</span>
            </button>
            <div class="item-summary">
              <div v-if="n.development" class="field">
                <span class="field-label">Neu:</span> {{ n.development }}
              </div>
              <div v-if="n.summary" class="field">
                <span class="field-label">Einordnung:</span> {{ n.summary }}
              </div>
              <div v-if="n.ampel_relevance" class="field">
                <span class="field-label">Ampel-Relevanz:</span> {{ n.ampel_relevance }}
              </div>
              <div v-if="n.triggers_detected?.length" class="triggers">
                <span v-for="t in n.triggers_detected" :key="t" class="trigger-tag">{{ t }}</span>
              </div>
            </div>
            <div v-if="expanded['n-' + n.topic] && n.deep_research" class="item-detail">
              <div v-html="renderMarkdown(n.deep_research)" />
            </div>
            <div v-else-if="expanded['n-' + n.topic] && !n.deep_research" class="item-empty">
              Keine Deep-Research für dieses Topic vorhanden.
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- ── Analyse-Prompt ────────────────────────────────── -->
    <div class="module-section">
      <button class="section-header" @click="openPromptSection">
        <i :class="sections.prompt ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
        <i class="pi pi-code section-icon" />
        <span>Analyse-Prompt</span>
        <span v-if="prompts" class="badge">{{ totalPromptLines }} Zeilen</span>
        <i v-if="loadingPrompts" class="pi pi-spin pi-spinner spinner" />
      </button>

      <div v-if="sections.prompt" class="section-body">
        <div v-if="errorPrompts" class="status-msg error">
          <i class="pi pi-exclamation-triangle" /> {{ errorPrompts }}
        </div>
        <template v-else-if="prompts">
          <!-- System Prompt -->
          <div class="context-item">
            <button class="item-header" @click="toggleExpand('system')">
              <i :class="expanded['system'] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
              <span class="item-title">System-Prompt</span>
              <span class="item-date">{{ systemLines }} Zeilen</span>
            </button>
            <pre v-if="expanded['system']" class="prompt-text">{{ prompts.system }}</pre>
          </div>
          <!-- User Prompt -->
          <div class="context-item">
            <button class="item-header" @click="toggleExpand('user')">
              <i :class="expanded['user'] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
              <span class="item-title">User-Prompt (Daten)</span>
              <span class="item-date">{{ userLines }} Zeilen</span>
            </button>
            <pre v-if="expanded['user']" class="prompt-text">{{ prompts.user }}</pre>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ApiService } from '@/services/apiService'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import type { AnalysisPrompts } from '@/types/ampel'

// ── Types ──
interface ResearchTopic {
  _id: string
  title: string
  status: string
  relevance_summary?: string
  synthesis?: string
  last_run_date?: string
}

interface NewsResult {
  topic: string
  title?: string
  date: string
  trend: string
  summary?: string
  development?: string
  recurring?: string
  ampel_relevance?: string
  triggers_detected?: string[]
  deep_research?: string
}

// ── State ──
const sections = reactive({ research: false, news: false, prompt: false })
const expanded = reactive<Record<string, boolean>>({})

const researches = ref<ResearchTopic[] | null>(null)
const loadingResearch = ref(false)
const errorResearch = ref('')

const newsTopics = ref<NewsResult[] | null>(null)
const loadingNews = ref(false)
const errorNews = ref('')

const prompts = ref<AnalysisPrompts | null>(null)
const loadingPrompts = ref(false)
const errorPrompts = ref('')

// ── Computed ──
const systemLines = computed(() => prompts.value?.system.split('\n').length ?? 0)
const userLines = computed(() => prompts.value?.user.split('\n').length ?? 0)
const totalPromptLines = computed(() => systemLines.value + userLines.value)

// ── Helpers ──
function trendLabel(trend: string): string {
  if (trend === 'improving') return '↑ besser'
  if (trend === 'deteriorating') return '↓ schlechter'
  return '→ stabil'
}

function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/### (.+)/g, '<h4>$1</h4>')
    .replace(/## (.+)/g, '<h3>$1</h3>')
    .replace(/# (.+)/g, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n- /g, '\n<li>')
    .replace(/<li>(.+?)(?=\n|$)/g, '<li>$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

function toggleExpand(key: string) {
  expanded[key] = !expanded[key]
}

// ── Lazy loading ──
async function fetchPrompts() {
  if (prompts.value || loadingPrompts.value) return
  loadingPrompts.value = true
  errorPrompts.value = ''
  try {
    prompts.value = await ApiService.get<AnalysisPrompts>(API_ENDPOINTS.AMPEL.PROMPTS)
  } catch {
    errorPrompts.value = 'Prompts konnten nicht geladen werden'
  } finally {
    loadingPrompts.value = false
  }
}

function openPromptSection() {
  sections.prompt = !sections.prompt
  if (sections.prompt) fetchPrompts()
}

// ── Load research & news on mount ──
onMounted(async () => {
  loadingResearch.value = true
  loadingNews.value = true

  try {
    const all = await ApiService.get<ResearchTopic[]>(API_ENDPOINTS.RESEARCH.LIST)
    researches.value = all.filter(r => r.status === 'completed' && r.relevance_summary)
  } catch {
    errorResearch.value = 'Research-Daten konnten nicht geladen werden'
  } finally {
    loadingResearch.value = false
  }

  try {
    newsTopics.value = await ApiService.get<NewsResult[]>(API_ENDPOINTS.NEWS.LATEST)
  } catch {
    errorNews.value = 'News-Daten konnten nicht geladen werden'
  } finally {
    loadingNews.value = false
  }
})
</script>

<style lang="scss" scoped>
.prompt-module {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

.module-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin: 0 0 1rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--p-surface-border);

  i.pi-database { color: var(--p-primary-500); font-size: 1.125rem; }
}

// ── Section (top-level collapsible) ──
.module-section {
  & + & { margin-top: 0.75rem; }
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  padding: 0.625rem 0.75rem;
  cursor: pointer;
  color: var(--p-text-color);
  font-size: 0.875rem;
  font-weight: 600;
  transition: all 0.15s;

  &:hover {
    border-color: var(--p-primary-300);
    background: var(--p-surface-hover);
  }

  > i:first-child {
    font-size: 0.75rem;
    color: var(--p-text-color-secondary);
  }
}

.section-icon {
  font-size: 0.875rem;
  color: var(--p-primary-500);
}

.badge {
  margin-left: auto;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-primary-500);
  background: color-mix(in srgb, var(--p-primary-500) 12%, transparent);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
}

.spinner {
  font-size: 0.875rem;
  color: var(--p-primary-500);
}

.section-body {
  margin-top: 0.5rem;
  padding-left: 0.5rem;
}

// ── Items inside a section ──
.context-item {
  & + & { margin-top: 0.625rem; }
}

.item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  background: none;
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  color: var(--p-text-color);
  font-size: 0.8125rem;
  font-weight: 600;
  transition: all 0.15s;

  &:hover {
    background: var(--p-surface-hover);
    border-color: var(--p-primary-300);
  }

  > i:first-child {
    font-size: 0.625rem;
    color: var(--p-text-color-secondary);
  }
}

.item-title {
  flex: 1;
  text-align: left;
}

.item-date {
  font-size: 0.7rem;
  font-weight: 400;
  color: var(--p-text-color-secondary);
  background: var(--p-surface-ground);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
}

.item-summary {
  margin-top: 0.375rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  border-left: 3px solid var(--p-primary-300);
  background: color-mix(in srgb, var(--p-primary-500) 4%, transparent);
  border-radius: 0 6px 6px 0;
}

.field + .field { margin-top: 0.25rem; }

.field-label {
  font-weight: 600;
  color: var(--p-text-color);
}

.triggers {
  margin-top: 0.375rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.trigger-tag {
  font-size: 0.65rem;
  font-weight: 500;
  padding: 0.125rem 0.4rem;
  border-radius: 10px;
  background: color-mix(in srgb, #f59e0b 15%, transparent);
  color: #b45309;
}

.trend-badge {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.125rem 0.4rem;
  border-radius: 10px;

  &.trend-improving {
    color: #16a34a;
    background: color-mix(in srgb, #16a34a 12%, transparent);
  }
  &.trend-deteriorating {
    color: #ef4444;
    background: color-mix(in srgb, #ef4444 12%, transparent);
  }
  &.trend-stable {
    color: var(--p-text-color-secondary);
    background: var(--p-surface-ground);
  }
}

// ── Detail panels (synthesis / deep-research / prompts) ──
.item-detail {
  margin-top: 0.375rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--p-text-color);
  max-height: 500px;
  overflow-y: auto;

  :deep(h3) {
    font-size: 0.875rem;
    font-weight: 600;
    margin: 0.75rem 0 0.375rem 0;
    color: var(--p-text-color);
  }

  :deep(h4) {
    font-size: 0.8125rem;
    font-weight: 600;
    margin: 0.5rem 0 0.25rem 0;
    color: var(--p-text-color);
  }

  :deep(strong) {
    font-weight: 600;
    color: var(--p-text-color);
  }

  :deep(li) {
    margin-left: 1rem;
    margin-bottom: 0.125rem;
    list-style-type: disc;
  }
}

.item-empty {
  margin-top: 0.375rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  color: var(--p-text-color-secondary);
  font-size: 0.8rem;
  font-style: italic;
}

.prompt-text {
  margin: 0.375rem 0 0 0;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.7rem;
  line-height: 1.6;
  color: var(--p-text-color-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 500px;
  overflow-y: auto;
}

// ── Status messages ──
.status-msg {
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: var(--p-text-color-secondary);

  &.error {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    i { color: #ef4444; }
  }
}
</style>
