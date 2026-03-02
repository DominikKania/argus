<template>
  <div class="research-context-card">
    <h3 class="section-title">
      <i class="pi pi-book" />
      Research-Kontext
      <span v-if="researches" class="research-count">{{ researches.length }}</span>
    </h3>

    <div v-if="error" class="research-error">
      <i class="pi pi-exclamation-triangle" />
      <span>{{ error }}</span>
    </div>

    <div v-else-if="loading && !researches" class="research-loading">
      <i class="pi pi-spin pi-spinner" />
      <span>Lade Research-Daten...</span>
    </div>

    <div v-else-if="researches && researches.length === 0" class="research-empty">
      <span>Keine abgeschlossenen Researches vorhanden.</span>
    </div>

    <template v-else-if="researches">
      <div
        v-for="r in researches"
        :key="r._id"
        class="research-item"
      >
        <button class="research-header" @click="toggle(r._id)">
          <i :class="expanded[r._id] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
          <span class="research-title">{{ r.title }}</span>
          <span v-if="r.last_run_date" class="research-date">{{ r.last_run_date }}</span>
        </button>

        <div v-if="r.relevance_summary" class="research-relevance">
          {{ r.relevance_summary }}
        </div>

        <div v-if="expanded[r._id] && r.synthesis" class="research-synthesis">
          <div v-html="renderMarkdown(r.synthesis)" />
        </div>
        <div v-else-if="expanded[r._id] && !r.synthesis" class="research-no-synthesis">
          Keine Synthese vorhanden — Research erneut ausführen für detaillierte Ergebnisse.
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ApiService } from '@/services/apiService'
import { API_ENDPOINTS } from '@/config/apiEndpoints'

interface ResearchTopic {
  _id: string
  title: string
  status: string
  relevance_summary?: string
  synthesis?: string
  last_run_date?: string
}

const researches = ref<ResearchTopic[] | null>(null)
const loading = ref(false)
const error = ref('')
const expanded = reactive<Record<string, boolean>>({})

function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/### (.+)/g, '<h4>$1</h4>')
    .replace(/## (.+)/g, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n- /g, '\n<li>')
    .replace(/<li>(.+?)(?=\n|$)/g, '<li>$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

function toggle(id: string) {
  expanded[id] = !expanded[id]
}

onMounted(async () => {
  loading.value = true
  try {
    const all = await ApiService.get<ResearchTopic[]>(API_ENDPOINTS.RESEARCH.LIST)
    researches.value = all.filter(r => r.status === 'completed' && r.relevance_summary)
  } catch {
    error.value = 'Research-Daten konnten nicht geladen werden'
  } finally {
    loading.value = false
  }
})
</script>

<style lang="scss" scoped>
.research-context-card {
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin: 0 0 1rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--p-surface-border);

  i.pi-book { color: var(--p-primary-500); font-size: 1.125rem; }
}

.research-count {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-primary-500);
  background: color-mix(in srgb, var(--p-primary-500) 12%, transparent);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
}

.research-item {
  & + & { margin-top: 0.75rem; }
}

.research-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  background: none;
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  padding: 0.625rem 0.75rem;
  cursor: pointer;
  color: var(--p-text-color);
  font-size: 0.875rem;
  font-weight: 600;
  transition: all 0.15s;

  &:hover {
    background: var(--p-surface-hover);
    border-color: var(--p-primary-300);
  }

  i:first-child {
    font-size: 0.75rem;
    color: var(--p-text-color-secondary);
  }
}

.research-title {
  flex: 1;
  text-align: left;
}

.research-date {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--p-text-color-secondary);
  background: var(--p-surface-ground);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
}

.research-relevance {
  margin-top: 0.5rem;
  padding: 0.625rem 0.75rem;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  border-left: 3px solid var(--p-primary-300);
  background: color-mix(in srgb, var(--p-primary-500) 4%, transparent);
  border-radius: 0 6px 6px 0;
}

.research-synthesis {
  margin-top: 0.5rem;
  padding: 1rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--p-text-color);
  max-height: 600px;
  overflow-y: auto;

  :deep(h3) {
    font-size: 0.9375rem;
    font-weight: 600;
    margin: 1rem 0 0.5rem 0;
    color: var(--p-text-color);
  }

  :deep(h4) {
    font-size: 0.875rem;
    font-weight: 600;
    margin: 0.75rem 0 0.375rem 0;
    color: var(--p-text-color);
  }

  :deep(strong) {
    font-weight: 600;
    color: var(--p-text-color);
  }

  :deep(li) {
    margin-left: 1rem;
    margin-bottom: 0.25rem;
    list-style-type: disc;
  }
}

.research-no-synthesis {
  margin-top: 0.5rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  color: var(--p-text-color-secondary);
  font-size: 0.8125rem;
  font-style: italic;
}

.research-loading,
.research-empty {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  color: var(--p-text-color-secondary);
  font-size: 0.8125rem;
}

.research-loading i {
  color: var(--p-primary-500);
}

.research-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  color: var(--p-text-color-secondary);
  font-size: 0.8125rem;

  i { color: #ef4444; }
}
</style>
