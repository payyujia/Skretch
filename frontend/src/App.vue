<script setup>
import Canvas from './components/Canvas.vue'
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <span class="wordmark">Skretch</span>
      <span class="tagline">Cast a wider net</span>
    </header>
    <main class="app-body">
      <Canvas />
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
  min-height: 0;
}
</style>
