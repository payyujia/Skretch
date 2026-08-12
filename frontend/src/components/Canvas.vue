<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import StickyNoteNode from './StickyNoteNode.vue'
import Toolbar from './Toolbar.vue'
import ChatPopover from './ChatPopover.vue'
import FrameNode from './Frame.vue'
import { useBoardStore } from '../stores/board'
import { useToolStore } from '../stores/tool'
import { defaultSpawnPosition } from '../utils/layout'
// import { uploadImage } from '../api/client'
// import { validateImageFile } from '../utils/image'

const board = useBoardStore()
const tool = useToolStore()
const { screenToFlowCoordinate, findNode } = useVueFlow()
const hoveredNodeId = ref(null)
const chatRef = ref(null)

// Frames render behind everything else — pin a low zIndex on frame-type
// nodes so members painted after them (or later in the array) never end up
// visually trapped under a frame's own hit area.
const FRAME_Z_INDEX = 0
const NODE_Z_INDEX = 1

// Fallback size used for a node's hit-box when Vue Flow hasn't measured its
// real DOM dimensions yet (e.g. the very first drag tick, or a node that's
// still off-screen). Close enough for containment checks; once the node has
// rendered, findNode(id).dimensions gives the real size instead.
const DEFAULT_NODE_SIZE = { width: 240, height: 120 }

const flowNodes = computed(() =>
  board.nodes.map((n) => ({
    id: n.id,
    type: n.type,
    position: { x: n.x, y: n.y },
    zIndex: n.type === 'frame' ? FRAME_Z_INDEX : NODE_Z_INDEX,
    data: n,
    draggable: !n.thinking && tool.active === 'select',
    connectable: Boolean(n.serverId),
  }))
)

// --- geometric containment (frame <-> member) ---

function frameRect(frameBoardNode) {
  return {
    x: frameBoardNode.x,
    y: frameBoardNode.y,
    width: frameBoardNode.data?.width ?? 500,
    height: frameBoardNode.data?.height ?? 700,
  }
}

function nodeCenter(nodeId) {
  const boardNode = board.nodes.find((n) => n.id === nodeId)
  if (!boardNode) return null
  const measured = findNode(nodeId)?.dimensions
  const width = measured?.width || DEFAULT_NODE_SIZE.width
  const height = measured?.height || DEFAULT_NODE_SIZE.height
  return { x: boardNode.x + width / 2, y: boardNode.y + height / 2 }
}

function pointInRect(point, rect) {
  return (
    point.x >= rect.x && point.x <= rect.x + rect.width &&
    point.y >= rect.y && point.y <= rect.y + rect.height
  )
}

/** Re-derive a single (non-frame) node's parent from where its center
 * currently sits — dropped inside a frame's bounds it joins that frame,
 * dragged back out it's freed. Runs after every drag of that node. */
function reconcileNodeParent(nodeId) {
  const node = board.nodes.find((n) => n.id === nodeId)
  if (!node || node.type === 'frame') return
  const center = nodeCenter(nodeId)
  if (!center) return

  const frames = board.nodes.filter((n) => n.type === 'frame')
  const containing = frames.find((f) => pointInRect(center, frameRect(f)))
  const targetId = containing?.id ?? null
  if (node.parentId !== targetId) board.reparentNode(nodeId, targetId)
}

/** After a frame itself moves, any member left outside its new bounds is
 * freed rather than dragged along — we don't auto-follow the frame, only
 * auto-detect containment, per the same rule a fresh drag would apply. */
function reconcileFrameMembers(frameId) {
  const frame = board.nodes.find((n) => n.id === frameId)
  if (!frame) return
  const rect = frameRect(frame)
  for (const node of board.nodes.filter((n) => n.type !== 'frame' && n.id !== frameId)) {
    const center = nodeCenter(node.id)
    const inside = center && pointInRect(center, rect)
    const shouldBelong = inside ? frameId : (node.parentId === frameId ? null : node.parentId)
    if (node.parentId !== shouldBelong) board.reparentNode(node.id, shouldBelong)
  }
}

function onNodeDragStop({ node }) {
  board.checkpoint()
  board.moveNode(node.id, node.position.x, node.position.y)
  if (node.type === 'frame') reconcileFrameMembers(node.id)
  else reconcileNodeParent(node.id)
}

function onNodeClick({ node, event }) {
  // Clicking a frame's body with a node tool armed creates the new node
  // inside that frame, rather than just selecting the frame — otherwise the
  // frame's own hit area (it fills its whole rect, background or not)
  // swallows clicks and the "nodes" tool becomes unusable anywhere inside one.
  if (tool.active === 'nodes' && tool.pendingNodeType && node.type === 'frame') {
    const pos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    board.createNodeOfType(tool.pendingNodeType, pos.x, pos.y, 'user', node.id)
    return
  }
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
      <template #node-frame="props"><FrameNode v-bind="props" @resize-end="reconcileFrameMembers(props.id)" /></template>

      <Background variant="dots" :gap="28" :size="3" color="var(--canvas-dot)" />
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