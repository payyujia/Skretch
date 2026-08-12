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
const colorHex = computed(() => colorOptions.find((c) => c.name === colorName.value)?.hex ?? colorOptions[0].hex)

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
    :class="[{ resizing }]"
    :style="{ width: `${width}px`, height: `${height}px`, '--frame-color': colorHex }"
    @dblclick.stop="startEditing"
  >
    <div class="frame-top">
      <div class="frame-label">
        <div class="frame-header-row">
          ◍
          <input
            v-if="isEditing"
            ref="inputRef"
            v-model="rawContent"
            class="frame-label-input nodrag"
            placeholder="Header, Subheader"
            @keydown="onKeydown"
            @blur="commit"
            @pointerdown.stop
          />
          <span v-else class="frame-header" :class="{ empty: !header }">
            {{ header || 'Header' }}
          </span>
        </div>
        
        <!-- Subheader is hidden while editing so it doesn't duplicate the comma separation -->
        <span v-if="!isEditing && subheader" class="frame-subheader">{{ subheader }}</span>
      </div>

      <div class="frame-controls nodrag">
        <button type="button" class="color-swatch" @click.stop="nextColor" title="Cycle color" :style="{'background-color': colorHex }">
          <span :style="{ backgroundColor: colorHex }" />
        </button>
        <button type="button" class="node-remove" @click.stop="board.deleteNode(id)">
          <Trash2 :size="14" />
        </button>
      </div>
    </div>

    <div class="frame-resize-handle nodrag" @pointerdown="onResizeStart" />
  </div>
</template>

<style scoped>
.frame {
  background: transparent;
  border: 2px dashed color-mix(in oklab, var(--frame-color), transparent 35%);
  box-shadow: none;
  padding: 0;
  z-index: 0;
}

.frame.resizing {
  border-style: solid;
}

.frame-top {
  position: absolute;
  top: 1rem;
  left: 14px;
  right: 14px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  font-size: xx-large;
  color: var(--muted);
}

.frame-label {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  background: transparent;
  padding: 0 6px;
  max-width: 70%;
}

.frame-header-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.frame-color-button {
  all: unset;
  cursor: pointer;
  font-size: inherit;
  color: inherit;
  line-height: 1;
}

.frame-header {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 1.5rem;
  line-height: 2rem;
  color: var(--frame-color);
}

.frame-header.empty {
  color: var(--muted);
  font-weight: 400;
  text-decoration: underline dashed;
}

.frame-subheader {
  font-family: var(--font-body);
  font-size: small;
  color: var(--muted);
}

.frame-label-input {
  font-family: var(--font-display);
  font-size: 1.5rem;
  line-height: 2rem;
  color: var(--muted); 
  border: none;
  background: transparent;
  outline: none;
  min-width: 250px;
  padding: 0;
}

.frame-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--canvas-bg);
  padding: 2px;
  border-radius: 999px;
}

.frame-remove:hover {
  color: var(--danger);
}

.frame-resize-handle {
  position: absolute;
  right: -6px;
  bottom: -6px;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: var(--surface);
  border: 1px solid var(--frame-color);
  cursor: nwse-resize;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.frame:hover .frame-resize-handle,
.frame.resizing .frame-resize-handle {
  opacity: 1;
}
</style>