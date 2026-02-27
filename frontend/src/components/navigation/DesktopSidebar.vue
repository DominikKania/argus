<template>
  <nav
    class="layout-sidebar-desktop"
    :class="{ 'sidebar-expanded': isExpanded }"
  >
    <div class="sidebar-content">
      <div class="menu-section">
        <ul class="menu-items">
          <li
            v-for="item in navigationItems"
            :key="item.label"
          >
            <RouterLink
              :to="item.to"
              class="menu-link"
              :class="{ active: item.active }"
            >
              <i :class="item.icon" />
              <span class="menu-text">{{ item.label }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>

      <div class="sidebar-toggle">
        <Button
          :icon="isExpanded ? 'pi pi-angle-double-left' : 'pi pi-angle-double-right'"
          text
          rounded
          aria-label="Toggle Sidebar"
          class="toggle-button"
          @click="toggleExpanded"
        />
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import { computed } from 'vue'
import { useNavigation } from '@/composables/useNavigation'
import type { MenuItem } from '@/types/navigation'

const { menuItems, isExpanded, toggleExpanded } = useNavigation()

const navigationItems = computed(() =>
  menuItems.value.filter((item): item is MenuItem & { to: string } => !!item.to && !item.bottomSection)
)
</script>

<style lang="scss" scoped>
.layout-sidebar-desktop {
  width: 4rem;
  background: var(--p-surface-card);
  transition: all 0.3s ease;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  border-right: 1px solid var(--p-navigation-border);
  position: fixed;
  top: 4rem;
  bottom: 0;
  left: 0;
  z-index: 999;

  &.sidebar-expanded {
    width: 200px;
  }

  .sidebar-content {
    min-width: 4rem;
    width: 200px;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .menu-section {
    padding: 1rem 0;
    flex-grow: 1;
  }

  .sidebar-toggle {
    margin-top: auto;
    padding: 0;
    display: flex;
    justify-content: flex-start;
    min-width: 3rem;
    height: 3rem;

    .toggle-button {
      width: 3rem;
      height: 3rem;
      margin-left: 0.5rem;
    }
  }
}

.menu-items {
  list-style: none;
  padding: 0;
  margin: 0;

  .menu-link {
    display: flex;
    align-items: center;
    padding: 0.875rem 1rem;
    color: var(--p-text-color);
    text-decoration: none;
    white-space: nowrap;
    transition: all 0.2s ease;
    border-radius: 0.25rem;
    margin: 0.125rem 0.25rem;

    &:hover {
      background-color: var(--p-surface-hover);
      transform: translateX(2px);
    }

    &.active {
      background-color: var(--p-navigation-item-active-background);
      color: var(--p-primary-color);
      font-weight: 500;

      i {
        color: var(--p-primary-color);
      }
    }

    i {
      width: 1.5rem;
      font-size: 1.125rem;
      text-align: center;
      color: var(--p-text-color-secondary);
      transition: color 0.2s;
    }

    .menu-text {
      margin-left: 1.25rem;
    }
  }
}

@media screen and (max-width: 768px) {
  .layout-sidebar-desktop {
    display: none;
  }
}
</style>
