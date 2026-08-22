<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import StickyNoteNode from '../components/StickyNoteNode.vue'
//import ImageNode from '../components/ImageNode.vue'
import Toolbar from '../components/Toolbar.vue'
import ChatPopover from '../components/ChatPopover.vue'
import FrameNode from '../components/Frame.vue'
import ExportNavbar from '../components/ExportNavbar.vue'
import { useBoardStore } from '../stores/board'
import { useToolStore } from '../stores/tool'
import { useAuthStore } from '../stores/auth'
import { defaultSpawnPosition } from '../utils/layout'
import { useBoardPresence } from '../composables/useBoardPresence'

// boardId now arrives via the route's `props` function (see router config),
// not from a parent template — the router acts as the "parent" that
// supplies this prop.
const props = defineProps({
  boardId: { type: [Number, String], required: true },
})
const board = useBoardStore()
const tool = useToolStore()
const auth = useAuthStore()
const presence = useBoardPresence()
const { screenToFlowCoordinate, flowToScreenCoordinate, findNode } = useVueFlow()

// ── Cursor broadcast ──────────────────────────────────────────────────────
function onMouseMove(event) {
  const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  presence.sendCursor(flowPos.x, flowPos.y)
}

// ── Remote cursors — exclude self, convert flow→screen for overlay placement ─
const remoteCursors = computed(() => {
  const myId = auth.user?.id
  return Object.values(board.presence).filter(
    (u) => u.userId !== myId && u.x != null && u.y != null
  ).map((u) => {
    const screen = flowToScreenCoordinate({ x: u.x, y: u.y })
    return { ...u, sx: screen.x, sy: screen.y }
  })
})
const hoveredNodeId = ref(null)
const chatRef = ref(null)

const FRAME_Z_INDEX = 0
const NODE_Z_INDEX = 1
const DEFAULT_NODE_SIZE = { width: 240, height: 120 }

// ── flowNodes ────────────────────────────────────────────────────────────
// This computed re-runs whenever ANY node in board.nodes changes (position,
// data, drag state, etc.) — Vue can't tell which node triggered it, only
// that the array's contents changed. A plain `.map()` here would allocate a
// brand-new object for every node on every recompute, which hands Vue Flow
// an entirely new object identity for the whole board on every single move,
// forcing it to re-diff nodes that didn't actually change.
//
// nodeObjectCache keeps one object per node id across recomputes. We only
// build a new object for a node when a field Vue Flow actually cares about
// has changed; every other node keeps its previous reference, so Vue Flow's
// diffing sees a stable identity for anything that didn't move.
const nodeObjectCache = new Map()

const flowNodes = computed(() => {
  const draggableBase = tool.active === 'select'
  const seenIds = new Set()

  const result = board.nodes.map((n) => {
    seenIds.add(n.id)
    const draggable = !n.thinking && draggableBase
    const connectable = Boolean(n.serverId)
    const zIndex = n.type === 'frame' ? FRAME_Z_INDEX : NODE_Z_INDEX
    const cached = nodeObjectCache.get(n.id)

    if (
      cached &&
      cached.type === n.type &&
      cached.position.x === n.x &&
      cached.position.y === n.y &&
      cached.zIndex === zIndex &&
      cached.data === n &&
      cached.draggable === draggable &&
      cached.connectable === connectable
    ) {
      return cached
    }

    const next = {
      id: n.id,
      type: n.type,
      position: { x: n.x, y: n.y },
      zIndex,
      data: n,
      draggable,
      connectable,
    }
    nodeObjectCache.set(n.id, next)
    return next
  })

  // Drop cache entries for nodes that no longer exist so it doesn't grow
  // unbounded across the life of the board.
  for (const id of nodeObjectCache.keys()) {
    if (!seenIds.has(id)) nodeObjectCache.delete(id)
  }

  return result
})

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

function reconcileFrameMembers(frameId) {
  const frame = board.nodes.find((n) => n.id === frameId)
  if (!frame) return
  const rect = frameRect(frame)
  for (const child of board.childrenOf(frameId)) {
    const center = nodeCenter(child.id)
    if (!center || !pointInRect(center, rect)) {
      board.reparentNode(child.id, null)
    }
  }
}

function onNodeDragStop({ node }) {
  board.checkpoint()
  board.moveNode(node.id, node.position.x, node.position.y)
  if (node.type === 'frame') reconcileFrameMembers(node.id)
  else reconcileNodeParent(node.id)
}

function onNodeClick({ node, event }) {
  if (tool.active === 'nodes' && tool.pendingNodeType && node.type === 'frame') {
    const pos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    board.createNodeOfType(tool.pendingNodeType, pos.x, pos.y, auth.user?.name ?? 'user', node.id)
    return
  }
  if (tool.active === 'select') board.select(node.id)
}

function onNodeDoubleClick({ node }) {
  if (node.type === 'frame') return
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
    board.createNodeOfType(tool.pendingNodeType, pos.x, pos.y, auth.user?.name ?? 'user')
    return
  }
  if (tool.active === 'select') board.deselect()
}

async function onPaste(event) {
  const item = [...(event.clipboardData?.items || [])].find((i) => i.type.startsWith('image/'))
  if (!item) return
  const file = item.getAsFile()
  if (!file || validateImageFile(file)) return

  const pos = defaultSpawnPosition()
  const id = await board.createNodeOfType('image', pos.x, pos.y, auth.user?.id ?? 'user')
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
  if (tag === 'INPUT' || tag === 'TEXTAREA') return

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

watch(
  () => props.boardId,
  (id) => {
    if (!id) return
    board.setBoardMeta(id)
    board.fetchBoard(id)
    presence.connect(id)
  },
  { immediate: true }
)

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('paste', onPaste)
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('paste', onPaste)
  // was CanvasWrapper's job — now that this component owns the route,
  // it owns cleanup of anything tied to "leaving this board" too.
  board.clearPresence()
})
</script>

<template>
  <div class="page-root">
    <ExportNavbar />
    <div class="canvas-viewport">
      <div class="canvas-wrapper" @mousemove="onMouseMove">
        <VueFlow
          :nodes="flowNodes"
          :default-viewport="{ zoom: 1 }"
          :min-zoom="0.3"
          :max-zoom="1.75"
          :nodes-connectable="true"
          :elevate-nodes-on-select="false"
          @node-drag-stop="onNodeDragStop"
          @node-click="onNodeClick"
          @node-double-click="onNodeDoubleClick"
          @node-mouse-enter="onNodeMouseEnter"
          @node-mouse-leave="onNodeMouseLeave"
          @pane-click="onPaneClick"
        >
          <template #node-sticky="props"><StickyNoteNode v-bind="props" /></template>
          <template #node-image="props"><ImageNode v-bind="props" /></template>
          <template #node-frame="props"><FrameNode v-bind="props" /></template>

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

        <!-- Remote cursors overlay -->
        <div class="cursor-overlay" aria-hidden="true">
          <div
            v-for="cursor in remoteCursors"
            :key="cursor.userId"
            class="remote-cursor"
            :style="{ transform: `translate(${cursor.sx}px, ${cursor.sy}px)` }"
          >
            <svg class="cursor-svg" width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M4 2L16.5 9.5L10.5 11L8 17.5L4 2Z"
                :fill="cursor.color"
                stroke="white"
                stroke-width="1.2"
                stroke-linejoin="round"
              />
            </svg>
            <span class="cursor-label" :style="{ background: cursor.color }">
              {{ cursor.name }}
            </span>
          </div>
        </div>

        <Toolbar />
        <ChatPopover ref="chatRef" :board-id="props.boardId" />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Page shell (formerly CanvasWrapper.vue) ─────────────────────────────── */
.page-root {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.canvas-viewport {
  flex: 1;
  margin-top: 48px;
  height: calc(100% - 48px);
  overflow: hidden;
}

/* ── Canvas itself ────────────────────────────────────────────────────────── */
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

/* ── Remote cursor overlay ────────────────────────────────────────────────── */
.cursor-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 20;
}

.remote-cursor {
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  align-items: flex-start;
  gap: 4px;
  will-change: transform;
  transition: transform 80ms linear;
}

.cursor-svg {
  display: block;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.3));
  flex-shrink: 0;
}

.cursor-label {
  display: inline-block;
  margin-top: 16px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  box-shadow: 0 1px 4px rgba(0,0,0,0.25);
  letter-spacing: 0.01em;
}
</style>