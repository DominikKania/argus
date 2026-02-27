<template>
  <div class="layout-topbar" :class="{ 'sidebar-expanded': isExpanded }">
    <div class="topbar-left">
      <Button
        icon="pi pi-bars"
        text
        rounded
        aria-label="Toggle Menu"
        class="mobile-menu-toggle"
        @click="toggleSidebar"
      />
      <div class="topbar-header">
        <span class="topbar-title">Argus</span>
      </div>
    </div>

    <div class="topbar-right">
      <div class="dummy-mode-toggle">
        <i class="pi pi-question-circle toggle-icon" />
        <span class="toggle-label">Einfach</span>
        <ToggleSwitch v-model="dummyMode" />
      </div>
      <ThemeSelector />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import ToggleSwitch from 'primevue/toggleswitch'
import { useNavigation } from '@/composables/useNavigation'
import { useDummyModeStore } from '@/stores/dummyModeStore'
import ThemeSelector from '@/components/common/ThemeSelector.vue'

const { toggleSidebar, isExpanded } = useNavigation()
const dummyModeStore = useDummyModeStore()

const dummyMode = computed({
  get: () => dummyModeStore.isDummyMode,
  set: () => dummyModeStore.toggleDummyMode(),
})
</script>

<style lang="scss" scoped>
.layout-topbar {
  height: 4rem;
  padding: 0 0.75rem;
  background: var(--p-surface-card);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: fixed;
  top: 0;
  right: 0;
  left: 0;
  z-index: 1000;

  &::before {
    content: '';
    position: absolute;
    left: 4rem;
    right: 0;
    bottom: 0;
    height: 1px;
    background: var(--p-navigation-border);
    transition: left 0.3s ease;

    @media screen and (max-width: 768px) {
      left: 0;
    }
  }

  &.sidebar-expanded::before {
    left: 200px;
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .topbar-header {
    display: flex;
    align-items: center;
    height: 2.5rem;

    .topbar-title {
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--p-primary-color);
      padding-right: 0.75rem;
      white-space: nowrap;
    }
  }

  .topbar-right {
    display: flex;
    align-items: center;
    margin-left: auto;
    height: 100%;
    flex-shrink: 0;
    gap: 0.5rem;
  }
}

.mobile-menu-toggle {
  display: none;

  @media screen and (max-width: 768px) {
    display: block;
  }
}

@media screen and (max-width: 768px) {
  .layout-topbar {
    .topbar-header {
      border-left: none;
      margin: 0;
    }

    .topbar-right {
      gap: 0.25rem;
    }
  }
}

.dummy-mode-toggle {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding-right: 0.75rem;
  border-right: 1px solid var(--p-surface-border);

  .toggle-icon {
    font-size: 0.875rem;
    color: var(--p-text-color-secondary);
  }

  .toggle-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--p-text-color-secondary);
    white-space: nowrap;
  }

  @media screen and (max-width: 640px) {
    .toggle-label { display: none; }
  }
}
</style>
