<script setup>
import { computed, nextTick, ref } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { useBoardStore } from '../stores/board'
import { colorOptions } from '../utils/nodeTypes'

const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, required: true },
})
const emit = defineEmits(['resizeEnd'])

const board = useBoardStore()
const inputRef = ref(null)
const resizing = ref(false)

const isEditing = computed(() => board.editingNodeId === props.id)
const isSelected = computed(() => board.selectedNodeId === props.id)
const header = computed(() => {
  const raw = props.data.content ?? ''
  const commaIdx = raw.indexOf(',')
  return commaIdx === -1 ? raw : raw.slice(0, commaIdx)
})
const subheader = computed(() => {
  const raw = props.data.content ?? ''
  const commaIdx = raw.indexOf(',')
  return commaIdx === -1 ? '' : raw.slice(commaIdx + 1).trim()
})

const rawContent = computed({
  get: () => props.data.content,
  set: (value) => board.setContentLocal(props.id, value),
})

const width = computed(() => props.data.data?.width ?? 500)
const height = computed(() => props.data.data?.height ?? 700)

const colorName = computed(() => props.data.data?.color ?? colorOptions[0].name)

function nextColor() {
  const index = colorOptions.findIndex((c) => c.name === colorName.value)
  const next = colorOptions[(index + 1) % colorOptions.length]
  board.checkpoint()
  console.log(next)
  board.updateNodeData(props.id, { color: next.name })
}

function startEditing() {
  board.startEditing(props.id)
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select()
  })
}

async function commit() {
  board.checkpoint()
  await board.updateNodeContent(props.id, rawContent.value.trim())
  board.stopEditing()
}

function onKeydown(event) {
  if (event.key === 'Enter' || event.key === 'Escape') {
    event.preventDefault()
    commit()
  }
}

// Manual bottom-right resize handle. The "nodrag" class is Vue Flow's own
// escape hatch — Vue Flow starts node dragging from a pointerdown listener
// registered in the capture phase, so a bubble-phase @pointerdown.stop here
// is too late to block it; nodrag is what actually suppresses it.
function onResizeStart(event) {
  event.stopPropagation()
  resizing.value = true
  const startX = event.clientX
  const startY = event.clientY
  const startW = width.value
  const startH = height.value

  function onMove(e) {
    const w = Math.max(160, startW + (e.clientX - startX))
    const h = Math.max(120, startH + (e.clientY - startY))
    board.updateNodeData(props.id, { width: w, height: h })
  }
  function onUp() {
    resizing.value = false
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    emit('resizeEnd')
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}
</script>

<template>
  <div
    class="board-node frame"
    :class="[{ selected: isSelected, resizing }]"
    :style="{ width: `${width}px`, height: `${height}px`,  border: `1.6px dashed var(--accent-${colorName})` }"
  >
    <div class="frame-top">
      <div class="frame-label" @dblclick.stop="startEditing">
        <div class="frame-header-row" :style="{color:`var(--accent-${colorName}-dark)`}">
          <input
            v-if="isEditing"
            ref="inputRef"
            v-model="rawContent"
            class="frame-label-input nodrag"
            placeholder="Header, description"
            @keydown="onKeydown"
            @blur="commit"
            @pointerdown.stop
          />
          <span v-else class="frame-header" :class="{ empty: !header }">
            {{ header || 'Untitled cluster' }}
          </span>
        </div>

        <!-- Subheader is hidden while editing so it doesn't duplicate the comma separation -->
        <span v-if="!isEditing && subheader" class="frame-subheader">{{ subheader }}</span>
      </div>

      <div class="frame-controls nodrag">
        <button
          type="button"
          class="color-swatch"
          @click.stop="nextColor"
          title="Cycle color"
          :style="{ backgroundColor: `var(--accent-${colorName})` }"
        />
        <button type="button" class="node-remove" @click.stop="board.deleteNode(id)">
          <Trash2 :size="14" />
        </button>
      </div>
    </div>
    <div class="frame-resize-handle nodrag" @pointerdown="onResizeStart" />
  </div>
</template>

<style scoped>
/* ── Frame container ──────────────────────────────────────────────── */
.frame {
  background: transparent;
  border-radius: 10px;
  padding: 0;
  z-index: 0;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.frame.selected {
  z-index: -10 !important;
  outline: none;
  box-shadow: var(--shadow-md);
}

.frame.resizing {
  box-shadow: 0 6px 28px rgba(0, 0, 0, 0.14);
}

/* ── Header bar ── */
.frame-top {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 24px;
  height: 100px;
  border-bottom: 1px solid var(--border);
}

.frame-label {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.frame-header-row {
  display: flex;
  align-items: center;
  gap: 0;
  width: 100%;
}

.frame-header {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 24px;
  letter-spacing: -0.01em;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}

.frame-header.empty {
  font-weight: 500;
  font-style: italic;
}

.frame-subheader {
  font-family: var(--font-body);
  font-size : 12px;
  color: var(--muted);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}

.frame-label-input {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 24px;
  color: var(--ink);
  border: none;
  border-bottom: 1.5px dashed color-mix(in oklab, var(--frame-color), transparent 30%);
  background: transparent;
  outline: none;
  width: 100%;
  max-width: 280px;
  padding: 0;
}

/* ── Controls (fade in on hover) ── */
.frame-controls {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.frame:hover .frame-controls {
  opacity: 1;
}

/* ── Resize handle ── */
.frame-resize-handle {
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: color-mix(in oklab, var(--frame-color), transparent 30%);
  cursor: nwse-resize;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.frame:hover .frame-resize-handle,
.frame.resizing .frame-resize-handle {
  opacity: 1;
}
</style>
