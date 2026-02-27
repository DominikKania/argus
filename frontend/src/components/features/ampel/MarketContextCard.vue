<template>
  <div class="market-context-card">
    <h3 class="section-title">
      <i class="pi pi-info-circle" />
      Markt-Kontext
      <button class="chat-trigger" v-tooltip.top="'Frag den Tutor'" @click="askAbout">
        <i class="pi pi-comments" />
      </button>
    </h3>
    <div class="context-grid">
      <div v-for="item in contextItems" :key="item.key" class="context-item" @click="askAboutItem(item)">
        <div class="context-header">
          <i :class="item.icon" class="context-icon" />
          <span class="context-label">{{ item.label }}</span>
          <button class="item-chat-trigger" v-tooltip.top="'Mehr erfahren'">
            <i class="pi pi-comments" />
          </button>
        </div>
        <p class="context-text">{{ item.text }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MarketContext } from '@/types/ampel'
import { useChatStore } from '@/stores/chatStore'

const props = defineProps<{
  context: MarketContext
}>()

const chatStore = useChatStore()

function askAbout() {
  const summary = contextItems.value.map(i => `${i.label}: ${i.text}`).join('\n')
  chatStore.openWithContext(
    `Erkläre mir den aktuellen Markt-Kontext:\n${summary}`
  )
}

function askAboutItem(item: { label: string; text: string }) {
  chatStore.openWithContext(
    `Erkläre mir "${item.label}" genauer. Was bedeutet das für mein MSCI World ETF?\n\nAktuelle Einschätzung: ${item.text}`
  )
}

const NOTE_CONFIG: Record<string, { label: string; icon: string }> = {
  sector_rotation_note: { label: 'Sektor-Rotation', icon: 'pi pi-sync' },
  regional_note: { label: 'Regional (USA vs. Europa)', icon: 'pi pi-globe' },
  put_call_note: { label: 'Put/Call Ratio', icon: 'pi pi-chart-bar' },
  breadth_note: { label: 'Marktbreite', icon: 'pi pi-th-large' },
  seasonality_note: { label: 'Saisonalität', icon: 'pi pi-calendar' },
}

const contextItems = computed(() => {
  const items: Array<{ key: string; label: string; icon: string; text: string }> = []
  for (const [key, config] of Object.entries(NOTE_CONFIG)) {
    const text = props.context[key as keyof MarketContext]
    if (text) {
      items.push({ key, ...config, text })
    }
  }
  return items
})
</script>

<style lang="scss" scoped>
.market-context-card {
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

  i.pi-info-circle { color: var(--p-primary-500); font-size: 1.125rem; }
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
  margin-left: auto;

  .market-context-card:hover & { opacity: 0.6; }
  &:hover { opacity: 1 !important; color: var(--p-primary-500); background: var(--p-surface-ground); }
}

.context-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;

  @media screen and (max-width: 640px) {
    grid-template-columns: 1fr;
  }
}

.context-item {
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--p-surface-ground);
  border: 1px solid transparent;
  transition: all 0.15s;
  cursor: pointer;

  &:hover {
    border-color: var(--p-primary-300);
    background: var(--p-surface-hover);

    .item-chat-trigger { opacity: 1; }
  }
}

.context-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.375rem;
}

.item-chat-trigger {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.125rem 0.25rem;
  border-radius: 4px;
  color: var(--p-text-color-secondary);
  opacity: 0;
  transition: all 0.15s;
  font-size: 0.75rem;
  margin-left: auto;

  &:hover { color: var(--p-primary-500); }
}

.context-icon {
  font-size: 0.875rem;
  color: var(--p-primary-500);
}

.context-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.context-text {
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--p-text-color-secondary);
  margin: 0;
}
</style>
