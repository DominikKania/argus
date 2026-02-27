import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark' | 'auto'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    isDarkMode: localStorage.getItem('isDarkMode') === 'true',
    themeMode: (localStorage.getItem('themeMode') || 'auto') as ThemeMode,
  }),
  actions: {
    setTheme(isDark: boolean) {
      this.isDarkMode = isDark
      localStorage.setItem('isDarkMode', isDark.toString())

      const root = document.documentElement
      if (isDark) {
        root.classList.add('dark')
        root.style.colorScheme = 'dark'
      } else {
        root.classList.remove('dark')
        root.style.colorScheme = 'light'
      }
    },

    setThemeMode(mode: ThemeMode) {
      this.themeMode = mode
      localStorage.setItem('themeMode', mode)

      if (mode === 'auto') {
        this.applyAutoTheme()
      } else {
        this.setTheme(mode === 'dark')
      }
    },

    applyAutoTheme() {
      const currentHour = new Date().getHours()
      const isDark = currentHour < 8 || currentHour >= 18
      this.setTheme(isDark)
    },

    initializeTheme() {
      const themeMode = localStorage.getItem('themeMode') as ThemeMode
      if (themeMode) {
        this.setThemeMode(themeMode)
      } else {
        this.setThemeMode('auto')
      }
    },
  },
  getters: {
    currentTheme: (state) => (state.isDarkMode ? 'dark' : 'light'),
    currentThemeMode: (state) => state.themeMode,
  },
})
