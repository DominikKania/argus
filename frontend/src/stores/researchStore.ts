import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'
import type { Research } from '@/types/research'

export const useResearchStore = defineStore('research', () => {
  const topics = ref<Research[]>([])
  const selectedTopic = ref<Research | null>(null)
  const loading = ref(false)
  const running = ref(false)
  const error = ref<string | null>(null)

  async function fetchTopics() {
    loading.value = true
    error.value = null
    try {
      topics.value = await ApiService.get<Research[]>(API_ENDPOINTS.RESEARCH.LIST)
    } catch (err) {
      error.value = 'Fehler beim Laden der Research-Themen'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchTopic(id: string) {
    loading.value = true
    error.value = null
    try {
      selectedTopic.value = await ApiService.get<Research>(API_ENDPOINTS.RESEARCH.DETAIL(id))
    } catch (err) {
      error.value = 'Fehler beim Laden des Topics'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function createTopic(title: string, prompt?: string, direction?: string): Promise<Research | null> {
    loading.value = true
    error.value = null
    try {
      const created = await ApiService.post<Research>(API_ENDPOINTS.RESEARCH.CREATE, {
        title,
        prompt: prompt || undefined,
        direction: direction || undefined,
      })
      topics.value.unshift(created)
      selectedTopic.value = created
      return created
    } catch (err: any) {
      error.value = err?.response?.data?.detail || 'Fehler beim Erstellen'
      console.error(err)
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateTopic(id: string, data: { title?: string; prompt?: string }) {
    error.value = null
    try {
      const updated = await ApiService.put<Research>(API_ENDPOINTS.RESEARCH.UPDATE(id), data)
      const idx = topics.value.findIndex((t) => t._id === id)
      if (idx >= 0) topics.value[idx] = updated
      if (selectedTopic.value?._id === id) selectedTopic.value = updated
      return updated
    } catch (err) {
      error.value = 'Fehler beim Aktualisieren'
      console.error(err)
      return null
    }
  }

  async function runResearch(id: string) {
    running.value = true
    error.value = null
    // Optimistic: mark as running
    if (selectedTopic.value?._id === id) {
      selectedTopic.value = { ...selectedTopic.value, status: 'running', error_message: null }
    }
    const idx = topics.value.findIndex((t) => t._id === id)
    if (idx >= 0) {
      topics.value[idx] = { ...topics.value[idx], status: 'running', error_message: null }
    }
    try {
      const updated = await ApiService.post<Research>(API_ENDPOINTS.RESEARCH.RUN(id), {})
      if (idx >= 0) topics.value[idx] = updated
      if (selectedTopic.value?._id === id) selectedTopic.value = updated
      return updated
    } catch (err: any) {
      error.value = err?.response?.data?.detail || 'Research fehlgeschlagen'
      // Refresh to get actual state
      await fetchTopic(id)
      console.error(err)
      return null
    } finally {
      running.value = false
    }
  }

  async function deleteTopic(id: string) {
    error.value = null
    try {
      await ApiService.delete(API_ENDPOINTS.RESEARCH.DELETE(id))
      topics.value = topics.value.filter((t) => t._id !== id)
      if (selectedTopic.value?._id === id) {
        selectedTopic.value = topics.value[0] || null
      }
      return true
    } catch (err) {
      error.value = 'Fehler beim Löschen'
      console.error(err)
      return false
    }
  }

  async function generatePrompt(title: string, direction?: string): Promise<string | null> {
    try {
      const res = await ApiService.post<{ prompt: string }>(
        API_ENDPOINTS.RESEARCH.GENERATE_PROMPT,
        { title, direction: direction || undefined },
      )
      return res.prompt
    } catch (err) {
      console.error(err)
      return null
    }
  }

  return {
    topics,
    selectedTopic,
    loading,
    running,
    error,
    fetchTopics,
    fetchTopic,
    createTopic,
    updateTopic,
    runResearch,
    deleteTopic,
    generatePrompt,
  }
})
