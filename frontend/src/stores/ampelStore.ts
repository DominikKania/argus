import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Analysis, OpenThesis } from '@/types/ampel'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'

export const useAmpelStore = defineStore('ampel', () => {
  const latestAnalysis = ref<Analysis | null>(null)
  const history = ref<Analysis[]>([])
  const theses = ref<OpenThesis[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchLatest() {
    loading.value = true
    error.value = null
    try {
      latestAnalysis.value = await ApiService.get<Analysis>(API_ENDPOINTS.AMPEL.LATEST)
    } catch (err) {
      error.value = 'Fehler beim Laden der letzten Analyse'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchHistory(limit = 10) {
    loading.value = true
    error.value = null
    try {
      history.value = await ApiService.get<Analysis[]>(API_ENDPOINTS.AMPEL.HISTORY(limit))
    } catch (err) {
      error.value = 'Fehler beim Laden der Historie'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchTheses() {
    loading.value = true
    error.value = null
    try {
      theses.value = await ApiService.get<OpenThesis[]>(API_ENDPOINTS.AMPEL.THESES)
    } catch (err) {
      error.value = 'Fehler beim Laden der Thesen'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchDashboard() {
    loading.value = true
    error.value = null
    try {
      await Promise.all([fetchLatestQuiet(), fetchThesesQuiet()])
    } catch (err) {
      error.value = 'Fehler beim Laden des Dashboards'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchLatestQuiet() {
    latestAnalysis.value = await ApiService.get<Analysis>(API_ENDPOINTS.AMPEL.LATEST)
  }

  async function fetchThesesQuiet() {
    theses.value = await ApiService.get<OpenThesis[]>(API_ENDPOINTS.AMPEL.THESES)
  }

  return {
    latestAnalysis,
    history,
    theses,
    loading,
    error,
    fetchLatest,
    fetchHistory,
    fetchTheses,
    fetchDashboard,
  }
})
