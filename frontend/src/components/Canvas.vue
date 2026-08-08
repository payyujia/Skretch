<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import IdeaNode from './IdeaNode.vue'
import { useBoardStore } from '../stores/board'
import { defaultSpawnPosition } from '../utils/layout'

const emit = defineEmits(['ask-ai'])

const board = useBoardStore()
const { screenToFlowCoordinate } = useVueFlow()
const hoveredNodeId = ref(null)

const flowNodes = computed(() =>
  board.nodes.map((n) => ({
    id: n.id,
    type: 'idea',
    position: { x: n.x, y: n.y },
    data: n,
    draggable: !n.thinking,
    connectable: Boolean(n.serverId),
  }))
)

const flowEdges = computed(() =>
  board.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    class: hoveredNodeId.value && (e.source === hoveredNodeId.value || e.target === hoveredNodeId.value)
      ? 'edge-active'
      : '',
  }))
)

function onNodeDragStop({ node }) {
  board.moveNode(node.id, node.position.x, node.position.y)
}

function onConnect(connection) {
  board.addEdge(connection.source, connection.target)
}

function onNodeClick({ node }) {
  board.select(node.id)
}

function onNodeDoubleClick({ node }) {
  board.startEditing(node.id)
}

function onNodeMouseEnter({ node }) {
  hoveredNodeId.value = node.id
}

function onNodeMouseLeave() {
  hoveredNodeId.value = null
}

function onPaneClick() {
  board.deselect()
}

function onPaneDoubleClick(event) {
  if (event.target.closest('.vue-flow__node')) return
  const pos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  board.spawnNode(pos)
}

function handleKeydown(event) {
  const tag = document.activeElement?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return // node & chat inputs own their own keys

  if (event.key === 'Enter' && board.selectedNodeId && !board.editingNodeId) {
    event.preventDefault()
    board.spawnFrom(board.selectedNodeId, event.shiftKey ? 'side' : 'down')
  } else if (event.key === 'Enter') {
    event.preventDefault()
    board.spawnNode(defaultSpawnPosition())
  } else if ((event.key === 'Delete' || event.key === 'Backspace') && board.selectedNodeId && !board.editingNodeId) {
    event.preventDefault()
    board.deleteNode(board.selectedNodeId)
  } else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'j' && board.selectedNodeId) {
    event.preventDefault()
    emit('ask-ai')
  } else if (event.key === 'Escape' && board.selectedNodeId) {
    board.deselect()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  board.fetchBoard()
})
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div class="canvas-wrapper" @dblclick="onPaneDoubleClick">
    <VueFlow
      :nodes="flowNodes"
      :edges="flowEdges"
      :default-viewport="{ zoom: 1 }"
      :min-zoom="0.3"
      :max-zoom="1.75"
      :nodes-connectable="true"
      @node-drag-stop="onNodeDragStop"
      @connect="onConnect"
      @node-click="onNodeClick"
      @node-double-click="onNodeDoubleClick"
      @node-mouse-enter="onNodeMouseEnter"
      @node-mouse-leave="onNodeMouseLeave"
      @pane-click="onPaneClick"
    >
      <template #node-idea="props">
        <IdeaNode v-bind="props" />
      </template>
      <Background variant="dots" :gap="28" :size="1.6" color="var(--canvas-dot)" />
      <Controls :show-interactive="false" position="bottom-left" />
    </VueFlow>

    <transition name="fade">
      <div class="hint-bar" v-if="!board.nodes.length">
        <span><kbd>Enter</kbd> new idea</span>
        <span class="dot">·</span>
        <span><kbd>⇧Enter</kbd> new branch</span>
        <span class="dot">·</span>
        <span>drag a node's edge to link ideas</span>
        <span class="dot">·</span>
        <span>double-click the canvas to drop a note</span>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.canvas-wrapper {
  position: relative;
  min-width: 0;
  background: var(--canvas-bg);
}

.canvas-wrapper :deep(.vue-flow) {
  background: var(--canvas-bg);
}

.canvas-wrapper :deep(.vue-flow__edge-path) {
  stroke: #c3c8d1;
  stroke-width: 1.6;
}

.canvas-wrapper :deep(.edge-active .vue-flow__edge-path) {
  stroke: var(--ink);
  stroke-width: 2;
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
  bottom: 20px;
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
