import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Analysis, OpenThesis, Position } from '@/types/ampel'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'

export const useAmpelStore = defineStore('ampel', () => {
  const latestAnalysis = ref<Analysis | null>(null)
  const history = ref<Analysis[]>([])
  const theses = ref<OpenThesis[]>([])
  const resolvedTheses = ref<OpenThesis[]>([])
  const positions = ref<Position[]>([])
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

  async function fetchResolvedTheses() {
    try {
      resolvedTheses.value = await ApiService.get<OpenThesis[]>(API_ENDPOINTS.AMPEL.THESES_RESOLVED)
    } catch (err) {
      console.error(err)
    }
  }

  async function fetchPositions() {
    try {
      positions.value = await ApiService.get<Position[]>(API_ENDPOINTS.AMPEL.POSITIONS)
    } catch (err) {
      console.error(err)
    }
  }

  async function createPosition(data: {
    ticker?: string
    entry_price: number
    entry_date: string
    quantity?: number
    thesis_id?: string
    notes?: string
  }): Promise<Position | null> {
    try {
      const pos = await ApiService.post<Position>(API_ENDPOINTS.AMPEL.CREATE_POSITION, data)
      positions.value.unshift(pos)
      return pos
    } catch (err) {
      console.error(err)
      return null
    }
  }

  async function closePosition(
    id: string,
    data: { exit_price: number; exit_date: string; notes?: string },
  ): Promise<Position | null> {
    try {
      const pos = await ApiService.put<Position>(API_ENDPOINTS.AMPEL.CLOSE_POSITION(id), data)
      const idx = positions.value.findIndex((p) => p._id === id)
      if (idx >= 0) positions.value.splice(idx, 1)
      return pos
    } catch (err) {
      console.error(err)
      return null
    }
  }

  async function deletePosition(id: string): Promise<boolean> {
    try {
      await ApiService.delete(API_ENDPOINTS.AMPEL.DELETE_POSITION(id))
      positions.value = positions.value.filter((p) => p._id !== id)
      return true
    } catch (err) {
      console.error(err)
      return false
    }
  }

  async function updateThesis(id: string, data: Partial<OpenThesis>): Promise<OpenThesis | null> {
    try {
      const updated = await ApiService.put<OpenThesis>(API_ENDPOINTS.AMPEL.UPDATE_THESIS(id), data)
      const idx = theses.value.findIndex((t) => t._id === id)
      if (idx >= 0) theses.value[idx] = updated
      return updated
    } catch (err) {
      console.error(err)
      return null
    }
  }

  async function refineThesis(
    thesis: Record<string, unknown>,
    chatHistory: Array<{ role: string; content: string }>,
  ): Promise<Record<string, unknown> | null> {
    try {
      const res = await ApiService.post<{ thesis: Record<string, unknown> }>(
        API_ENDPOINTS.AMPEL.REFINE_THESIS,
        { thesis, chat_history: chatHistory },
      )
      return res.thesis
    } catch (err) {
      console.error(err)
      return null
    }
  }

  return {
    latestAnalysis,
    history,
    theses,
    resolvedTheses,
    positions,
    loading,
    error,
    fetchLatest,
    fetchHistory,
    fetchTheses,
    fetchResolvedTheses,
    fetchDashboard,
    updateThesis,
    refineThesis,
    fetchPositions,
    createPosition,
    closePosition,
    deletePosition,
  }
})
