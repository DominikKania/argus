<template>
  <div class="layout-wrapper">
    <DesktopSidebar />
    <MobileSidebar />

    <div class="layout-main" :class="{ 'sidebar-expanded': isExpanded }">
      <TopBar />

      <div class="layout-content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useNavigation } from '@/composables/useNavigation'
import TopBar from '@/components/navigation/TopBar.vue'
import DesktopSidebar from '@/components/navigation/DesktopSidebar.vue'
import MobileSidebar from '@/components/navigation/MobileSidebar.vue'

const { isExpanded } = useNavigation()
</script>

<style lang="scss">
.layout-wrapper {
  min-height: 100vh;
  display: flex;
  background-color: var(--p-surface-ground);
}

.layout-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  position: relative;
  transition: margin-left 0.3s ease;
}

.layout-content {
  flex: 1;
  padding: 0;
  @apply md:p-8;
  background: var(--p-surface-ground);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 4rem);
  margin-top: 4rem;
}

@media screen and (min-width: 769px) {
  .layout-main {
    margin-left: 4rem;

    &.sidebar-expanded {
      margin-left: 200px;
    }
  }

  .layout-content {
    margin-top: calc(4rem + 2px);
  }
}
</style>
