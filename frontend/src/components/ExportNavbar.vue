<script setup>
import { isReactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useBoardStore } from '../stores/board'

const router = useRouter()
const board = useBoardStore()

const showPanel = ref(false)
const isExporting = ref(false)
const exportSuccess = ref(false)
const exportError = ref(null)
const exportFormat = ref('auto')  // 'auto' | 'essay' | 'prd'

// ── Build a structured JSON preview from current board nodes ─────────────────
const boardJson = computed(() => {
  const frames = board.nodes.filter((n) => n.type === 'frame')
  const orphans = board.nodes.filter((n) => n.type !== 'frame' && !n.parentId)

  const sections = frames.map((f) => ({
    frame: f.data?.title || f.content || 'Untitled Frame',
    position: { x: Math.round(f.x), y: Math.round(f.y) },
    items: board.nodes
      .filter((n) => n.parentId === f.id)
      .map((n) => ({
        type: n.type,
        content: n.content,
        ...(Object.keys(n.data || {}).length ? { data: n.data } : {}),
      })),
  }))

  if (orphans.length) {
    sections.push({
      frame: '(unframed)',
      items: orphans.map((n) => ({
        type: n.type,
        content: n.content,
        ...(Object.keys(n.data || {}).length ? { data: n.data } : {}),
      })),
    })
  }

  return {
    board: board.currentBoardName || 'Untitled Board',
    exportedAt: new Date().toISOString(),
    sections,
  }
})

const jsonPreview = computed(() => JSON.stringify(boardJson.value, null, 2))

// ── Export to Google Docs ────────────────────────────────────────────────────
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function exportToDocs() {
  isExporting.value = true
  exportError.value = null
  exportSuccess.value = false
  try {
    const token = localStorage.getItem('skretch_token')
    const res = await fetch(`${BASE}/api/export/docs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        board_id: board.currentBoardId,
        payload: boardJson.value,
        format: exportFormat.value,
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `Export failed (${res.status})`)
    }
    const data = await res.json()
    exportSuccess.value = true
    // Open the Google Doc in a new tab if the backend returns a url
    if (data.doc_url) window.open(data.doc_url, '_blank')
    setTimeout(() => {
      exportSuccess.value = false
      showPanel.value = false
    }, 2500)
  } catch (err) {
    exportError.value = err.message
  } finally {
    isExporting.value = false
  }
}

const presenceUsers = computed(() => Object.values(board.presence))
</script>

<template>
  <div class="export-navbar">
    <!-- ── Left: back + board name ── -->
    <div class="nav-left">
      <button class="back-btn" @click="router.push('/boards')" title="Back to boards">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M10 3L5 8l5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <span class="board-name">{{ board.currentBoardName || 'Board' }}</span>
    </div>
    <!-- ── Center: presence avatars ── -->
    <div class="nav-center">
      <div class="presence-stack" v-if="presenceUsers.length">
        <div
          v-for="u in presenceUsers.slice(0, 5)"
          :key="u.userId"
          class="presence-avatar avatar"
          :style="{ background: u.color, borderColor: u.color }"
          :title="u.name || u.userId"
        >
          <img v-if="u.avatar" :src="u.avatar" :alt="u.name" />
          <span v-else>{{ (u.name || '?')[0].toUpperCase() }}</span>
        </div>
        <span v-if="presenceUsers.length > 5" class="presence-overflow">
          +{{ presenceUsers.length - 5 }}
        </span>
      </div>
    </div>

    <!-- ── Right: export actions ── -->
    <div class="nav-right">
      <!-- Slides: static / cosmetic -->
      <button class="export-btn slides-btn" disabled title="Coming soon">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="1" y="2" width="12" height="9" rx="1" stroke="currentColor" stroke-width="1.4"/>
          <path d="M5 12h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          <path d="M7 11v1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
        </svg>
        Google Slides
        <span class="soon-badge">SOON</span>
      </button>

      <!-- Docs: functional -->
      <button class="export-btn docs-btn" @click="showPanel = !showPanel">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M3 1h6l3 3v9a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1z" stroke="currentColor" stroke-width="1.4"/>
          <path d="M9 1v3h3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          <path d="M4 7h6M4 9.5h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
        </svg>
        Google Docs
      </button>
    </div>

    <!-- ── Export panel (slide-in) ── -->
    <Transition name="panel-slide">
      <div v-if="showPanel" class="export-panel">
        <div class="panel-header">
          <h3 class="panel-title">Export Preview</h3>
          <button class="node-remove" @click="showPanel = false">✕</button>
        </div>

        <p class="panel-description">
          Your brainstorming will be turned into full documentation. Read below for the context gleaned. Comprehensive whiteboards reap satisfying outputs.
          Make sure to plan well with Skretchpad before exporting!
        </p>

        <!-- Format selector -->
        <div class="format-selector">
          <span class="format-label">Output format</span>
          <div class="format-options">
            <label
              v-for="opt in [
                { value: 'auto',  label: 'Auto',  desc: 'AI decides' },
                { value: 'essay', label: 'Essay', desc: 'Analysis / research' },
                { value: 'prd',   label: 'PRD',   desc: 'Product requirements' },
              ]"
              :key="opt.value"
              class="format-option"
              :class="{ active: exportFormat === opt.value }"
            >
              <input type="radio" v-model="exportFormat" :value="opt.value" />
              <span class="format-option-text">
                <strong>{{ opt.label }}</strong>
                <small>{{ opt.desc }}</small>
              </span>
            </label>
          </div>
        </div>

        <!-- JSON tree preview -->
        <div class="json-preview">
          <pre>{{ jsonPreview }}</pre>
        </div>

        <!-- Status messages -->
        <div v-if="exportSuccess" class="status-success">
          ✓ Successfully exported to Google Docs
        </div>
        <div v-if="exportError" class="status-error">
          ✕ {{ exportError }}
        </div>

        <!-- Action buttons -->
        <div class="panel-actions">
          <button class="cancel-btn" @click="showPanel = false">Cancel</button>
          <button
            class="confirm-btn"
            :disabled="isExporting"
            @click="exportToDocs"
          >
            <span v-if="isExporting" class="spinner" />
            {{ isExporting ? 'Exporting…' : 'Export to Docs' }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- Backdrop when panel is open -->
    <div v-if="showPanel" class="panel-backdrop" @click="showPanel = false" />
  </div>
</template>

<style scoped>
/* ── Navbar bar ─────────────────────────────────────────────────────────── */
.export-navbar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: var(--surface);
  border-bottom: 1.5px solid var(--border);
  box-shadow: var(--shadow-sm);
  font-family: var(--font-body);
}

/* ── Left ── */
.nav-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--ink);
  transition: background 0.15s, border-color 0.15s;
  flex-shrink: 0;
}

.board-name {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 14px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}

/* ── Center (presence) ── */
.nav-center {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.presence-stack {
  display: flex;
  align-items: center;
  gap: -4px;
}

.presence-avatar {
  display: flex;
  color:var(--surface);
  align-items: center;
  justify-content: center;
  overflow: hidden;
  margin-left: -6px;
  cursor: default;
  transition: transform 0.15s;
  flex-shrink: 0;
}
.presence-avatar:first-child { margin-left: 0; }
.presence-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.presence-overflow {
  margin-left: 4px;
  font-size: 11px;
  color: var(--muted);
  font-family: var(--font-mono);
}

/* ── Right ── */
.nav-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: flex-end;
}

.export-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 600;
  font-family: var(--font-body);
  border: 1.5px solid var(--border);
  transition: all 0.15s;
  cursor: pointer;
}

.slides-btn {
  background: transparent;
  color: var(--muted);
  cursor: not-allowed;
  opacity: 0.65;
}

.docs-btn {
  background: var(--user-accent);
  color: #fff;
  border-color: var(--user-accent);
}
.docs-btn:hover {
  background: #1e4bc4;
  border-color: #1e4bc4;
  box-shadow: 0 4px 12px rgba(47, 95, 224, 0.3);
}

.soon-badge {
  background: rgba(0,0,0,0.15);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 9px;
  letter-spacing: 0.05em;
}

/* ── Export panel ─────────────────────────────────────────────────────────── */
.export-panel {
  position: fixed;
  top: 48px;
  right: 0;
  bottom: 0;
  width: 380px;
  background:var(--surface);
  border: 2px solid var(--border);
  border-radius:var(--radius);
  z-index: 200;
  display: flex;
  flex-direction: column;
  padding: 20px;
  gap: 16px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 24px;
  letter-spacing: -0.01em;
  line-height: 1.2;
  margin:0;
}

.panel-description {
  font-family: var(--font-mono);
  color: var(--muted);
  margin: 0;
  font-size: 12px;
}

.json-preview {
  flex: 1;
  overflow-y: auto;
  background: var(--border-strong);
  border-radius: var(--radius);
  padding: 12px;
}

.json-preview pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
  color:var(--accent-blue);
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── Format selector ── */
.format-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.format-label {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.format-options {
  display: flex;
  gap: 6px;
}

.format-option {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1.5px solid var(--accent-yellow);
  border-radius: 0.5rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.format-option input[type="radio"] {
  display: none;
}

.format-option.active {
  background-color: var(--accent-mint-surface);
  border-color: var(--accent-mint);
}
.format-option-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.format-option-text strong {
  font-family: var(--font-display);
  font-weight: 800;
  color: var(--accent-yellow-dark);
  line-height: 1;
}

.format-option.active .format-option-text strong {
  color: var(--accent-mint-dark);
}

.format-option-text small {
  font-family: var(--font-body);
  font-size: 9px;
  color: var(--muted);
  line-height: 1.5;
}

/* ── Status messages ── */
.status-success{
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--success);
  padding: 8px 12px;
  background: var(--canvas-bg);
  border: 1px solid var(--success-tint);
  border-radius: 4px;
}

.status-error {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--danger);
  padding: 8px 12px;
  background: var(--accent-coral-surface);
  border: 1px solid var(--accent-coral);
  border-radius: 4px;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

.cancel-btn {
  flex: 1;
  height: 38px;
  font-family: var(--font-display);
  background: transparent;
  border: 1.5px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  transition: all 0.15s;
}
.cancel-btn:hover {
  background: var(--danger);
  color: var(--surface);
}

.confirm-btn {
  flex: 2;
  height: 38px;
  background: var(--user-accent);
  border: none;
  color: var(--surface);
  border-radius: 0.5rem;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.15s;
}
.confirm-btn:hover:not(:disabled) {
  background: var(--agent-accent);
  transform: translateY(1px);
}
.confirm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: var(--surface);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

/* ── Backdrop ── */
.panel-backdrop {
  position: fixed;
  inset: 0;
  z-index: 199;
  background: rgba(0,0,0,0.25);
}

/* ── Transitions ── */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
