<script setup>
import { onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import Canvas from '../components/Canvas.vue'
import ExportNavbar from '../components/ExportNavbar.vue'
import { useBoardStore } from '../stores/board'

const route = useRoute()
const board = useBoardStore()

const boardId = Number(route.params.id)

onUnmounted(() => {
  board.clearPresence()
})
</script>

<template>
  <div class="canvas-wrapper">
    <ExportNavbar />
    <div class="canvas-viewport">
      <Canvas :board-id="boardId" />
    </div>
  </div>
</template>

<style scoped>
.canvas-wrapper {
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
</style>