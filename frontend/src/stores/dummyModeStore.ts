import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useDummyModeStore = defineStore('dummyMode', () => {
  const isDummyMode = ref(localStorage.getItem('argus-dummy-mode') === 'true')

  function toggleDummyMode() {
    isDummyMode.value = !isDummyMode.value
    localStorage.setItem('argus-dummy-mode', isDummyMode.value.toString())
  }

  return {
    isDummyMode,
    toggleDummyMode,
  }
})
