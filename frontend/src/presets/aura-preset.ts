import { definePreset } from '@primevue/themes'
import Aura from '@primevue/themes/aura'

export const ArgusAuraPreset = definePreset(Aura, {
  components: {
    dialog: {
      header: { padding: '1rem' },
      content: { padding: '0' },
      background: '{surface.ground}',
      title: { font: { size: '0.875rem', weight: '100' } },
    },
    drawer: {
      header: { padding: '0rem' },
      background: '{surface.card}',
    },
    card: {
      background: '{surface.card}',
    },
    breadcrumb: {
      background: 'transparent',
    },
  },
  semantic: {
    formField: {
      background: '{surface.0}',
    },
    colorScheme: {
      dark: {
        formField: {
          background: '{zinc.900}',
          disabledBackground: '{zinc.800}',
          filledBackground: '{zinc.800}',
          borderColor: '{zinc.700}',
          hoverBorderColor: '{zinc.600}',
        },
        overlay: {
          background: '{zinc.800}',
          borderColor: '{zinc.700}',
        },
        primary: {
          '50': '{indigo.50}',
          '100': '{indigo.100}',
          '200': '{indigo.200}',
          '300': '{indigo.300}',
          '400': '{indigo.400}',
          '500': '{indigo.500}',
          '600': '{indigo.600}',
          '700': '{indigo.700}',
          '800': '{indigo.800}',
          '900': '{indigo.900}',
          '950': '{indigo.950}',
        },
        surface: {
          ground: '{zinc.900}',
          card: '{zinc.800}',
          border: '{zinc.700}',
          hover: '{zinc.700/50}',
          section: '{zinc.800}',
        },
        navigation: {
          border: '{zinc.700}',
          item: {
            active: { background: '{zinc.700}' },
          },
        },
      },
      light: {
        primary: {
          '50': '{indigo.50}',
          '100': '{indigo.100}',
          '200': '{indigo.200}',
          '300': '{indigo.300}',
          '400': '{indigo.400}',
          '500': '{indigo.500}',
          '600': '{indigo.600}',
          '700': '{indigo.700}',
          '800': '{indigo.800}',
          '900': '{indigo.900}',
          '950': '{indigo.950}',
        },
        surface: {
          ground: '{surface.0}',
          card: '{zinc.50}',
          border: '{zinc.200}',
          hover: '{zinc.100}',
          section: '{zinc.50}',
        },
        navigation: {
          border: '{zinc.200}',
          item: {
            active: { background: '{zinc.100}' },
          },
        },
      },
    },
  },
})
