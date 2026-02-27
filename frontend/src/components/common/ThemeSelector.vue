<template>
  <div class="theme-selector">
    <Select
      v-model="selectedThemeMode"
      :options="themeOptions"
      option-label="name"
      option-value="value"
      class="theme-select"
      @update:modelValue="handleThemeUpdate"
    >
      <template #value="slotProps">
        <div class="flex text-xs items-center">
          <i :class="['pi mr-2', getThemeIcon(slotProps.value)]" />
          <span>{{ getThemeName(slotProps.value) }}</span>
        </div>
      </template>
      <template #option="slotProps">
        <div class="flex text-xs items-center">
          <i :class="['pi mr-2', getThemeIcon(slotProps.option.value)]" />
          <div>
            <span>{{ slotProps.option.name }}</span>
            <div class="text-xs">
              {{ slotProps.option.description }}
            </div>
          </div>
        </div>
      </template>
    </Select>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useThemeStore, type ThemeMode } from '@/stores/themeStore'
import Select from 'primevue/select'

const themeStore = useThemeStore()

const selectedThemeMode = computed({
  get: () => themeStore.currentThemeMode,
  set: (value: ThemeMode) => {
    themeStore.setThemeMode(value)
  },
})

const themeOptions = [
  {
    name: 'Helles Design',
    value: 'light' as ThemeMode,
    description: 'Optimiert für Tageslicht',
  },
  {
    name: 'Dunkles Design',
    value: 'dark' as ThemeMode,
    description: 'Optimiert für geringe Helligkeit',
  },
  {
    name: 'Automatisch',
    value: 'auto' as ThemeMode,
    description: 'Wechselt basierend auf Tageszeit',
  },
]

const getThemeName = (value: ThemeMode): string => {
  const theme = themeOptions.find((t) => t.value === value)
  return theme?.name || 'Design auswählen'
}

const getThemeIcon = (value: ThemeMode): string => {
  switch (value) {
    case 'dark':
      return 'pi-moon'
    case 'light':
      return 'pi-sun'
    case 'auto':
      return 'pi-clock'
    default:
      return 'pi-sun'
  }
}

const handleThemeUpdate = (value: ThemeMode) => {
  selectedThemeMode.value = value
}
</script>

<style scoped>
.theme-selector {
  display: flex;
  align-items: center;
}

.theme-select {
  min-width: 180px;
}

:deep(.p-select) {
  font-size: 0.875rem;
}
</style>
