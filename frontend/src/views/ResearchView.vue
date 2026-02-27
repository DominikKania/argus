<template>
  <div class="research-view">
    <!-- Loading -->
    <div v-if="researchStore.loading && !researchStore.topics.length" class="loading-state">
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
          Deep Research
          <span v-if="researchStore.topics.length" class="count-badge">{{ researchStore.topics.length }}</span>
        </h1>
        <Button label="Neues Thema" icon="pi pi-plus" size="small" @click="showNewDialog = true" />
      </div>

      <div class="master-detail">
        <!-- Topic List (Master) -->
        <div class="topic-list">
          <div v-if="!researchStore.topics.length" class="empty-list">
            <i class="pi pi-search" />
            <p>Noch keine Themen.</p>
          </div>
          <button
            v-for="t in researchStore.topics"
            :key="t._id"
            class="topic-item"
            :class="{ active: researchStore.selectedTopic?._id === t._id }"
            @click="selectTopic(t)"
          >
            <span class="topic-status-dot" :class="`status-${t.status}`" />
            <div class="topic-item-text">
              <span class="topic-item-title">{{ t.title }}</span>
              <span class="topic-item-meta">{{ t.updated_date }}</span>
            </div>
          </button>
        </div>

        <!-- Detail Panel -->
        <div class="detail-panel" v-if="researchStore.selectedTopic">
          <div class="detail-header">
            <div class="detail-title-row">
              <h2 class="detail-title">{{ researchStore.selectedTopic.title }}</h2>
              <span class="status-badge" :class="`badge-${researchStore.selectedTopic.status}`">
                <i v-if="researchStore.selectedTopic.status === 'running'" class="pi pi-spin pi-spinner" />
                {{ statusLabels[researchStore.selectedTopic.status] }}
              </span>
            </div>
            <div class="detail-actions">
              <Button
                label="Ausführen"
                icon="pi pi-play"
                size="small"
                :loading="researchStore.running"
                :disabled="!researchStore.selectedTopic.prompt?.trim() || researchStore.running"
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
              <label class="section-label">Research-Prompt</label>
              <Button
                label="Prompt generieren"
                icon="pi pi-sparkles"
                size="small"
                severity="secondary"
                text
                :loading="generatingPrompt"
                @click="regeneratePrompt"
              />
            </div>
            <textarea
              v-model="editablePrompt"
              class="prompt-editor"
              placeholder="Research-Prompt hier eingeben oder generieren lassen..."
            />
          </div>

          <!-- Error -->
          <div v-if="researchStore.selectedTopic.error_message" class="research-error">
            <i class="pi pi-exclamation-circle" />
            {{ researchStore.selectedTopic.error_message }}
          </div>

          <!-- Results -->
          <div v-if="researchStore.selectedTopic.results" class="results-section">
            <label class="section-label">Ergebnis</label>
            <div class="results-meta">
              <span v-if="researchStore.selectedTopic.last_run_date">
                <i class="pi pi-clock" /> {{ researchStore.selectedTopic.last_run_date }}
              </span>
            </div>
            <div class="results-content" v-html="renderedResults" />
            <div v-if="researchStore.selectedTopic.relevance_summary" class="relevance-box">
              <span class="relevance-label">Relevanz für Ampel:</span>
              {{ researchStore.selectedTopic.relevance_summary }}
            </div>
          </div>

          <!-- Empty results -->
          <div v-else-if="researchStore.selectedTopic.status === 'ready'" class="no-results">
            <i class="pi pi-play-circle" />
            <p>Klicke "Ausführen" um die Research zu starten.</p>
          </div>
        </div>

        <!-- No selection -->
        <div v-else class="detail-panel detail-empty">
          <i class="pi pi-search" />
          <p>Wähle ein Thema aus oder erstelle ein neues.</p>
        </div>
      </div>
    </template>

    <!-- New Topic Dialog -->
    <Dialog
      v-model:visible="showNewDialog"
      header="Neues Research-Thema"
      :modal="true"
      :style="{ width: '500px' }"
      :closable="!creating"
    >
      <div class="new-topic-form">
        <label class="form-label">Thema</label>
        <InputText
          v-model="newTitle"
          placeholder="z.B. Trump Zollpolitik"
          class="w-full"
          :disabled="creating"
          @keydown.enter="createNewTopic"
        />
        <small class="form-hint">Ein KI-Prompt wird automatisch generiert.</small>
      </div>
      <template #footer>
        <Button label="Abbrechen" severity="secondary" text @click="showNewDialog = false" :disabled="creating" />
        <Button label="Erstellen" icon="pi pi-plus" :loading="creating" :disabled="!newTitle.trim()" @click="createNewTopic" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useResearchStore } from '@/stores/researchStore'
import { useChatStore } from '@/stores/chatStore'
import type { Research } from '@/types/research'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import { marked } from 'marked'

const researchStore = useResearchStore()
const chatStore = useChatStore()

const showNewDialog = ref(false)
const newTitle = ref('')
const creating = ref(false)
const generatingPrompt = ref(false)
const editablePrompt = ref('')

const statusLabels: Record<string, string> = {
  draft: 'Entwurf',
  ready: 'Bereit',
  running: 'Läuft...',
  completed: 'Abgeschlossen',
  error: 'Fehler',
}

// Track prompt changes
const promptDirty = computed(() => {
  if (!researchStore.selectedTopic) return false
  return editablePrompt.value !== researchStore.selectedTopic.prompt
})

// Sync editable prompt when selection changes
watch(
  () => researchStore.selectedTopic,
  (topic) => {
    editablePrompt.value = topic?.prompt || ''
  },
  { immediate: true },
)

// Render markdown results
const renderedResults = computed(() => {
  if (!researchStore.selectedTopic?.results) return ''
  return marked(researchStore.selectedTopic.results)
})

function selectTopic(topic: Research) {
  researchStore.selectedTopic = topic
  // Fetch full details (includes results)
  researchStore.fetchTopic(topic._id)
}

async function createNewTopic() {
  if (!newTitle.value.trim()) return
  creating.value = true
  const created = await researchStore.createTopic(newTitle.value.trim())
  creating.value = false
  if (created) {
    showNewDialog.value = false
    newTitle.value = ''
  }
}

async function regeneratePrompt() {
  if (!researchStore.selectedTopic) return
  generatingPrompt.value = true
  const prompt = await researchStore.generatePrompt(researchStore.selectedTopic.title)
  generatingPrompt.value = false
  if (prompt) {
    editablePrompt.value = prompt
  }
}

async function savePrompt() {
  if (!researchStore.selectedTopic || !promptDirty.value) return
  await researchStore.updateTopic(researchStore.selectedTopic._id, {
    prompt: editablePrompt.value,
  })
}

async function runSelected() {
  if (!researchStore.selectedTopic) return
  // Save prompt first if dirty
  if (promptDirty.value) await savePrompt()
  await researchStore.runResearch(researchStore.selectedTopic._id)
}

async function deleteSelected() {
  if (!researchStore.selectedTopic) return
  await researchStore.deleteTopic(researchStore.selectedTopic._id)
}

function askAbout() {
  if (!researchStore.selectedTopic) return
  const t = researchStore.selectedTopic
  let msg = `Erkläre mir das Research-Thema: ${t.title}`
  if (t.relevance_summary) {
    msg += `\n\nRelevanz: ${t.relevance_summary}`
  }
  chatStore.openWithContext(msg)
}

onMounted(() => {
  researchStore.fetchTopics()
})
</script>

<style lang="scss" scoped>
.research-view {
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

.topic-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &.status-draft { background: #9ca3af; }
  &.status-ready { background: #3b82f6; }
  &.status-running { background: #f59e0b; animation: pulse-dot 1.5s infinite; }
  &.status-completed { background: #10b981; }
  &.status-error { background: #ef4444; }
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
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

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.625rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;

  &.badge-draft { background: #f3f4f6; color: #6b7280; :root.dark & { background: #374151; color: #9ca3af; } }
  &.badge-ready { background: #eff6ff; color: #3b82f6; :root.dark & { background: #1e3a5f; color: #60a5fa; } }
  &.badge-running { background: #fffbeb; color: #f59e0b; :root.dark & { background: #451a03; color: #fcd34d; } }
  &.badge-completed { background: #ecfdf5; color: #059669; :root.dark & { background: #064e3b; color: #6ee7b7; } }
  &.badge-error { background: #fef2f2; color: #ef4444; :root.dark & { background: #450a0a; color: #fca5a5; } }
}

.detail-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

// Prompt Editor — flex sizing is in the second .prompt-section block below

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;

  .section-label { margin-bottom: 0; }
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
  min-height: 200px;
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

// Error
.research-error {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.8125rem;
  margin-bottom: 1rem;

  i { margin-top: 0.125rem; }
}

// Results
.results-section {
  border-top: 1px solid var(--p-surface-border);
  padding-top: 1rem;
}

.results-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
  margin-bottom: 0.75rem;

  i { font-size: 0.625rem; }
}

.results-content {
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--p-text-color);

  :deep(h3) {
    font-size: 0.9375rem;
    font-weight: 600;
    margin: 1.25rem 0 0.5rem;
    color: var(--p-text-color);
  }

  :deep(p) {
    margin: 0.5rem 0;
  }

  :deep(ul), :deep(ol) {
    padding-left: 1.25rem;
    margin: 0.5rem 0;
  }

  :deep(li) {
    margin: 0.25rem 0;
  }

  :deep(strong) {
    font-weight: 600;
  }
}

.relevance-box {
  margin-top: 1rem;
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
}

.form-hint {
  font-size: 0.75rem;
  color: var(--p-text-color-secondary);
}

.w-full { width: 100%; }
</style>
