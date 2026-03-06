import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'
import type { NewsTopic, WatchlistItem } from '@/types/news'

export const useNewsStore = defineStore('news', () => {
  const topics = ref<NewsTopic[]>([])
  const selectedTopic = ref<NewsTopic | null>(null)
  const loading = ref(false)
  const running = ref(false)
  const error = ref<string | null>(null)
  const watchlist = ref<WatchlistItem[]>([])

  async function fetchTopics() {
    loading.value = true
    error.value = null
    try {
      topics.value = await ApiService.get<NewsTopic[]>(API_ENDPOINTS.NEWS.LIST)
    } catch (err) {
      error.value = 'Fehler beim Laden der News-Themen'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchTopic(id: string) {
    loading.value = true
    error.value = null
    try {
      selectedTopic.value = await ApiService.get<NewsTopic>(API_ENDPOINTS.NEWS.DETAIL(id))
    } catch (err) {
      error.value = 'Fehler beim Laden des Topics'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchWatchlist() {
    try {
      watchlist.value = await ApiService.get<WatchlistItem[]>(API_ENDPOINTS.PRICES.WATCHLIST)
    } catch (err) {
      console.error('Watchlist laden fehlgeschlagen:', err)
    }
  }

  async function addAsset(ticker: string, name?: string, category: string = 'stock'): Promise<WatchlistItem | null> {
    try {
      const created = await ApiService.post<WatchlistItem>(API_ENDPOINTS.PRICES.ADD_WATCHLIST, {
        ticker, name: name || undefined, category,
      })
      watchlist.value.push(created)
      watchlist.value.sort((a, b) => a.ticker.localeCompare(b.ticker))
      return created
    } catch (err: any) {
      error.value = err?.response?.data?.detail || 'Fehler beim Hinzufügen'
      console.error(err)
      return null
    }
  }

  async function removeAsset(ticker: string): Promise<boolean> {
    try {
      await ApiService.delete(API_ENDPOINTS.PRICES.REMOVE_WATCHLIST(ticker))
      watchlist.value = watchlist.value.filter((w) => w.ticker !== ticker)
      return true
    } catch (err) {
      console.error(err)
      return false
    }
  }

  async function createTopic(
    title: string,
    prompt?: string,
    direction?: string,
    rssFeeds?: Array<{ name: string; url: string }>,
    assets?: string[],
  ): Promise<NewsTopic | null> {
    loading.value = true
    error.value = null
    try {
      const created = await ApiService.post<NewsTopic>(API_ENDPOINTS.NEWS.CREATE, {
        title,
        prompt: prompt || undefined,
        direction: direction || undefined,
        rss_feeds: rssFeeds || undefined,
        assets: assets?.length ? assets : undefined,
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

  async function updateTopic(id: string, data: { title?: string; prompt?: string; active?: boolean; rss_feeds?: Array<{ name: string; url: string }>; assets?: string[] }) {
    error.value = null
    try {
      const updated = await ApiService.put<NewsTopic>(API_ENDPOINTS.NEWS.UPDATE(id), data)
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

  async function toggleActive(id: string) {
    const topic = topics.value.find((t) => t._id === id)
    if (!topic) return null
    return updateTopic(id, { active: !topic.active })
  }

  async function runTopic(id: string) {
    running.value = true
    error.value = null
    try {
      const result = await ApiService.post<any>(API_ENDPOINTS.NEWS.RUN(id), {})
      // Refresh topic to get latest result
      await fetchTopic(id)
      // Also update list entry
      const idx = topics.value.findIndex((t) => t._id === id)
      if (idx >= 0 && selectedTopic.value) {
        topics.value[idx] = selectedTopic.value
      }
      return result
    } catch (err: any) {
      error.value = err?.response?.data?.detail || 'News-Analyse fehlgeschlagen'
      console.error(err)
      return null
    } finally {
      running.value = false
    }
  }

  async function runAll() {
    running.value = true
    error.value = null
    try {
      const result = await ApiService.post<{ topics_analyzed: number }>(API_ENDPOINTS.NEWS.RUN_ALL, {})
      await fetchTopics()
      return result
    } catch (err: any) {
      error.value = err?.response?.data?.detail || 'News-Analyse fehlgeschlagen'
      console.error(err)
      return null
    } finally {
      running.value = false
    }
  }

  async function deleteTopic(id: string) {
    error.value = null
    try {
      await ApiService.delete(API_ENDPOINTS.NEWS.DELETE(id))
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

  async function generatePrompt(title: string, direction?: string, assets?: string[]): Promise<string | null> {
    try {
      const res = await ApiService.post<{ prompt: string }>(
        API_ENDPOINTS.NEWS.GENERATE_PROMPT,
        { title, direction: direction || undefined, assets: assets?.length ? assets : undefined },
      )
      return res.prompt
    } catch (err) {
      console.error(err)
      return null
    }
  }

  async function refinePrompt(
    topicTitle: string,
    originalPrompt: string,
    chatHistory: Array<{ role: string; content: string }>,
  ): Promise<string | null> {
    try {
      const res = await ApiService.post<{ prompt: string }>(
        API_ENDPOINTS.NEWS.REFINE_PROMPT,
        { topic_title: topicTitle, original_prompt: originalPrompt, chat_history: chatHistory },
      )
      return res.prompt
    } catch (err) {
      console.error(err)
      return null
    }
  }

  async function suggestFeeds(
    title: string,
    prompt?: string,
  ): Promise<Array<{ name: string; url: string }> | null> {
    try {
      const res = await ApiService.post<{ feeds: Array<{ name: string; url: string }> }>(
        API_ENDPOINTS.NEWS.SUGGEST_FEEDS,
        { title, prompt: prompt || undefined },
      )
      return res.feeds
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
    watchlist,
    fetchTopics,
    fetchTopic,
    fetchWatchlist,
    addAsset,
    removeAsset,
    createTopic,
    updateTopic,
    toggleActive,
    runTopic,
    runAll,
    deleteTopic,
    generatePrompt,
    refinePrompt,
    suggestFeeds,
  }
})
