<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import StickyNoteNode from './StickyNoteNode.vue'
import Toolbar from './Toolbar.vue'
import ChatPopover from './ChatPopover.vue'
import { useBoardStore } from '../stores/board'
import { useToolStore } from '../stores/tool'
import { defaultSpawnPosition } from '../utils/layout'
// import { uploadImage } from '../api/client'
// import { validateImageFile } from '../utils/image'

const board = useBoardStore()
const tool = useToolStore()
const { screenToFlowCoordinate } = useVueFlow()
const hoveredNodeId = ref(null)
const chatRef = ref(null)

const flowNodes = computed(() =>
  board.nodes.map((n) => ({
    id: n.id,
    type: n.type,
    position: { x: n.x, y: n.y },
    data: n,
    draggable: !n.thinking && tool.active === 'select',
    connectable: Boolean(n.serverId),
  }))
)

function onNodeDragStop({ node }) {
  board.checkpoint()
  board.moveNode(node.id, node.position.x, node.position.y)
}

function onNodeClick({ node }) {
  if (tool.active === 'select') board.select(node.id)
}

function onNodeDoubleClick({ node }) {
  if (tool.active === 'select') board.startEditing(node.id)
}

function onNodeMouseEnter({ node }) {
  hoveredNodeId.value = node.id
}

function onNodeMouseLeave() {
  hoveredNodeId.value = null
}

function onPaneClick(event) {
  if (tool.active === 'nodes' && tool.pendingNodeType) {
    const pos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    board.createNodeOfType(tool.pendingNodeType, pos.x, pos.y)
    return
  }
  if (tool.active === 'select') board.deselect()
}

function onPaneDoubleClick(event) {
  if (tool.active !== 'select') return
  if (event.target.closest('.vue-flow__node')) return
  board.checkpoint()
  const pos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  board.spawnNode(pos)
}

async function onPaste(event) {
  const item = [...(event.clipboardData?.items || [])].find((i) => i.type.startsWith('image/'))
  if (!item) return
  const file = item.getAsFile()
  if (!file || validateImageFile(file)) return // silently ignore; explicit upload UI shows errors

  const pos = defaultSpawnPosition()
  const id = await board.createNodeOfType('image', pos.x, pos.y)
  try {
    const { url } = await uploadImage(file)
    board.checkpoint()
    await board.updateNodeData(id, { image: url, embedding: null })
  } catch {
    // leave the node as an empty placeholder — the click-to-upload UI lets them retry
  }
}

function handleKeydown(event) {
  const tag = document.activeElement?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return // node & chat inputs own their own keys

  const meta = event.metaKey || event.ctrlKey
  if (meta && event.key.toLowerCase() === 'z' && event.shiftKey) {
    event.preventDefault()
    board.redo()
  } else if (meta && event.key.toLowerCase() === 'z') {
    event.preventDefault()
    board.undo()
  } else if (event.key.toLowerCase() === 'v' && !meta) {
    tool.setSelect()
  } else if (event.key === 'Enter' && board.selectedNodeId && !board.editingNodeId) {
    event.preventDefault()
    board.checkpoint()
    board.spawnFrom(board.selectedNodeId, event.shiftKey ? 'side' : 'down')
  } else if (event.key === 'Enter') {
    event.preventDefault()
    board.checkpoint()
    board.spawnNode(defaultSpawnPosition())
  } else if ((event.key === 'Delete' || event.key === 'Backspace') && board.selectedNodeId && !board.editingNodeId) {
    event.preventDefault()
    board.checkpoint()
    board.deleteNode(board.selectedNodeId)
  } else if (meta && event.key.toLowerCase() === 'j' && board.selectedNodeId) {
    event.preventDefault()
    chatRef.value?.focusWithContext()
  } else if (event.key === 'Escape') {
    if (tool.active !== 'select') tool.setSelect()
    else if (board.selectedNodeId) board.deselect()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('paste', onPaste)
  board.fetchBoard()
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('paste', onPaste)
})
</script>

<template>
  <div class="canvas-wrapper" @dblclick="onPaneDoubleClick">
    <VueFlow
      :nodes="flowNodes"
      :default-viewport="{ zoom: 1 }"
      :min-zoom="0.3"
      :max-zoom="1.75"
      :nodes-connectable="true"
      @node-drag-stop="onNodeDragStop"
      @node-click="onNodeClick"
      @node-double-click="onNodeDoubleClick"
      @node-mouse-enter="onNodeMouseEnter"
      @node-mouse-leave="onNodeMouseLeave"
      @pane-click="onPaneClick"
    >
      <template #node-sticky="props"><StickyNoteNode v-bind="props" /></template>
      <template #node-image="props"><ImageNode v-bind="props" /></template>
      <Background variant="dots" :gap="28" :size="1.6" color="var(--canvas-dot)" />
      <Controls :show-interactive="false" position="bottom-left" />
    </VueFlow>

    <transition name="fade">
      <div class="hint-bar" v-if="!board.nodes.length">
        <span><kbd>Enter</kbd> new idea</span>
        <span class="dot">·</span>
        <span><kbd>⇧Enter</kbd> new branch</span>
        <span class="dot">·</span>
        <span>pick a tool below to draw or add other node types</span>
      </div>
    </transition>

    <Toolbar />
    <ChatPopover ref="chatRef" />
  </div>
</template>

<style scoped>
.canvas-wrapper {
  position: relative;
  min-width: 0;
  height: 100%;
  background: var(--canvas-bg);
}

.canvas-wrapper :deep(.vue-flow) {
  background: var(--canvas-bg);
}

.canvas-wrapper :deep(.vue-flow__controls) {
  box-shadow: var(--shadow-sm);
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
}

.canvas-wrapper :deep(.vue-flow__controls-button) {
  background: var(--surface);
  border: none;
  border-bottom: 1px solid var(--border);
  fill: var(--ink);
}

.hint-bar {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 999px;
  box-shadow: var(--shadow-sm);
  font-size: 12.5px;
  color: var(--muted);
  white-space: nowrap;
  z-index: 15;
}

.hint-bar kbd {
  font-family: var(--font-mono);
  background: var(--canvas-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 5px;
  color: var(--ink);
  font-size: 11.5px;
}

.hint-bar .dot {
  opacity: 0.5;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
