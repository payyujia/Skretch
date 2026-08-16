<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Trash2, Link, FileText, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useBoardStore } from '../stores/board'
import { colorOptions } from '../utils/nodeTypes'
const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, required: true },
})

const board = useBoardStore()
const textareaRef = ref(null)

const reactionOptions = ['👍', '👎', '🔥', '🤡', '❓']

const isEditing = computed(() => board.editingNodeId === props.id)
const isSelected = computed(() => board.selectedNodeId === props.id)
const isAgent = computed(() => props.data.createdBy === 'agent')

const content = computed({
  get: () => props.data.content,
  set: (value) => board.setContentLocal(props.id, value),
})

const noteColor = computed(() => {
  const chosen = props.data.data?.color
  return colorOptions.find((option) => option.name === chosen)?.hex ?? colorOptions[0].hex
})

const currentColorName = computed(() => props.data.data?.color ?? colorOptions[0].name)
const reactions = computed(() => props.data.data?.reactions || {})
const reactionEntries = computed(() => Object.entries(reactions.value).filter(([, count]) => count > 0))
const rotation = computed(() => props.data.data?.rotation ?? 0)

const citations = computed(() => props.data.data?.citations || [])
const docSource = computed(() => props.data.data?.source || null)
const citationsOpen = ref(false)

function selectColor(color) {
  board.checkpoint()
  board.updateNodeData(props.id, { color })
}

function addReaction(emoji) {
  const current = reactions.value[emoji] || 0
  board.checkpoint()
  board.updateNodeData(props.id, {
    reactions: { ...reactions.value, [emoji]: current + 1 },
  })
}

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
    board.checkpoint()
    await board.commitNode(props.id, content.value)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    board.checkpoint()
    await board.commitNode(props.id, content.value)
    board.stopEditing()
  } else if (event.key === 'Backspace' && !content.value) {
    event.preventDefault()
    board.checkpoint()
    board.deleteNode(props.id)
  }
}

async function onBlur() {
  if (!isEditing.value) return
  board.checkpoint()
  await board.commitNode(props.id, content.value)
  board.stopEditing()
}

function onDoubleClick() {
  board.startEditing(props.id)
}
</script>

<template>
  <div
    class="board-node sticky-note"
    :class="{ agent: isAgent, selected: isSelected, editing: isEditing, thinking: data.thinking, 'just-placed': data.justPlaced }"
    :style="{ backgroundColor:`color-mix(in oklab, ${noteColor}, white 50%)`,transform: `rotate(${rotation}deg)`, borderTopColor: noteColor}"
    @dblclick.stop="onDoubleClick"
  >
    <span v-if="isAgent" class="node-badge">AI</span>
    <div class="header">
      <span>◍ @{{ data.createdBy}}</span>
      <div class="color-picker">
        <button
          v-for="option in colorOptions"
          :key="option.name"
          type="button"
          class="color-swatch"
          :class="{ active: currentColorName === option.name }"
          :style="{ backgroundColor: option.hex }"
          @click.stop="selectColor(option.name)"
          :aria-label="`Set note color to ${option.name}`"
        ></button>
      </div>
      <button type="button" class="node-remove" @click.stop="board.deleteNode(id)">
        <Trash2 :size="14 " />
      </button>
    </div>
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
      <span v-if="data.thinking" class="node-typing-dots"><i /><i /><i /></span>
      <template v-else>{{ data.content || 'Empty idea' }}</template>
    </p>
    <div class="footer">
      <div class="reactions">
        <template v-if="reactionEntries.length">
          <span v-for="([emoji, count]) in reactionEntries" :key="emoji" class="reaction-pill">
            {{ emoji }}{{ count }}
          </span>
        </template>
      </div>
      <div class="reaction-selector" :class="{ 'has-reactions': reactionEntries.length }">
          <button
            v-for="reaction in reactionOptions"
            :key="reaction"
            type="button"
            class="reaction-button"
            @click.stop="addReaction(reaction)"
          >{{ reaction }}</button>
        </div>
    </div>

    <!-- Source attribution (from RAG document) -->
    <div v-if="docSource" class="source-badge" @click.stop>
      <FileText :size="11" />
      <span>{{ docSource.doc_name }}</span>
    </div>

    <!-- Citations footer (from research grounding) -->
    <div v-if="citations.length" class="citations-footer" @click.stop>
      <button type="button" class="citations-toggle" @click="citationsOpen = !citationsOpen">
        <Link :size="11" />
        <span>{{ citations.length }} source{{ citations.length > 1 ? 's' : '' }}</span>
        <ChevronUp v-if="citationsOpen" :size="11" />
        <ChevronDown v-else :size="11" />
      </button>
      <div v-if="citationsOpen" class="citations-list">
        <a
          v-for="(cite, i) in citations"
          :key="i"
          :href="cite.url"
          target="_blank"
          rel="noopener noreferrer"
          class="citation-link"
          @click.stop
        >
          {{ cite.title || cite.url }}
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sticky-note {
  position: relative;
  width: 15rem;
  padding: var(--radius);
  border-top-width: 4px;
  display: flex;
  flex-direction: column;
  gap: .375rem;
  filter: brightness(1.1);
  transition: filter 0.2s ease, box-shadow 0.2s ease;
}
.sticky-note:hover { 
  filter:brightness(1);
}

.color-picker {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  border: 1px solid var(--border);
  background-color: var(--canvas-bg);
  border-radius:.5rem;
  opacity: 0;
  visibility: hidden;
  padding: 0 3px;
  height:1.2rem;
  box-shadow: var(--shadow-sm);
  transition: opacity 0.2s ease, visibility 0.2s ease;
}

.sticky-note:hover .color-picker {
  opacity: 1;
  visibility: visible;
}

.node-text {
  margin: 0;
  min-height: 4rem;
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
  min-height: 4rem;
  resize: none;
  border: none;
  background: transparent;
  padding: 0;
  outline: none;
  overflow: hidden;
  font-size: 14px;
  font-family: var(--font-body);
}

.footer {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: space-between;
  width: 100%;
}
.header {
  display: flex;
  color: var(--muted);
  gap: 0.75rem;
  place-items: center;
  justify-content: space-between;
}

.reactions {
  display: flex;
  gap: 0.25rem;
  min-height: 1rem;
  font-size: 0.75rem;
}

.reaction-pill {
  align-items: center;
  border-radius: 0.5rem;
  padding: 1px 4px;
  color:var(--muted);
  background:var(--canvas-bg);
  border: 1px solid var(--border);
  box-shadow: inset var(--shadow-sm);
}

.reaction-selector {
  display: flex;
  width:10rem;
  opacity: 0;
  visibility: hidden;
  box-shadow: inset var(--shadow-sm);
  justify-content: space-evenly;
  margin-left: auto;
  border:1px solid var(--border);
  border-radius: .5rem;
  background-color: var(--canvas-bg);
  transition: opacity 0.2s ease, visibility 0.2s ease;
}

.reaction-selector.has-reactions,
.sticky-note:hover .reaction-selector {
  opacity: 1;
  visibility: visible;
}

.reaction-button {
  background-color: transparent;
  border: none;
  line-height: 1rem;
  font-size: 0.75rem;
  transition: transform 0.15s ease, background 0.15s ease;
}

.reaction-button:hover {
  transform: translateY(-1px) scale(1.3);
}

/* ── Source / Citations ──────────────────────────────────────────────────── */
.source-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10.5px;
  color: var(--muted);
  margin-top: 4px;
  padding: 2px 6px;
  border: 1px solid var(--border);
  border-radius: 999px;
  width: fit-content;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  max-width: 100%;
}

.citations-footer {
  margin-top: 4px;
  font-size: 11px;
}

.citations-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 10.5px;
  color: var(--muted);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.citations-toggle:hover {
  color: var(--ink);
  border-color: var(--ink);
}

.citations-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 5px;
  padding: 6px 8px;
  background: var(--canvas-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.citation-link {
  font-size: 11px;
  color: var(--user-accent);
  text-decoration: none;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  display: block;
}

.citation-link:hover {
  text-decoration: underline;
}
</style>
