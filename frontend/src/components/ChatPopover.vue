<script setup>
import { nextTick, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { useBoardStore } from '../stores/board'
import { useToolStore } from '../stores/tool'
import { useAgentChat } from '../composables/useAgentChat'

const board = useBoardStore()
const tool = useToolStore()
const { messages, connected, sending, send } = useAgentChat()

const draft = ref('')
const inputRef = ref(null)
const listRef = ref(null)
const contextNode = ref(null)

watch(
  messages,
  () => nextTick(() => { if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight }),
  { deep: true }
)

function submit() {
  if (!draft.value.trim() || sending.value) return
  send(draft.value, contextNode.value)
  draft.value = ''
  contextNode.value = null
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function focusWithContext() {
  tool.chatOpen = true
  if (board.selectedNode) contextNode.value = board.selectedNode
  nextTick(() => inputRef.value?.focus())
}

defineExpose({ focusWithContext })
</script>

<template>
  <transition name="pop">
    <aside v-if="tool.chatOpen" class="chat-popover">
      <header class="chat-header">
        <span class="title">Agent</span>
        <span class="status" :class="{ connected }">{{ connected ? 'online' : 'connecting…' }}</span>
        <button type="button" class="close-btn" @click="tool.chatOpen = false"><X :size="16" /></button>
      </header>

      <div class="chat-messages" ref="listRef">
        <p v-if="!messages.length" class="empty-hint">
          Ask the agent to brainstorm, research, or tidy up — it places ideas straight on the board.
        </p>
        <div v-for="(m, i) in messages" :key="i" class="message" :class="m.role">
          {{ m.content }}
        </div>
      </div>

      <div class="chat-input">
        <div v-if="contextNode" class="context-chip">
          <span>re: {{ contextNode.content || 'this idea' }}</span>
          <button type="button" @click="contextNode = null">×</button>
        </div>
        <div class="input-row">
          <textarea
            ref="inputRef"
            v-model="draft"
            rows="1"
            placeholder="Brainstorm with the agent… (⌘J to reference a node)"
            @keydown="onKeydown"
          />
          <button type="button" class="send-btn" :disabled="!draft.trim() || sending" @click="submit">
            {{ sending ? '···' : 'Send' }}
          </button>
        </div>
      </div>
    </aside>
  </transition>
</template>

<style scoped>
.chat-popover {
  position: absolute;
  bottom: 84px;
  right: 20px;
  width: 340px;
  height: 460px;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-md);
  overflow: hidden;
  z-index: 25;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}

.title {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 14px;
}

.status {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.status::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted);
  margin-right: 5px;
}

.status.connected::before {
  background: #2fae60;
}

.close-btn {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--muted);
  display: flex;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty-hint {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.message {
  max-width: 88%;
  padding: 9px 12px;
  border-radius: 12px;
  font-size: 13.5px;
  line-height: 1.45;
  white-space: pre-wrap;
}

.message.user {
  align-self: flex-end;
  background: var(--user-accent);
  color: #fff;
  border-bottom-right-radius: 3px;
}

.message.assistant {
  align-self: flex-start;
  background: var(--agent-accent-tint);
  color: var(--ink);
  border-bottom-left-radius: 3px;
}

.message.system {
  align-self: center;
  background: transparent;
  color: var(--danger);
  font-family: var(--font-mono);
  font-size: 12px;
}

.chat-input {
  border-top: 1px solid var(--border);
  padding: 10px;
}

.context-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--user-accent-tint);
  color: var(--user-accent);
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  margin-bottom: 8px;
  max-width: 100%;
}

.context-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-chip button {
  border: none;
  background: none;
  color: inherit;
  font-size: 14px;
  line-height: 1;
  padding: 0;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

textarea {
  flex: 1;
  resize: none;
  max-height: 120px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 9px 11px;
  font-size: 13.5px;
  font-family: var(--font-body);
  outline: none;
}

textarea:focus {
  border-color: var(--user-accent);
}

.send-btn {
  border: none;
  background: var(--ink);
  color: #fff;
  border-radius: var(--radius);
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 500;
}

.send-btn:disabled {
  background: var(--border);
  color: var(--muted);
  cursor: not-allowed;
}

.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
