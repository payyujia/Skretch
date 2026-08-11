<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { MousePointer2, StickyNote, Pen, Trash2, Undo2, Redo2, Sparkles } from 'lucide-vue-next'
import { useToolStore } from '../stores/tool'
import { useBoardStore } from '../stores/board'
import { NODE_TYPES } from '../utils/nodeTypes'

const tool = useToolStore()
const board = useBoardStore()
const openFlyout = ref(null) // null | 'nodes'
const rootEl = ref(null)

function toggleFlyout(name) {
  openFlyout.value = openFlyout.value === name ? null : name
}

function chooseSelect() {
  tool.setSelect()
  openFlyout.value = null
}

function chooseNodeType(type) {
  tool.pickNodeType(type)
  openFlyout.value = null
}

function onDocClick(event) {
  if (rootEl.value && !rootEl.value.contains(event.target)) openFlyout.value = null
}

onMounted(() => document.addEventListener('mousedown', onDocClick))
onUnmounted(() => document.removeEventListener('mousedown', onDocClick))
</script>

<template>
  <div class="toolbar-root" ref="rootEl">
    <transition name="pop">
      <div v-if="openFlyout === 'nodes'" class="flyout">
        <button v-for="nt in NODE_TYPES" :key="nt.type" class="flyout-item" @click="chooseNodeType(nt.type)">
          <component :is="nt.icon" :size="16" />
          <span>{{ nt.label }}</span>
        </button>
      </div>
    </transition>

    <div class="toolbar">
      <button class="tool-btn" :class="{ active: tool.active === 'select' }" title="Select (V)" @click="chooseSelect">
        <MousePointer2 :size="18" />
      </button>
      <button
        class="tool-btn"
        :class="{ active: tool.active === 'nodes' }"
        title="Nodes"
        @click="toggleFlyout('nodes')"
      >
        <StickyNote :size="18" />
      </button>
      <button class="tool-btn" title="Draw">
        <Pen :size="18" />
      </button>

      <span class="divider" />

      <button class="tool-btn" title="Undo (⌘Z)" :disabled="!board.canUndo" @click="board.undo()">
        <Undo2 :size="18" />
      </button>
      <button class="tool-btn" title="Redo (⌘⇧Z)" :disabled="!board.canRedo" @click="board.redo()">
        <Redo2 :size="18" />
      </button>

      <span class="divider" />

      <button class="tool-btn" :class="{ active: tool.chatOpen }" title="Ask the agent" @click="tool.toggleChat()">
        <Sparkles :size="18" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.toolbar-root {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  z-index: 20;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 6px;
  box-shadow: var(--shadow-md);
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 9px;
  color: var(--ink);
}

.tool-btn:hover:not(:disabled) {
  background: var(--canvas-bg);
}

.tool-btn.active {
  background: var(--user-accent);
  color: #fff;
}

.tool-btn:disabled {
  color: var(--border);
  cursor: not-allowed;
}

.divider {
  width: 1px;
  height: 22px;
  background: var(--border);
  margin: 0 4px;
}

.flyout {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 6px;
  box-shadow: var(--shadow-md);
  min-width: 168px;
}

.flyout-item {
  display: flex;
  align-items: center;
  gap: 9px;
  border: none;
  background: transparent;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--ink);
  text-align: left;
}

.flyout-item:hover {
  background: var(--canvas-bg);
}

.flyout-item.active {
  background: var(--user-accent-tint);
  color: var(--user-accent);
}

.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>