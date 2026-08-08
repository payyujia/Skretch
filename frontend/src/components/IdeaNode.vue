<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useBoardStore } from '../stores/board'

const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, required: true },
})

const board = useBoardStore()
const textareaRef = ref(null)

const isEditing = computed(() => board.editingNodeId === props.id)
const isSelected = computed(() => board.selectedNodeId === props.id)
const isAgent = computed(() => props.data.createdBy === 'agent')

const content = computed({
  get: () => props.data.content,
  set: (value) => board.setContentLocal(props.id, value),
})

watch(isEditing, async (editing) => {
  if (!editing) return
  await nextTick()
  textareaRef.value?.focus()
  textareaRef.value?.select()
  autoGrow({ target: textareaRef.value })
})

function autoGrow(event) {
  const el = event.target
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

async function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    await board.commitNode(props.id, content.value)
    board.spawnFrom(props.id, 'down')
  } else if (event.key === 'Enter' && event.shiftKey) {
    event.preventDefault()
    await board.commitNode(props.id, content.value)
    board.spawnFrom(props.id, 'side')
  } else if (event.key === 'Escape') {
    event.preventDefault()
    await board.commitNode(props.id, content.value)
    board.stopEditing()
  } else if (event.key === 'Backspace' && !content.value) {
    event.preventDefault()
    board.deleteNode(props.id)
  }
}

async function onBlur() {
  if (!isEditing.value) return
  await board.commitNode(props.id, content.value)
  board.stopEditing()
}

function onDoubleClick() {
  board.startEditing(props.id)
}
</script>

<template>
  <div
    class="idea-node"
    :class="{ agent: isAgent, selected: isSelected, editing: isEditing, thinking: data.thinking, 'just-placed': data.justPlaced }"
    @dblclick.stop="onDoubleClick"
  >
    <Handle type="target" :position="Position.Left" class="handle" />
    <Handle type="source" :position="Position.Right" class="handle" />

    <span v-if="isAgent" class="badge">AI</span>
    <button v-if="!isEditing" type="button" class="remove-btn" @click.stop="board.deleteNode(id)">×</button>

    <textarea
      v-if="isEditing"
      ref="textareaRef"
      v-model="content"
      class="node-text"
      rows="1"
      placeholder="Type an idea…"
      @input="autoGrow"
      @keydown="onKeydown"
      @blur="onBlur"
      @pointerdown.stop
    />
    <p v-else class="node-text" :class="{ empty: !data.content }">
      <span v-if="data.thinking" class="typing-dots"><i /><i /><i /></span>
      <template v-else>{{ data.content || 'Empty idea' }}</template>
    </p>
  </div>
</template>

<style scoped>
.idea-node {
  position: relative;
  min-width: 180px;
  max-width: 260px;
  padding: 12px 14px;
  background: var(--surface);
  border: 1.5px solid var(--border-strong);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  font-size: 14px;
  line-height: 1.4;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.idea-node.selected {
  border-color: var(--user-accent);
  box-shadow: 0 0 0 3px var(--user-accent-tint);
}

.idea-node.agent {
  border-color: var(--agent-accent);
  background: var(--agent-accent-tint);
}

.idea-node.agent.selected {
  box-shadow: 0 0 0 3px rgba(122, 79, 224, 0.18);
}

.idea-node.thinking {
  border-style: dashed;
  background: var(--surface);
  animation: pulse 1.3s ease-in-out infinite;
}

.idea-node.just-placed {
  animation: placeGlow 0.9s ease-out;
}

.idea-node.editing {
  box-shadow: var(--shadow-md);
}

.node-text {
  margin: 0;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
}

.node-text.empty {
  color: var(--muted);
  font-style: italic;
}

textarea.node-text {
  width: 100%;
  min-height: 22px;
  resize: none;
  border: none;
  background: transparent;
  padding: 0;
  outline: none;
  overflow: hidden;
  font-size: 14px;
  font-family: var(--font-body);
}

.badge {
  position: absolute;
  top: -9px;
  left: 10px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: #fff;
  background: var(--agent-accent);
  padding: 2px 6px;
  border-radius: 5px;
}

.remove-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  font-size: 13px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.idea-node:hover .remove-btn {
  opacity: 1;
}

.remove-btn:hover {
  border-color: var(--danger);
  color: var(--danger);
}

.typing-dots {
  display: inline-flex;
  gap: 3px;
  align-items: center;
  height: 14px;
}

.typing-dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--agent-accent);
  animation: bounce 1.1s infinite ease-in-out;
}

.typing-dots i:nth-child(2) {
  animation-delay: 0.15s;
}
.typing-dots i:nth-child(3) {
  animation-delay: 0.3s;
}

:deep(.handle) {
  width: 8px;
  height: 8px;
  background: var(--surface);
  border: 1.5px solid var(--muted);
  opacity: 0;
  transition: opacity 0.15s ease;
}

.idea-node:hover :deep(.handle) {
  opacity: 1;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

@keyframes placeGlow {
  0% { box-shadow: 0 0 0 6px rgba(122, 79, 224, 0.28); }
  100% { box-shadow: var(--shadow-sm); }
}

@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
  40% { transform: translateY(-3px); opacity: 1; }
}
</style>
