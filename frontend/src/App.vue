<script setup>
import { ref } from 'vue'
import Canvas from './components/Canvas.vue'
import ChatPanel from './components/ChatPanel.vue'

const chatPanel = ref(null)
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <span class="wordmark">Skretch</span>
      <span class="tagline">think out loud, ship the doc</span>
    </header>
    <main class="app-body">
      <Canvas @ask-ai="chatPanel?.focusWithContext()" />
      <ChatPanel ref="chatPanel" />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.topbar {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  z-index: 10;
}

.wordmark {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 18px;
  letter-spacing: -0.02em;
}

.tagline {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
}

.app-body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 360px;
  min-height: 0;
}

@media (max-width: 860px) {
  .app-body {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr 320px;
  }
}
</style>
