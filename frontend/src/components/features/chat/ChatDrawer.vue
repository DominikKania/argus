<template>
  <Drawer
    v-model:visible="chatStore.isOpen"
    position="right"
    :modal="false"
    class="chat-drawer"
  >
    <template #header>
      <div class="chat-header">
        <i class="pi pi-comments" />
        <span>Trading-Tutor</span>
        <Button
          v-if="chatStore.messages.length"
          icon="pi pi-trash"
          text
          rounded
          severity="secondary"
          size="small"
          v-tooltip.left="'Chat leeren'"
          @click="chatStore.clearHistory()"
        />
      </div>
    </template>

    <div class="chat-body" ref="chatBody">
      <!-- Prompt Review Banner -->
      <div v-if="chatStore.promptReviewContext" class="review-banner">
        <div class="banner-header">
          <i class="pi pi-file-edit" />
          <span>Prompt besprechen</span>
        </div>
        <p class="banner-topic">{{ chatStore.promptReviewContext.topicTitle }}</p>
        <Button
          v-if="chatStore.messages.length >= 2"
          label="Prompt aktualisieren"
          icon="pi pi-sync"
          size="small"
          class="refine-btn"
          :loading="refining"
          @click="refinePrompt"
        />
      </div>

      <!-- Thesis Review Banner -->
      <div v-if="chatStore.thesisReviewContext" class="review-banner review-banner-thesis">
        <div class="banner-header">
          <i class="pi pi-bookmark" />
          <span>These besprechen</span>
        </div>
        <p class="banner-topic">{{ chatStore.thesisReviewContext.statement }}</p>
        <Button
          v-if="chatStore.messages.length >= 2"
          label="These aktualisieren"
          icon="pi pi-sync"
          size="small"
          class="refine-btn"
          :loading="refiningThesis"
          @click="refineThesis"
        />
      </div>

      <!-- Lesson Banner -->
      <div v-if="chatStore.lessonContext" class="review-banner review-banner-lesson">
        <div class="banner-header">
          <i class="pi pi-lightbulb" />
          <span>Lernen aus These</span>
        </div>
        <p class="banner-topic">{{ chatStore.lessonContext.statement }}</p>
        <Button
          v-if="chatStore.messages.length >= 2"
          :label="lessonSaved ? 'Regeln gespeichert' : 'Regeln extrahieren'"
          :icon="lessonSaved ? 'pi pi-check' : 'pi pi-lightbulb'"
          size="small"
          class="refine-btn"
          :severity="lessonSaved ? 'success' : 'primary'"
          :disabled="lessonSaved || savingLesson"
          :loading="savingLesson"
          @click="saveLesson"
        />
      </div>

      <!-- Welcome -->
      <div v-if="!chatStore.messages.length && !chatStore.isLoading" class="welcome">
        <div class="welcome-icon">
          <i class="pi pi-sparkles" />
        </div>
        <h3 class="welcome-title">{{ welcomeTitle }}</h3>
        <p class="welcome-text">{{ welcomeText }}</p>
        <div class="suggestions">
          <button
            v-for="s in suggestions"
            :key="s"
            class="suggestion-chip"
            @click="chatStore.sendMessage(s)"
          >
            {{ s }}
          </button>
        </div>
      </div>

      <!-- Messages -->
      <template v-else>
        <template v-for="(msg, i) in chatStore.messages" :key="i">
          <!-- Skip empty assistant messages (streaming placeholder) -->
          <div
            v-if="msg.content || msg.role !== 'assistant'"
            class="message"
            :class="`message-${msg.role}`"
          >
            <div
              class="message-bubble"
              :class="{ streaming: chatStore.isLoading && msg.role === 'assistant' && i === chatStore.messages.length - 1 }"
            >{{ msg.content }}</div>
          </div>
        </template>

        <!-- Typing indicator (only while waiting for first chunk) -->
        <div v-if="chatStore.isLoading && (!lastMessage?.content || lastMessage.role !== 'assistant')" class="message message-assistant">
          <div class="message-bubble typing-bubble">
            <span class="typing-dot" />
            <span class="typing-dot" />
            <span class="typing-dot" />
          </div>
        </div>

        <!-- Error -->
        <div v-if="chatStore.error" class="chat-error">
          <i class="pi pi-exclamation-circle" />
          {{ chatStore.error }}
        </div>
      </template>
    </div>

    <template #footer>
      <div class="chat-input-area">
        <textarea
          ref="inputEl"
          v-model="inputText"
          class="chat-input"
          placeholder="Stelle eine Frage..."
          rows="1"
          @keydown.enter.exact.prevent="send"
          @input="autoResize"
        />
        <Button
          icon="pi pi-send"
          rounded
          :disabled="!inputText.trim() || chatStore.isLoading"
          @click="send"
        />
      </div>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import Drawer from 'primevue/drawer'
import Button from 'primevue/button'
import { useChatStore } from '@/stores/chatStore'
import { useAmpelStore } from '@/stores/ampelStore'
import { usePricesStore } from '@/stores/pricesStore'
import { useResearchStore } from '@/stores/researchStore'
import { ApiService } from '@/services/apiService'
import { API_ENDPOINTS } from '@/config/apiEndpoints'

const chatStore = useChatStore()
const ampelStore = useAmpelStore()
const pricesStore = usePricesStore()
const researchStore = useResearchStore()
const route = useRoute()
const inputText = ref('')
const chatBody = ref<HTMLElement>()
const inputEl = ref<HTMLTextAreaElement>()

const lastMessage = computed(() =>
  chatStore.messages.length ? chatStore.messages[chatStore.messages.length - 1] : null,
)
const refining = ref(false)
const refiningThesis = ref(false)
const savingLesson = ref(false)
const lessonSaved = ref(false)

async function refineThesis() {
  const ctx = chatStore.thesisReviewContext
  if (!ctx || chatStore.messages.length < 2) return
  refiningThesis.value = true
  const refined = await ampelStore.refineThesis(
    ctx.thesis,
    chatStore.messages.map(m => ({ role: m.role, content: m.content })),
  )
  refiningThesis.value = false
  if (refined) {
    chatStore.refinedThesis = refined
    chatStore.messages.push({
      role: 'assistant',
      content: 'These wurde aktualisiert und übernommen.',
    })
  }
}

async function saveLesson() {
  const ctx = chatStore.lessonContext
  if (!ctx || chatStore.messages.length < 2) return

  savingLesson.value = true
  try {
    // Send full conversation to LLM for lesson extraction
    const messages = chatStore.messages.map(m => ({ role: m.role, content: m.content }))
    const res = await ApiService.post<{ lessons_learned?: string }>(
      API_ENDPOINTS.AMPEL.EXTRACT_LESSONS(ctx.thesisId),
      { messages },
    )
    if (res?.lessons_learned) {
      lessonSaved.value = true
      chatStore.messages.push({
        role: 'assistant',
        content: `Regeln aus dem Gespräch extrahiert und gespeichert:\n\n${res.lessons_learned}`,
      })
    }
  } catch (err) {
    console.error(err)
  } finally {
    savingLesson.value = false
  }
}

async function refinePrompt() {
  const ctx = chatStore.promptReviewContext
  if (!ctx || chatStore.messages.length < 2) return
  refining.value = true
  const refined = await researchStore.refinePrompt(
    ctx.topicTitle,
    ctx.prompt,
    chatStore.messages.map(m => ({ role: m.role, content: m.content })),
  )
  refining.value = false
  if (refined) {
    chatStore.refinedPrompt = refined
    chatStore.messages.push({
      role: 'assistant',
      content: 'Prompt wurde aktualisiert und in den Editor übernommen.',
    })
  }
}

// Track current view
watch(() => route.name, (name) => {
  if (name && typeof name === 'string') {
    chatStore.setView(name)
  }
}, { immediate: true })

watch(() => pricesStore.selectedTicker, (ticker) => {
  chatStore.setTicker(ticker || null)
}, { immediate: true })

// Rating labels
const ratingLabels: Record<string, string> = {
  GREEN: 'GRÜN',
  GREEN_FRAGILE: 'GRÜN (fragil)',
  YELLOW: 'GELB',
  YELLOW_BEARISH: 'GELB (bärisch)',
  RED: 'ROT',
  RED_CAPITULATION: 'ROT (Kapitulation)',
}

const actionLabels: Record<string, string> = {
  hold: 'Halten',
  buy: 'Kaufen',
  partial_sell: 'Teilverkauf',
  hedge: 'Absichern',
  wait: 'Abwarten',
}

// Dynamic welcome text per view
const welcomeTitle = computed(() => {
  const view = chatStore.currentView
  if (view === 'kurse') return `Frag mich zu ${pricesStore.selectedTicker || 'Kursen'}!`
  if (view === 'thesen') return 'Frag mich zu deinen Thesen!'
  if (view === 'ampel') return 'Frag mich zur Ampel-Analyse!'
  if (view === 'research') return 'Frag mich zu deinem Research!'
  return 'Hallo! Ich bin dein Trading-Tutor.'
})

const welcomeText = computed(() => {
  const view = chatStore.currentView
  if (view === 'kurse') {
    return 'Ich erkläre dir den Kursverlauf, technische Indikatoren und was die Zahlen bedeuten.'
  }
  if (view === 'thesen') {
    return 'Ich erkläre dir die offenen Thesen, Katalysatoren und Szenarien.'
  }
  if (view === 'ampel') {
    return 'Ich erkläre dir die Signale, Marktdaten und was sie für dein Portfolio bedeuten.'
  }
  if (view === 'research') {
    return 'Ich erkläre dir die Research-Ergebnisse und was sie für dein Portfolio bedeuten.'
  }
  return 'Frag mich alles zur aktuellen Analyse — ich erkläre Begriffe, Zusammenhänge und was die Daten für dich bedeuten.'
})

// Dynamic suggestions based on current view + real data
const suggestions = computed(() => {
  const view = chatStore.currentView
  const analysis = ampelStore.latestAnalysis

  if (view === 'ampel' && analysis) {
    const rating = ratingLabels[analysis.rating?.overall] || analysis.rating?.overall
    const vix = analysis.market?.vix?.value
    const firstEvent = analysis.sentiment_events?.[0]
    const items: string[] = []

    items.push(`Warum ist die Ampel ${rating}?`)
    if (vix) items.push(`Erkläre mir den VIX bei ${vix.toFixed(1)}`)
    if (firstEvent) {
      const headline = firstEvent.headline.length > 50
        ? firstEvent.headline.slice(0, 47) + '...'
        : firstEvent.headline
      items.push(`${headline} — was bedeutet das?`)
    }
    if (analysis.market?.golden_cross) {
      items.push('Was bedeutet das Golden Cross?')
    } else {
      items.push('Warum gibt es kein Golden Cross?')
    }
    return items
  }

  if (view === 'kurse') {
    const ticker = pricesStore.selectedTicker || 'IWDA.AS'
    const latest = pricesStore.prices?.[pricesStore.prices.length - 1]
    const items: string[] = []

    if (latest?.close) {
      items.push(`Wie steht ${ticker} bei ${latest.close.toFixed(2)}€?`)
    } else {
      items.push(`Wie steht ${ticker} gerade?`)
    }
    items.push(`Was bedeutet der SMA 50 für ${ticker}?`)
    if (latest?.close && latest?.sma50) {
      const above = latest.close > latest.sma50
      items.push(above
        ? `${ticker} ist über dem SMA 50 — ist das gut?`
        : `${ticker} ist unter dem SMA 50 — muss ich mir Sorgen machen?`
      )
    } else {
      items.push(`Ist ${ticker} gerade über- oder unterbewertet?`)
    }
    items.push('Erkläre mir den Kursverlauf')
    return items
  }

  if (view === 'thesen') {
    const theses = ampelStore.theses
    const items: string[] = []

    if (theses.length > 0) {
      const first = theses[0]
      const stmt = first.statement.length > 60
        ? first.statement.slice(0, 57) + '...'
        : first.statement
      items.push(`Erkläre mir: ${stmt}`)
      if (first.catalyst) {
        items.push(`Was passiert wenn "${first.catalyst}" eintritt?`)
      }
    }
    items.push('Welche Risiken sehe ich bei meinen Thesen?')
    if (theses.length > 1) {
      items.push('Wie hängen meine Thesen zusammen?')
    } else {
      items.push('Was ist eine Investment-These?')
    }
    return items.slice(0, 4)
  }

  if (view === 'research') {
    const topics = researchStore.topics
    const items: string[] = []

    if (researchStore.selectedTopic) {
      const t = researchStore.selectedTopic
      const title = t.title.length > 40 ? t.title.slice(0, 37) + '...' : t.title
      items.push(`Erkläre mir: ${title}`)
      if (t.relevance_summary) {
        items.push(`Was bedeutet "${t.relevance_summary.slice(0, 50)}..." für mein Portfolio?`)
      }
    }
    if (topics.length > 1) {
      items.push('Wie hängen meine Research-Themen zusammen?')
    }
    items.push('Welche Risiken ergeben sich aus meinem Research?')
    return items.slice(0, 4)
  }

  // Dashboard (default)
  if (analysis) {
    const rating = ratingLabels[analysis.rating?.overall] || 'die Ampel'
    const action = actionLabels[analysis.recommendation?.action] || ''
    return [
      `Was bedeutet ${rating} für mich?`,
      action ? `Erkläre mir die Empfehlung: ${action}` : 'Was ist die aktuelle Empfehlung?',
      'Wie steht mein ETF gerade?',
      'Worauf sollte ich als nächstes achten?',
    ]
  }

  return [
    'Was bedeutet die Ampel-Bewertung?',
    'Erkläre mir den VIX',
    'Was ist ein Golden Cross?',
    'Wie sicher ist mein ETF gerade?',
  ]
})

function send() {
  if (!inputText.value.trim() || chatStore.isLoading) return
  chatStore.sendMessage(inputText.value)
  inputText.value = ''
  if (inputEl.value) {
    inputEl.value.style.height = 'auto'
  }
}

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, scrollToBottom)
watch(() => chatStore.isLoading, scrollToBottom)
// Scroll during streaming as content builds up
watch(
  () => lastMessage.value?.content,
  () => { if (chatStore.isLoading) scrollToBottom() },
)
watch(() => chatStore.isOpen, (open) => {
  if (open) {
    nextTick(() => inputEl.value?.focus())
  }
})
</script>

<style lang="scss">
.chat-drawer {
  width: 420px !important;

  @media screen and (max-width: 480px) {
    width: 100% !important;
  }

  .p-drawer-content {
    padding: 0 !important;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .p-drawer-footer {
    padding: 0.75rem 1rem !important;
    border-top: 1px solid var(--p-surface-border);
  }
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 1rem;
  color: var(--p-text-color);
  width: 100%;

  i.pi-comments {
    color: var(--p-primary-500);
  }

  .p-button {
    margin-left: auto;
  }
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

// Review Banner
.review-banner {
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border-radius: 10px;
  background: rgba(var(--p-primary-500-rgb, 99, 102, 241), 0.08);
  border: 1px solid rgba(var(--p-primary-500-rgb, 99, 102, 241), 0.2);
  flex-shrink: 0;

  &.review-banner-thesis {
    background: rgba(245, 158, 11, 0.08);
    border-color: rgba(245, 158, 11, 0.2);

    .banner-header { color: #f59e0b; }
  }

  &.review-banner-lesson {
    background: rgba(16, 185, 129, 0.08);
    border-color: rgba(16, 185, 129, 0.2);

    .banner-header { color: #059669; :root.dark & { color: #6ee7b7; } }
  }
}

.banner-header {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-primary-500);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.banner-topic {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--p-text-color);
  margin: 0.375rem 0 0 0;
}

.refine-btn {
  margin-top: 0.5rem;
  width: 100%;
}

// Welcome
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2rem 1rem;
  gap: 0.75rem;
}

.welcome-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  background: var(--p-primary-100);
  display: flex;
  align-items: center;
  justify-content: center;

  :root.dark & {
    background: rgba(var(--p-primary-500-rgb, 99, 102, 241), 0.15);
  }

  i {
    font-size: 1.25rem;
    color: var(--p-primary-500);
  }
}

.welcome-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin: 0;
}

.welcome-text {
  font-size: 0.8125rem;
  color: var(--p-text-color-secondary);
  line-height: 1.5;
  margin: 0;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 0.5rem;
}

.suggestion-chip {
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  border-radius: 20px;
  padding: 0.375rem 0.875rem;
  font-size: 0.75rem;
  color: var(--p-text-color);
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
  text-align: left;

  &:hover {
    border-color: var(--p-primary-500);
    color: var(--p-primary-500);
    background: var(--p-surface-card);
  }
}

// Messages
.message {
  display: flex;
  max-width: 85%;

  &.message-user {
    align-self: flex-end;

    .message-bubble {
      background: var(--p-primary-500);
      color: white;
      border-radius: 16px 16px 4px 16px;
    }
  }

  &.message-assistant {
    align-self: flex-start;

    .message-bubble {
      background: var(--p-surface-ground);
      color: var(--p-text-color);
      border-radius: 16px 16px 16px 4px;
      border: 1px solid var(--p-surface-border);
    }
  }
}

.message-bubble {
  padding: 0.625rem 0.875rem;
  font-size: 0.8125rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;

  &.streaming::after {
    content: '▊';
    display: inline;
    animation: blink-cursor 0.8s step-end infinite;
    color: var(--p-primary-500);
    font-weight: 200;
  }
}

@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

// Typing indicator
.typing-bubble {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--p-text-color-secondary);
  animation: typing 1.4s ease-in-out infinite;

  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

// Error
.chat-error {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  color: #ef4444;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
}

// Input
.chat-input-area {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
}

.chat-input {
  flex: 1;
  resize: none;
  border: 1px solid var(--p-surface-border);
  border-radius: 12px;
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  font-family: inherit;
  line-height: 1.5;
  color: var(--p-text-color);
  background: var(--p-surface-ground);
  outline: none;
  max-height: 120px;
  transition: border-color 0.15s;

  &:focus {
    border-color: var(--p-primary-500);
  }

  &::placeholder {
    color: var(--p-text-color-secondary);
  }
}
</style>
