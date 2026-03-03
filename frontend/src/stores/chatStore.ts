import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/**
 * Typewriter that drips queued text word-by-word into a target ref.
 * Creates a smooth "someone is typing" feel regardless of network chunking.
 */
/**
 * RAF-based smooth streamer. Buffers all incoming text and reveals it
 * character-by-character at a constant rate synced to the display refresh.
 * This is the same technique used by ChatGPT / Vercel AI SDK.
 */
function createSmoothStream(
  messages: { value: ChatMessage[] },
  getIdx: () => number,
  charsPerSecond = 200,
) {
  let fullText = ''
  let charIndex = 0
  let lastTime = 0
  let frameId: number | null = null
  const msPerChar = 1000 / charsPerSecond

  function animate(time: number) {
    const elapsed = time - lastTime
    if (elapsed >= msPerChar) {
      // Advance by however many chars are due (catch up if behind)
      const charsToAdvance = Math.max(1, Math.floor(elapsed / msPerChar))
      charIndex = Math.min(charIndex + charsToAdvance, fullText.length)

      const idx = getIdx()
      messages.value[idx] = {
        ...messages.value[idx],
        content: fullText.slice(0, charIndex),
      }
      lastTime = time
    }

    if (charIndex < fullText.length) {
      frameId = requestAnimationFrame(animate)
    } else {
      frameId = null
    }
  }

  return {
    push(text: string) {
      fullText += text
      if (!frameId) {
        lastTime = performance.now()
        frameId = requestAnimationFrame(animate)
      }
    },
    finish() {
      if (frameId) {
        cancelAnimationFrame(frameId)
        frameId = null
      }
      const idx = getIdx()
      messages.value[idx] = {
        ...messages.value[idx],
        content: fullText,
      }
      charIndex = fullText.length
    },
    get pending() {
      return charIndex < fullText.length
    },
  }
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

export interface LessonContext {
  thesisId: string
  statement: string
  resolution: string
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
  const lessonContext = ref<LessonContext | null>(null)

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
    lessonContext.value = null
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

  function openForLesson(ctx: LessonContext) {
    messages.value = []
    error.value = null
    promptReviewContext.value = null
    thesisReviewContext.value = null
    lessonContext.value = ctx
    isOpen.value = true
    sendMessage(
      `Lass uns über diese aufgelöste These sprechen und daraus lernen:\n\n` +
      `These: ${ctx.statement}\n` +
      `Auflösung: ${ctx.resolution}\n\n` +
      `Was können wir daraus lernen? War die These gut formuliert? Was sollten wir bei zukünftigen Analysen anders machen?`
    )
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

    const typewriter = createSmoothStream(messages, () => assistantIdx)

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
              typewriter.push(parsed)
            } else if (parsed.error) {
              throw new Error(parsed.error)
            }
          } catch (parseErr) {
            // Ignore parse errors for incomplete chunks
          }
        }
      }

      // Drain any remaining queued text
      typewriter.finish()

      // Remove empty assistant message if nothing was received
      if (!messages.value[assistantIdx].content) {
        messages.value.splice(assistantIdx, 1)
        error.value = 'Keine Antwort erhalten'
      }
    } catch (err) {
      typewriter.finish()
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
    lessonContext.value = null
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
    lessonContext,
    setView,
    setTicker,
    toggleChat,
    openChat,
    closeChat,
    openWithContext,
    openForPromptReview,
    openForThesisReview,
    openForLesson,
    sendMessage,
    clearHistory,
  }
})
