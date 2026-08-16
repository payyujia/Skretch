<script setup>
import { nextTick, ref, watch } from 'vue'
import { X, Paperclip, FileText, Loader2 } from 'lucide-vue-next'
import { useBoardStore } from '../stores/board'
import { useToolStore } from '../stores/tool'
import { useAgentChat } from '../composables/useAgentChat'
import { uploadDocument, deleteDocument } from '../api/client'

const props = defineProps({
  boardId: { type: [Number, String], required: true },
})

const board = useBoardStore()
const tool = useToolStore()
const { messages, connected, sending, send } = useAgentChat(props.boardId)
const draft = ref('')
const inputRef = ref(null)
const listRef = ref(null)
const contextNode = ref(null)

// Document attachment state
const fileInputRef = ref(null)
const attachedDocs = ref([]) // [{ name: string, uploading: boolean, error: string|null }]

watch(
  messages,
  () => nextTick(() => { if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight }),
  { deep: true }
)

function submit() {
  if (!draft.value.trim() || sending.value) return
  const docNames = attachedDocs.value
    .filter(d => !d.uploading && !d.error)
    .map(d => d.name)
  send(draft.value, contextNode.value, docNames)
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

// ── Document handling ─────────────────────────────────────────────────────────

function openFilePicker() {
  fileInputRef.value?.click()
}

async function onFileSelected(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  for (const file of files) {
    const entry = { name: file.name, uploading: true, error: null }
    attachedDocs.value.push(entry)
    try {
      await uploadDocument(file, props.boardId)
      entry.uploading = false
    } catch (err) {
      entry.uploading = false
      entry.error = err.message || 'Upload failed'
    }
  }
}

function removeDoc(name) {
  attachedDocs.value = attachedDocs.value.filter(d => d.name !== name)
  deleteDocument(name, props.boardId).catch(() => {/* best-effort */})
}
defineExpose({ focusWithContext })
</script>

<template>
  <transition name="pop">
    <aside v-if="tool.chatOpen" class="chat-popover">

      <!-- ── Header: agent-accent tinted strip ── -->
      <header class="chat-header">
        <div class="header-left">
          <span class="header-dot" :class="{ connected }" />
          <span class="title">Agent</span>
        </div>
        <span class="status-label">{{ connected ? 'online' : 'connecting…' }}</span>
        <button type="button" class="close-btn" @click="tool.chatOpen = false" title="Close">
          <X :size="14" />
        </button>
      </header>

      <!-- ── Message list ── -->
      <div class="chat-messages" ref="listRef">
        <p v-if="!messages.length" class="empty-hint">
          Ask the agent to brainstorm, research, or tidy up — it places ideas straight on the board.
          Upload project docs below to let it reference your specs.
        </p>
        <div v-for="(m, i) in messages" :key="i" class="message" :class="m.role">
          {{ m.content }}
        </div>
      </div>

      <!-- ── Input area ── -->
      <div class="chat-input">
        <!-- Context chip (selected node) -->
        <div v-if="contextNode" class="context-chip">
          <span>re: {{ contextNode.content || 'this idea' }}</span>
          <button type="button" @click="contextNode = null">×</button>
        </div>

        <!-- Document chips -->
        <div v-if="attachedDocs.length" class="doc-chips">
          <div
            v-for="doc in attachedDocs"
            :key="doc.name"
            class="doc-chip"
            :class="{ uploading: doc.uploading, error: doc.error }"
          >
            <Loader2 v-if="doc.uploading" :size="12" class="spin" />
            <FileText v-else :size="12" />
            <span class="doc-chip-name" :title="doc.name">{{ doc.name }}</span>
            <button v-if="!doc.uploading" type="button" class="doc-chip-remove" @click="removeDoc(doc.name)">×</button>
          </div>
        </div>

        <div class="input-row">
          <!-- Hidden file input -->
          <input
            ref="fileInputRef"
            type="file"
            accept=".pdf,.docx,.doc,.txt"
            multiple
            style="display:none"
            @change="onFileSelected"
          />

          <!-- Attach button -->
          <button
            type="button"
            class="attach-btn"
            title="Attach project document (PDF, DOCX, TXT)"
            @click="openFilePicker"
          >
            <Paperclip :size="15" />
          </button>

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
/* ── Shell ── */
.chat-popover {
  position: absolute;
  bottom: 84px;
  right: 20px;
  width: 340px;
  height: 480px;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  overflow: hidden;
  z-index: 25;
}

/* ── Header: tinted agent strip ── */
.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--agent-accent-tint);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 1;
}

.header-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
  flex-shrink: 0;
  transition: background 0.3s ease;
}
.header-dot.connected {
  background: var(--success);
  box-shadow: 0 0 0 2px var(--success-tint);
}

.title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 13px;
  color: var(--agent-accent);
  letter-spacing: 0.04em;
}

.status-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.04em;
}

.close-btn {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
  cursor: pointer;
  flex-shrink: 0;
}
.close-btn:hover {
  background: var(--border);
  color: var(--ink);
}

/* ── Messages ── */
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
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.55;
}

.message {
  max-width: 88%;
  padding: 9px 12px;
  border-radius: var(--radius);
  font-family: var(--font-body);
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
  border: 1px solid var(--border);
}

.message.system {
  align-self: center;
  background: transparent;
  color: var(--danger);
  font-family: var(--font-mono);
  font-size: 12px;
}

/* ── Input area ── */
.chat-input {
  border-top: 1px solid var(--border);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.context-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--user-accent-tint);
  color: var(--user-accent);
  font-family: var(--font-body);
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
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
  cursor: pointer;
}

/* Doc chips row */
.doc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.doc-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 3px 8px 3px 6px;
  font-family: var(--font-body);
  font-size: 11.5px;
  color: var(--ink);
  max-width: 160px;
}

.doc-chip.uploading {
  opacity: 0.65;
  border-style: dashed;
}

.doc-chip.error {
  border-color: var(--danger);
  color: var(--danger);
}

.doc-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100px;
}

.doc-chip-remove {
  border: none;
  background: none;
  color: var(--muted);
  font-size: 14px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  flex-shrink: 0;
}

.doc-chip-remove:hover {
  color: var(--danger);
}

/* Spinning loader icon */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.attach-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  border-radius: var(--radius);
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.15s, border-color 0.15s;
}

.attach-btn:hover {
  color: var(--ink);
  border-color: var(--ink);
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
  background: var(--surface);
  color: var(--ink);
  outline: none;
  transition: border-color 0.15s;
}

textarea:focus {
  border-color: var(--agent-accent);
}

.send-btn {
  border: none;
  background: var(--ink);
  color: var(--surface);
  border-radius: var(--radius);
  padding: 9px 14px;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.88;
  transform: translateY(-1px);
}

.send-btn:disabled {
  background: var(--border);
  color: var(--muted);
  cursor: not-allowed;
}

/* ── Transition ── */
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
