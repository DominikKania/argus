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
      <!-- Welcome -->
      <div v-if="!chatStore.messages.length && !chatStore.isLoading" class="welcome">
        <div class="welcome-icon">
          <i class="pi pi-sparkles" />
        </div>
        <h3 class="welcome-title">Hallo! Ich bin dein Trading-Tutor.</h3>
        <p class="welcome-text">
          Frag mich alles zur aktuellen Analyse — ich erkläre Begriffe,
          Zusammenhänge und was die Daten für dich bedeuten.
        </p>
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
        <div
          v-for="(msg, i) in chatStore.messages"
          :key="i"
          class="message"
          :class="`message-${msg.role}`"
        >
          <div class="message-bubble">{{ msg.content }}</div>
        </div>

        <!-- Typing indicator -->
        <div v-if="chatStore.isLoading" class="message message-assistant">
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
import { ref, watch, nextTick } from 'vue'
import Drawer from 'primevue/drawer'
import Button from 'primevue/button'
import { useChatStore } from '@/stores/chatStore'

const chatStore = useChatStore()
const inputText = ref('')
const chatBody = ref<HTMLElement>()
const inputEl = ref<HTMLTextAreaElement>()

const suggestions = [
  'Was bedeutet die Ampel-Bewertung?',
  'Erkläre mir den VIX',
  'Was ist ein Golden Cross?',
  'Wie sicher ist mein ETF gerade?',
]

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
