<template>
  <div class="prompt-module">
    <div class="module-header">
      <h3 class="module-title">
        <i class="pi pi-database" />
        Prompt-Kontext
      </h3>
      <button
        class="run-button"
        :disabled="running"
        @click="runAnalysis"
      >
        <i :class="running ? 'pi pi-spin pi-spinner' : 'pi pi-play'" />
        {{ running ? runStatus : 'Analyse starten' }}
      </button>
    </div>

    <!-- ── Signal Progress (visible during/after run) ────── -->
    <div v-if="Object.keys(signalResults).length || running" class="module-section">
      <button class="section-header section-header--active" @click="sections.llmOutput = !sections.llmOutput">
        <i :class="sections.llmOutput ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
        <i class="pi pi-bolt section-icon" />
        <span>Analyse</span>
        <span v-if="runResult" :class="['result-badge', `result-${runResult.rating?.toLowerCase()}`]">
          {{ runResult.rating }} ({{ runResult.score }}/4) — {{ runResult.action }}
        </span>
        <button v-if="runResult && !running" class="chat-trigger" v-tooltip.top="'Frag den Tutor'" @click.stop="askAboutAnalysis">
          <i class="pi pi-comments" />
        </button>
        <i v-if="running && !runResult" class="pi pi-spin pi-spinner spinner" />
      </button>

      <div v-if="sections.llmOutput" class="section-body">
        <!-- Signal chips -->
        <div v-if="Object.keys(signalResults).length || running" class="signal-progress">
          <div
            v-for="name in ['trend', 'volatility', 'macro', 'sentiment']"
            :key="name"
            :class="['signal-chip', signalResults[name] ? `chip-${signalResults[name].context}` : 'chip-pending']"
          >
            <span class="chip-label">{{ signalLabels[name] }}</span>
            <span v-if="signalResults[name]" class="chip-context">{{ signalResults[name].context }}</span>
            <i v-if="signalResults[name]" class="pi pi-check chip-icon" />
            <i v-else-if="running" class="pi pi-spin pi-spinner chip-icon" />
          </div>
        </div>

        <div v-if="runError" class="status-msg error">
          <i class="pi pi-exclamation-triangle" /> {{ runError }}
        </div>
        <pre v-if="llmOutput" ref="llmOutputEl" class="llm-output">{{ llmOutput }}</pre>
      </div>
    </div>

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
            <div class="target-chips">
              <span class="target-label">Ziel:</span>
              <button
                v-for="t in ampelTargetOptions"
                :key="t.value"
                :class="['target-chip', { active: (r.ampel_targets || []).includes(t.value) }]"
                @click.stop="toggleTarget(r, t.value)"
              >
                {{ t.label }}
              </button>
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

    <!-- ── Earnings-Kontext ──────────────────────────────── -->
    <div v-if="earnings" class="module-section">
      <button class="section-header" @click="sections.earnings = !sections.earnings">
        <i :class="sections.earnings ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
        <i class="pi pi-briefcase section-icon" />
        <span>Earnings-Kontext</span>
        <span class="badge">{{ earnings.earnings_health }}</span>
      </button>

      <div v-if="sections.earnings" class="section-body">
        <div class="item-summary">
          <div class="field">
            <span class="field-label">Beat Rate:</span> {{ earnings.beat_rate }} ({{ earnings.beat_rate_pct }}%)
          </div>
          <div class="field">
            <span class="field-label">Ø Surprise:</span> {{ earnings.avg_surprise_pct > 0 ? '+' : '' }}{{ earnings.avg_surprise_pct?.toFixed(1) }}%
          </div>
          <div v-if="earnings.fwd_eps_growth_0y != null" class="field">
            <span class="field-label">FWD EPS Growth:</span> {{ (earnings.fwd_eps_growth_0y * 100) > 0 ? '+' : '' }}{{ (earnings.fwd_eps_growth_0y * 100).toFixed(1) }}%
          </div>
          <div class="field">
            <span class="field-label">Revisions:</span> {{ earnings.revision_direction }}
            (7d: {{ earnings.net_revisions_7d > 0 ? '+' : '' }}{{ earnings.net_revisions_7d }},
             30d: {{ earnings.net_revisions_30d > 0 ? '+' : '' }}{{ earnings.net_revisions_30d }})
          </div>
          <div class="field">
            <span class="field-label">Health:</span>
            <span :class="['health-badge', `health-${earnings.earnings_health}`]">{{ earnings.earnings_health }}</span>
          </div>
        </div>

        <!-- Sektor-Aufschlüsselung -->
        <div v-if="earnings.by_sector && Object.keys(earnings.by_sector).length" class="context-item" style="margin-top: 0.5rem">
          <button class="item-header" @click="toggleExpand('earnings-sectors')">
            <i :class="expanded['earnings-sectors'] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
            <span class="item-title">Sektor-Aufschlüsselung</span>
            <span class="item-date">{{ Object.keys(earnings.by_sector).length }} Sektoren</span>
          </button>
          <div v-if="expanded['earnings-sectors']" class="item-detail">
            <div v-for="(data, sector) in earnings.by_sector" :key="sector" style="margin-bottom: 0.375rem">
              <strong>{{ sector }}:</strong>
              Beat {{ data.beat_rate }} ({{ data.beat_rate_pct }}%) |
              Surprise {{ data.avg_surprise_pct > 0 ? '+' : '' }}{{ data.avg_surprise_pct?.toFixed(1) }}% |
              Revisions: {{ data.revision_direction }}
            </div>
          </div>
        </div>

        <!-- Anstehende Earnings -->
        <div v-if="earnings.upcoming?.length" class="context-item" style="margin-top: 0.5rem">
          <button class="item-header" @click="toggleExpand('earnings-upcoming')">
            <i :class="expanded['earnings-upcoming'] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
            <span class="item-title">Anstehende Earnings</span>
            <span class="item-date">{{ earnings.upcoming.length }}</span>
          </button>
          <div v-if="expanded['earnings-upcoming']" class="item-detail">
            <div v-for="u in earnings.upcoming" :key="u.ticker">
              <strong>{{ u.ticker }}</strong> ({{ u.sector }}) — {{ u.date }}
            </div>
          </div>
        </div>

        <!-- Kürzlich gemeldet -->
        <div v-if="earnings.recently_reported?.length" class="context-item" style="margin-top: 0.5rem">
          <button class="item-header" @click="toggleExpand('earnings-recent')">
            <i :class="expanded['earnings-recent'] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
            <span class="item-title">Kürzlich gemeldet</span>
            <span class="item-date">{{ earnings.recently_reported.length }}</span>
          </button>
          <div v-if="expanded['earnings-recent']" class="item-detail">
            <div v-for="r in earnings.recently_reported" :key="r.ticker">
              <strong>{{ r.ticker }}</strong> ({{ r.sector }}) — Surprise {{ r.surprise_pct > 0 ? '+' : '' }}{{ r.surprise_pct?.toFixed(1) }}%
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Analyse-Prompts (per Stage) ─────────────────── -->
    <div class="module-section">
      <button class="section-header" @click="openPromptSection">
        <i :class="sections.prompt ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
        <i class="pi pi-code section-icon" />
        <span>Analyse-Prompts</span>
        <span v-if="prompts?.stages" class="badge">{{ Object.keys(prompts.stages).length }} Stufen</span>
        <i v-if="loadingPrompts" class="pi pi-spin pi-spinner spinner" />
      </button>

      <div v-if="sections.prompt" class="section-body">
        <div v-if="errorPrompts" class="status-msg error">
          <i class="pi pi-exclamation-triangle" /> {{ errorPrompts }}
        </div>
        <template v-else-if="prompts?.stages">
          <div v-for="(stage, name) in prompts.stages" :key="name" class="context-item">
            <button class="item-header" @click="toggleExpand('stage-' + name)">
              <i :class="expanded['stage-' + name] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
              <span class="item-title">{{ stageLabels[name] || name }}</span>
              <span class="item-date">{{ countLines(stage.system) + countLines(stage.user) }} Zeilen</span>
            </button>
            <div v-if="expanded['stage-' + name]" class="stage-prompts">
              <div class="stage-prompt-label">System</div>
              <pre class="prompt-text">{{ stage.system }}</pre>
              <div class="stage-prompt-label">Daten</div>
              <pre class="prompt-text">{{ stage.user }}</pre>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ApiService } from '@/services/apiService'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { useChatStore } from '@/stores/chatStore'
import type { AnalysisPrompts } from '@/types/ampel'

const chatStore = useChatStore()

// ── Types ──
interface ResearchTopic {
  _id: string
  title: string
  status: string
  relevance_summary?: string
  synthesis?: string
  last_run_date?: string
  ampel_targets?: string[]
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

interface SignalResult {
  context: string
  note: string
}

interface RunResult {
  rating: string
  score: number
  action: string
}

const signalLabels: Record<string, string> = {
  trend: 'Trend',
  volatility: 'Volatilität',
  macro: 'Makro',
  sentiment: 'Sentiment',
}

// ── State ──
const sections = reactive({ research: false, news: false, prompt: false, llmOutput: false, earnings: false })
const signalResults = reactive<Record<string, SignalResult>>({})
const expanded = reactive<Record<string, boolean>>({})

const researches = ref<ResearchTopic[] | null>(null)
const loadingResearch = ref(false)
const errorResearch = ref('')

const newsTopics = ref<NewsResult[] | null>(null)
const loadingNews = ref(false)
const errorNews = ref('')

const earnings = ref<Record<string, unknown> | null>(null)

const prompts = ref<AnalysisPrompts | null>(null)
const loadingPrompts = ref(false)
const errorPrompts = ref('')

// ── Run state ──
const running = ref(false)
const runStatus = ref('')
const llmOutput = ref('')
const runResult = ref<RunResult | null>(null)
const runError = ref('')
const llmOutputEl = ref<HTMLPreElement | null>(null)

// ── Computed ──
const stageLabels: Record<string, string> = {
  trend: 'Stage 1: Trend-Analyst',
  volatility: 'Stage 1: Volatilitäts-Analyst',
  macro: 'Stage 1: Makro-Analyst',
  sentiment: 'Stage 1: Sentiment-Analyst',
  synthesis: 'Stage 2: Synthese',
}

function countLines(text: string): number {
  return text ? text.split('\n').length : 0
}

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

const ampelTargetOptions = [
  { value: 'trend', label: 'Trend' },
  { value: 'volatility', label: 'Volatilität' },
  { value: 'macro', label: 'Makro' },
  { value: 'sentiment', label: 'Sentiment' },
]

async function toggleTarget(research: ResearchTopic, target: string) {
  const current = research.ampel_targets || []
  const next = current.includes(target)
    ? current.filter(t => t !== target)
    : [...current, target]
  research.ampel_targets = next
  try {
    await ApiService.put(API_ENDPOINTS.RESEARCH.UPDATE(research._id), { ampel_targets: next })
  } catch {
    // Revert on failure
    research.ampel_targets = current
  }
}

// ── Chat about analysis ──
function askAboutAnalysis() {
  if (!runResult.value) return
  const signalSummary = Object.entries(signalResults)
    .map(([name, s]) => `${signalLabels[name]}: ${s.context}`)
    .join(', ')
  chatStore.openWithContext(
    `Erkläre mir die aktuelle Ampel-Analyse: Rating ${runResult.value.rating} (Score ${runResult.value.score}/4), ` +
    `Empfehlung: ${runResult.value.action}. Signale: ${signalSummary}. ` +
    `Was bedeutet das für mein MSCI World ETF?`
  )
}

// ── Run Analysis (SSE) ──
async function runAnalysis() {
  if (running.value) return

  running.value = true
  runStatus.value = 'Starte...'
  llmOutput.value = ''
  runResult.value = null
  runError.value = ''
  // Clear previous signal results
  for (const key of Object.keys(signalResults)) {
    delete signalResults[key]
  }
  sections.llmOutput = true

  try {
    const response = await fetch('/api' + API_ENDPOINTS.AMPEL.RUN, {
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

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue

        try {
          const event = JSON.parse(raw)
          switch (event.type) {
            case 'status':
              runStatus.value = event.data
              break
            case 'prompt':
              // Update the prompt section with fresh data
              prompts.value = { system: event.data.system, user: event.data.user }
              break
            case 'signal':
              signalResults[event.data.name] = {
                context: event.data.context,
                note: event.data.note || '',
              }
              break
            case 'chunk':
              llmOutput.value += event.data
              await nextTick()
              if (llmOutputEl.value) {
                llmOutputEl.value.scrollTop = llmOutputEl.value.scrollHeight
              }
              break
            case 'done':
              runResult.value = event.data
              break
            case 'error':
              runError.value = event.data
              break
          }
        } catch {
          // Skip unparseable lines
        }
      }
    }
  } catch (e) {
    runError.value = `Verbindung fehlgeschlagen: ${e}`
  } finally {
    running.value = false
    // Reload news after analysis (backend fetches fresh news during run)
    try {
      newsTopics.value = await ApiService.get<NewsResult[]>(API_ENDPOINTS.NEWS.LATEST)
    } catch { /* ignore */ }
  }
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

// ── Load data on mount ──
onMounted(async () => {
  loadingResearch.value = true
  loadingNews.value = true

  // Load latest analysis to get persisted llm_output
  try {
    const latest = await ApiService.get<Record<string, unknown>>(API_ENDPOINTS.AMPEL.LATEST)
    if (latest?.llm_output) {
      llmOutput.value = latest.llm_output as string
      runResult.value = {
        rating: (latest.rating as Record<string, unknown>)?.overall as string || '',
        score: (latest.rating as Record<string, unknown>)?.mechanical_score as number || 0,
        action: (latest.recommendation as Record<string, unknown>)?.action as string || '',
      }
      // Restore signal results from saved analysis
      const signals = latest.signals as Record<string, Record<string, unknown>> | undefined
      if (signals) {
        for (const name of ['trend', 'volatility', 'macro', 'sentiment']) {
          const s = signals[name]
          if (s) {
            signalResults[name] = {
              context: (s.context as string) || '',
              note: (s.note as string) || '',
            }
          }
        }
      }
    }
    const market = latest?.market as Record<string, unknown> | undefined
    if (market?.earnings) {
      earnings.value = market.earnings as Record<string, unknown>
    }
  } catch {
    // No analysis yet — that's fine
  }

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

.module-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--p-surface-border);
  margin-bottom: 1rem;
}

.module-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;

  i.pi-database { color: var(--p-primary-500); font-size: 1.125rem; }
}

.chat-trigger {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 6px;
  color: var(--p-text-color-secondary);
  opacity: 0.6;
  transition: all 0.15s;
  font-size: 0.875rem;

  &:hover { opacity: 1; color: var(--p-primary-500); background: var(--p-surface-ground); }
}

.run-button {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 8px;
  background: var(--p-primary-500);
  color: white;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;

  &:hover:not(:disabled) {
    background: var(--p-primary-600);
  }

  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
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

  &--active {
    border-color: var(--p-primary-400);
    background: color-mix(in srgb, var(--p-primary-500) 8%, var(--p-surface-ground));
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

.result-badge {
  margin-left: auto;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 10px;

  &.result-green, &.result-green_fragile {
    color: #16a34a;
    background: color-mix(in srgb, #16a34a 12%, transparent);
  }
  &.result-yellow, &.result-yellow_bearish {
    color: #ca8a04;
    background: color-mix(in srgb, #ca8a04 12%, transparent);
  }
  &.result-red, &.result-red_capitulation {
    color: #ef4444;
    background: color-mix(in srgb, #ef4444 12%, transparent);
  }
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

.target-chips {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.375rem;
  padding: 0.375rem 0.75rem;
}

.target-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  margin-right: 0.125rem;
}

.target-chip {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  border-radius: 10px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-ground);
  color: var(--p-text-color-secondary);
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: var(--p-primary-300);
    color: var(--p-primary-500);
  }

  &.active {
    background: color-mix(in srgb, var(--p-primary-500) 15%, transparent);
    border-color: var(--p-primary-400);
    color: var(--p-primary-600);
  }
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

.stage-prompts {
  margin-top: 0.375rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stage-prompt-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0.25rem 0.75rem 0;
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

.llm-output {
  margin: 0;
  padding: 0.75rem;
  border-radius: 8px;
  background: #1e1e2e;
  border: 1px solid var(--p-surface-border);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.7rem;
  line-height: 1.6;
  color: #cdd6f4;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 600px;
  overflow-y: auto;
}

.health-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.125rem 0.4rem;
  border-radius: 10px;

  &.health-strong {
    color: #16a34a;
    background: color-mix(in srgb, #16a34a 12%, transparent);
  }
  &.health-moderate {
    color: #ca8a04;
    background: color-mix(in srgb, #ca8a04 12%, transparent);
  }
  &.health-weak, &.health-deteriorating {
    color: #ef4444;
    background: color-mix(in srgb, #ef4444 12%, transparent);
  }
}

// ── Signal progress chips ──
.signal-progress {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.signal-chip {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 8px;
  font-size: 0.75rem;
  font-weight: 600;
  border: 1px solid var(--p-surface-border);
  transition: all 0.3s;

  &.chip-pending {
    background: var(--p-surface-ground);
    color: var(--p-text-color-secondary);
  }

  &.chip-green {
    background: color-mix(in srgb, #16a34a 12%, transparent);
    border-color: color-mix(in srgb, #16a34a 30%, transparent);
    color: #16a34a;
  }

  &.chip-yellow {
    background: color-mix(in srgb, #ca8a04 12%, transparent);
    border-color: color-mix(in srgb, #ca8a04 30%, transparent);
    color: #ca8a04;
  }

  &.chip-red {
    background: color-mix(in srgb, #ef4444 12%, transparent);
    border-color: color-mix(in srgb, #ef4444 30%, transparent);
    color: #ef4444;
  }
}

.chip-label {
  white-space: nowrap;
}

.chip-context {
  text-transform: uppercase;
  font-size: 0.65rem;
  letter-spacing: 0.5px;
}

.chip-icon {
  font-size: 0.7rem;
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
