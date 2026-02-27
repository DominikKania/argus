import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import PrimeVue from 'primevue/config'
import Drawer from 'primevue/drawer'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Tooltip from 'primevue/tooltip'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import ConfirmDialog from 'primevue/confirmdialog'
import router from './router'
import { ArgusAuraPreset } from './presets/aura-preset'

import 'primeicons/primeicons.css'

// Apply theme class BEFORE Vue mounts to prevent flash of unstyled content
const applyInitialTheme = () => {
  const themeMode = localStorage.getItem('themeMode')
  const savedIsDark = localStorage.getItem('isDarkMode') === 'true'

  let isDark = false
  if (themeMode === 'auto' || !themeMode) {
    const currentHour = new Date().getHours()
    isDark = currentHour < 8 || currentHour >= 18
  } else if (themeMode === 'dark') {
    isDark = true
  } else if (themeMode === 'light') {
    isDark = false
  } else {
    isDark = savedIsDark
  }

  if (isDark) {
    document.documentElement.classList.add('dark')
    document.documentElement.style.colorScheme = 'dark'
  } else {
    document.documentElement.classList.remove('dark')
    document.documentElement.style.colorScheme = 'light'
  }
}

applyInitialTheme()

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

app.use(PrimeVue, {
  theme: {
    preset: ArgusAuraPreset,
    options: {
      darkModeSelector: '.dark',
    },
  },
})

app.use(router)
app.use(ToastService)
app.use(ConfirmationService)

app.component('Drawer', Drawer)
app.component('Button', Button)
app.component('Card', Card)
app.component('Divider', Divider)
app.component('ConfirmDialog', ConfirmDialog)
app.directive('tooltip', Tooltip)

app.mount('#app')
