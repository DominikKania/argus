import { ref, computed, provide, inject, type InjectionKey, type Ref, type ComputedRef } from 'vue'
import type { MenuItem } from '@/types/navigation'

export interface NavigationStore {
  sidebarVisible: Ref<boolean>
  isExpanded: Ref<boolean>
  menuItems: ComputedRef<MenuItem[]>
  toggleSidebar: () => void
  toggleExpanded: () => void
}

export interface NavigationConfig {
  menuItemsFactory: () => MenuItem[]
}

const navigationKey = Symbol.for('argus:navigation') as InjectionKey<NavigationStore>
const SIDEBAR_STORAGE_KEY = 'argus-sidebar-expanded'

export function createNavigation(config: NavigationConfig): NavigationStore {
  const sidebarVisible = ref(false)
  const isExpanded = ref(localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true')

  const menuItems = computed<MenuItem[]>(() => config.menuItemsFactory())

  const toggleSidebar = () => {
    sidebarVisible.value = !sidebarVisible.value
  }

  const toggleExpanded = () => {
    isExpanded.value = !isExpanded.value
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(isExpanded.value))
  }

  const store: NavigationStore = {
    sidebarVisible,
    isExpanded,
    menuItems,
    toggleSidebar,
    toggleExpanded,
  }

  provide(navigationKey, store)
  return store
}

export function useNavigation(): NavigationStore {
  const store = inject(navigationKey)
  if (!store) {
    throw new Error('useNavigation must be used within a component that has called createNavigation')
  }
  return store
}
