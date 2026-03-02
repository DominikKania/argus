import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PriceEntry, WatchlistEntry } from '@/types/prices'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'

export const usePricesStore = defineStore('prices', () => {
  const watchlist = ref<WatchlistEntry[]>([])
  const prices = ref<PriceEntry[]>([])
  const selectedTicker = ref<string>('IWDA.AS')
  const loading = ref(false)
  const syncing = ref(false)
  const error = ref<string | null>(null)

  async function fetchWatchlist() {
    try {
      watchlist.value = await ApiService.get<WatchlistEntry[]>(API_ENDPOINTS.PRICES.WATCHLIST)
    } catch (err) {
      console.error('Fehler beim Laden der Watchlist:', err)
    }
  }

  async function fetchPrices(ticker: string, days = 60) {
    loading.value = true
    error.value = null
    selectedTicker.value = ticker
    try {
      prices.value = await ApiService.get<PriceEntry[]>(API_ENDPOINTS.PRICES.TICKER(ticker, days))
    } catch (err) {
      error.value = `Fehler beim Laden der Kursdaten für ${ticker}`
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchAll(ticker?: string) {
    loading.value = true
    error.value = null
    try {
      await fetchWatchlist()
      const t = ticker || selectedTicker.value || watchlist.value[0]?.ticker || 'IWDA.AS'
      await fetchPrices(t, 60)
    } catch (err) {
      error.value = 'Fehler beim Laden der Kursdaten'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function syncPrices() {
    syncing.value = true
    error.value = null
    try {
      const result = await ApiService.post<{ total_new_records: number; results: any[] }>(
        API_ENDPOINTS.PRICES.SYNC,
        {},
      )
      // Reload current view after sync
      await fetchPrices(selectedTicker.value, 60)
      return result
    } catch (err) {
      error.value = 'Fehler beim Synchronisieren der Kursdaten'
      console.error(err)
      throw err
    } finally {
      syncing.value = false
    }
  }

  return {
    watchlist,
    prices,
    selectedTicker,
    loading,
    syncing,
    error,
    fetchWatchlist,
    fetchPrices,
    fetchAll,
    syncPrices,
  }
})
