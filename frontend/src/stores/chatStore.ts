import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'
import { ApiService } from '@/services/apiService'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isOpen = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentView = ref('dashboard')
  const currentTicker = ref<string | null>(null)

  function setView(view: string) {
    currentView.value = view
  }

  function setTicker(ticker: string | null) {
    currentTicker.value = ticker
  }

  function toggleChat() {
    isOpen.value = !isOpen.value
  }

  function openChat() {
    isOpen.value = true
  }

  function closeChat() {
    isOpen.value = false
  }

  function openWithContext(topic: string) {
    messages.value = []
    error.value = null
    isOpen.value = true
    sendMessage(topic)
  }

  async function sendMessage(userMessage: string) {
    if (!userMessage.trim() || isLoading.value) return

    messages.value.push({ role: 'user', content: userMessage.trim() })

    isLoading.value = true
    error.value = null

    try {
      const history = messages.value.slice(0, -1)

      const response = await ApiService.post<{ response: string }>(
        API_ENDPOINTS.CHAT,
        {
          message: userMessage.trim(),
          history,
          context: {
            view: currentView.value,
            ticker: currentTicker.value,
          },
        }
      )

      messages.value.push({ role: 'assistant', content: response.response })
    } catch (err) {
      error.value = 'Fehler beim Senden der Nachricht'
      console.error(err)
      messages.value.pop()
    } finally {
      isLoading.value = false
    }
  }

  function clearHistory() {
    messages.value = []
    error.value = null
  }

  return {
    messages,
    isOpen,
    isLoading,
    error,
    currentView,
    currentTicker,
    setView,
    setTicker,
    toggleChat,
    openChat,
    closeChat,
    openWithContext,
    sendMessage,
    clearHistory,
  }
})
