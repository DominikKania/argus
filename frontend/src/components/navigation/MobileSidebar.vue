<template>
  <Drawer
    :visible="sidebarVisible"
    :modal="true"
    :dismissable="true"
    :show-close-icon="false"
    class="layout-sidebar-mobile"
    position="left"
    @update:visible="toggleSidebar"
  >
    <div class="sidebar-header">
      <span class="sidebar-title">Argus</span>
    </div>
    <div class="sidebar-content">
      <ul class="menu-items">
        <li
          v-for="item in navigationItems"
          :key="item.label"
        >
          <RouterLink
            :to="item.to"
            class="menu-link"
            :class="{ active: item.active }"
            @click="toggleSidebar"
          >
            <i :class="item.icon" />
            <span class="menu-text">{{ item.label }}</span>
          </RouterLink>
        </li>
      </ul>
    </div>
  </Drawer>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import Drawer from 'primevue/drawer'
import { computed } from 'vue'
import { useNavigation } from '@/composables/useNavigation'
import type { MenuItem } from '@/types/navigation'

const { sidebarVisible, menuItems, toggleSidebar } = useNavigation()

const navigationItems = computed(() =>
  menuItems.value.filter((item): item is MenuItem & { to: string } =>
    !!item.to && !item.action
  )
)
</script>

<style lang="scss" scoped>
.layout-sidebar-mobile {
  :deep(.p-drawer) {
    width: 100%;
    max-width: 280px;
  }

  .sidebar-header {
    padding: 1.5rem 0 0 0;
    display: flex;

    .sidebar-title {
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--p-primary-color);
    }
  }
}

.sidebar-content {
  padding-top: 1rem;
}

.menu-items {
  list-style: none;
  padding: 0;
  margin: 0;

  .menu-link {
    display: flex;
    align-items: center;
    padding: 0.75rem 0.5rem;
    color: var(--p-text-color);
    text-decoration: none;
    white-space: nowrap;
    transition: all 0.2s ease;
    border-radius: 0.25rem;
    margin: 0.125rem 0.75rem;

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
      display: flex;
      justify-content: center;
      color: var(--p-text-color-secondary);
      transition: color 0.2s;
    }

    .menu-text {
      margin-left: 0.75rem;
    }
  }
}

@media screen and (min-width: 769px) {
  .layout-sidebar-mobile {
    display: none;
  }
}
</style>
