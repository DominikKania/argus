import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface PromptReviewContext {
  topicId: string
  topicTitle: string
  prompt: string
}

export interface ThesisReviewContext {
  thesisId: string
  statement: string
  thesis: Record<string, unknown>
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isOpen = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentView = ref('dashboard')
  const currentTicker = ref<string | null>(null)
  const promptReviewContext = ref<PromptReviewContext | null>(null)
  const refinedPrompt = ref<string | null>(null)
  const thesisReviewContext = ref<ThesisReviewContext | null>(null)
  const refinedThesis = ref<Record<string, unknown> | null>(null)

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
    promptReviewContext.value = null
    thesisReviewContext.value = null
    isOpen.value = true
    sendMessage(topic)
  }

  function openForPromptReview(ctx: PromptReviewContext) {
    messages.value = []
    error.value = null
    promptReviewContext.value = ctx
    thesisReviewContext.value = null
    isOpen.value = true
  }

  function openForThesisReview(ctx: ThesisReviewContext) {
    messages.value = []
    error.value = null
    promptReviewContext.value = null
    thesisReviewContext.value = ctx
    isOpen.value = true
  }

  async function sendMessage(userMessage: string) {
    if (!userMessage.trim() || isLoading.value) return

    messages.value.push({ role: 'user', content: userMessage.trim() })

    isLoading.value = true
    error.value = null

    // Add empty assistant message to build up incrementally
    messages.value.push({ role: 'assistant', content: '' })
    const assistantIdx = messages.value.length - 1

    try {
      const history = messages.value.slice(0, -2) // exclude current user + empty assistant

      const context: Record<string, unknown> = {
        view: currentView.value,
        ticker: currentTicker.value,
      }
      if (promptReviewContext.value) {
        context.prompt_review = promptReviewContext.value.prompt
        context.prompt_topic = promptReviewContext.value.topicTitle
      }
      if (thesisReviewContext.value) {
        context.thesis_review = JSON.stringify(thesisReviewContext.value.thesis)
      }

      const response = await fetch('/api' + API_ENDPOINTS.CHAT_STREAM, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage.trim(),
          history,
          context,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') continue

          try {
            const parsed = JSON.parse(data)
            if (typeof parsed === 'string') {
              messages.value[assistantIdx] = {
                ...messages.value[assistantIdx],
                content: messages.value[assistantIdx].content + parsed,
              }
            } else if (parsed.error) {
              throw new Error(parsed.error)
            }
          } catch (parseErr) {
            // Ignore parse errors for incomplete chunks
          }
        }
      }

      // Remove empty assistant message if nothing was received
      if (!messages.value[assistantIdx].content) {
        messages.value.splice(assistantIdx, 1)
        error.value = 'Keine Antwort erhalten'
      }
    } catch (err) {
      error.value = 'Fehler beim Senden der Nachricht'
      console.error(err)
      // Remove empty assistant message and user message on error
      if (!messages.value[assistantIdx]?.content) {
        messages.value.splice(assistantIdx, 1) // remove empty assistant
        messages.value.pop() // remove user message
      }
    } finally {
      isLoading.value = false
    }
  }

  function clearHistory() {
    messages.value = []
    error.value = null
    promptReviewContext.value = null
    thesisReviewContext.value = null
  }

  return {
    messages,
    isOpen,
    isLoading,
    error,
    currentView,
    currentTicker,
    promptReviewContext,
    refinedPrompt,
    thesisReviewContext,
    refinedThesis,
    setView,
    setTicker,
    toggleChat,
    openChat,
    closeChat,
    openWithContext,
    openForPromptReview,
    openForThesisReview,
    sendMessage,
    clearHistory,
  }
})
