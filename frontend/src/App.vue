<template>
  <div :class="{ dark: isDarkTheme }">
    <Toast position="top-center" />
    <ConfirmDialog />
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useThemeStore } from '@/stores/themeStore'
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'
import { createNavigation } from '@/composables/useNavigation'

const themeStore = useThemeStore()
const isDarkTheme = computed(() => themeStore.isDarkMode)

let autoThemeInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  themeStore.initializeTheme()

  if (themeStore.currentThemeMode === 'auto') {
    autoThemeInterval = setInterval(() => {
      if (themeStore.currentThemeMode === 'auto') {
        themeStore.applyAutoTheme()
      }
    }, 60000)
  }
})

onUnmounted(() => {
  if (autoThemeInterval) {
    clearInterval(autoThemeInterval)
  }
})

// Initialize navigation with Argus menu items
const route = useRoute()

createNavigation({
  menuItemsFactory: () => [
    {
      label: 'Dashboard',
      icon: 'pi pi-home',
      to: '/',
      active: route.path === '/',
    },
    {
      label: 'Ampel',
      icon: 'pi pi-chart-bar',
      to: '/ampel',
      active: route.path.startsWith('/ampel'),
    },
    {
      label: 'Thesen',
      icon: 'pi pi-bookmark',
      to: '/thesen',
      active: route.path.startsWith('/thesen'),
    },
    {
      label: 'Kurse',
      icon: 'pi pi-chart-line',
      to: '/kurse',
      active: route.path.startsWith('/kurse'),
    },
    {
      label: 'Research',
      icon: 'pi pi-search',
      to: '/research',
      active: route.path.startsWith('/research'),
    },
    {
      label: 'News',
      icon: 'pi pi-megaphone',
      to: '/news',
      active: route.path.startsWith('/news'),
    },
    {
      label: 'Prompt',
      icon: 'pi pi-database',
      to: '/prompt-kontext',
      active: route.path.startsWith('/prompt-kontext'),
    },
  ],
})
</script>

<style>
@import 'tailwindcss';

#app {
  font-family: var(--p-font-family);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--p-text-color);
  background-color: var(--p-surface-ground);
}

.p-toast .p-toast-message .p-toast-message-content {
  border-width: 0;
}

:root {
  color-scheme: light;
}

:root.dark {
  color-scheme: dark;
}
</style>
