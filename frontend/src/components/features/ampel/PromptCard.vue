<template>
  <div class="prompt-card">
    <h3 class="section-title">
      <i class="pi pi-code" />
      Analyse-Prompt
    </h3>

    <div v-if="error" class="prompt-error">
      <i class="pi pi-exclamation-triangle" />
      <span>{{ error }}</span>
    </div>

    <template v-else>
      <!-- System Prompt -->
      <div class="prompt-section">
        <button class="prompt-header" @click="toggleSystem">
          <i :class="showSystem ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
          <span>System-Prompt</span>
          <span v-if="prompts" class="prompt-meta">{{ systemLines }} Zeilen</span>
          <i v-if="loading" class="pi pi-spin pi-spinner prompt-spinner" />
        </button>
        <pre v-if="showSystem && prompts" class="prompt-text">{{ prompts.system }}</pre>
      </div>

      <!-- User Prompt (Daten) -->
      <div class="prompt-section">
        <button class="prompt-header" @click="toggleUser">
          <i :class="showUser ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
          <span>User-Prompt (Daten)</span>
          <span v-if="prompts" class="prompt-meta">{{ userLines }} Zeilen</span>
          <i v-if="loading" class="pi pi-spin pi-spinner prompt-spinner" />
        </button>
        <pre v-if="showUser && prompts" class="prompt-text">{{ prompts.user }}</pre>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ApiService } from '@/services/apiService'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import type { AnalysisPrompts } from '@/types/ampel'

const prompts = ref<AnalysisPrompts | null>(null)
const loading = ref(false)
const error = ref('')
const showSystem = ref(false)
const showUser = ref(false)

const systemLines = computed(() => prompts.value?.system.split('\n').length ?? 0)
const userLines = computed(() => prompts.value?.user.split('\n').length ?? 0)

async function fetchPrompts() {
  if (prompts.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    prompts.value = await ApiService.get<AnalysisPrompts>(API_ENDPOINTS.AMPEL.PROMPTS)
  } catch (e: any) {
    error.value = 'Prompts konnten nicht geladen werden'
  } finally {
    loading.value = false
  }
}

function toggleSystem() {
  showSystem.value = !showSystem.value
  if (showSystem.value) fetchPrompts()
}

function toggleUser() {
  showUser.value = !showUser.value
  if (showUser.value) fetchPrompts()
}
</script>

<style lang="scss" scoped>
.prompt-card {
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

  i.pi-code { color: var(--p-primary-500); font-size: 1.125rem; }
}

.prompt-section {
  & + & { margin-top: 0.75rem; }
}

.prompt-header {
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

.prompt-meta {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--p-text-color-secondary);
  background: var(--p-surface-ground);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
}

.prompt-spinner {
  font-size: 0.875rem;
  color: var(--p-primary-500);
}

.prompt-text {
  margin: 0.5rem 0 0 0;
  padding: 1rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--p-text-color-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 500px;
  overflow-y: auto;
}

.prompt-error {
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
