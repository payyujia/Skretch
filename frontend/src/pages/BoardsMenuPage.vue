<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getBoards, createBoard } from '../api/client'

const router = useRouter()
const auth   = useAuthStore()

const boards      = ref([])
const loading     = ref(true)
const creating    = ref(false)
const newBoardName = ref('')
const showCreate  = ref(false)
const error       = ref('')

onMounted(async () => {
  await loadBoards()
})

async function loadBoards() {
  loading.value = true
  error.value   = ''
  try {
    const res  = await getBoards()
    boards.value = (res.boards || []).sort(
      (a, b) => new Date(b.last_visited_at || b.created_at || 0) -
                new Date(a.last_visited_at || a.created_at || 0)
    )
  } catch (e) {
    error.value = 'Could not load boards. Make sure you are connected.'
  } finally {
    loading.value = false
  }
}

function openBoard(board) {
  router.push({ name: 'canvas', params: { id: board.board_id } })
}

async function handleCreate() {
  const name = newBoardName.value.trim() || 'Untitled Board'
  creating.value = true
  try {
    const board = await createBoard(name)
    boards.value.unshift(board)
    showCreate.value  = false
    newBoardName.value = ''
    openBoard(board)
  } catch {
    error.value = 'Failed to create board.'
  } finally {
    creating.value = false
  }
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// Deterministic pastel colour per board (cycles through retro palette)
const CARD_COLORS = ['#f5f0e8', '#fefce8', '#f0f4ff', '#f0fdf4', '#fff1f2', '#fdf4ff']
function cardColor(idx) { return CARD_COLORS[idx % CARD_COLORS.length] }
</script>

<template>
  <div class="boards-root">
    <!-- ── Top Navbar ──────────────────────────────────────────────────── -->
    <header class="topbar">
      <div class="topbar-left">
        <span class="logo">
          <span class="logo-sk">SK</span><span class="logo-retch">RETCH</span>
        </span>
        <!-- Cosmetic nav pills -->
        <nav class="nav-pills" aria-label="Navigation (cosmetic)">
          <button class="nav-pill active">Boards</button>
          <button class="nav-pill">Templates</button>
          <button class="nav-pill">Shared</button>
          <button class="nav-pill">Archive</button>
        </nav>
      </div>

      <div class="topbar-right">
        <!-- Cosmetic action buttons -->
        <button class="btn-outline-sm">Upgrade</button>
        <button class="btn-outline-sm">Settings</button>

        <!-- User avatar -->
        <div class="user-chip" v-if="auth.user">
          <img
            v-if="auth.user.avatar_url"
            :src="auth.user.avatar_url"
            :alt="auth.user.name"
            class="avatar"
            referrerpolicy="no-referrer"
          />
          <span v-else class="avatar avatar-fallback">
            {{ auth.user.name?.[0]?.toUpperCase() || '?' }}
          </span>
          <span class="user-name">{{ auth.user.name }}</span>
          <button class="logout-btn" @click="auth.logout(); $router.push('/')">Logout</button>
        </div>
      </div>
    </header>

    <!-- ── Hero headline ─────────────────────────────────────────────── -->
    <div class="page-hero">
      <div class="hero-inner">
        <div class="hero-label">&#x2016; YOUR WORKSPACE</div>
        <h1 class="hero-title">
          Your Boards<span class="hero-dot">.</span>
        </h1>
        <p class="hero-sub">
          Pick up where you left off, or start something new.
        </p>
      </div>
    </div>

    <!-- ── Main content ───────────────────────────────────────────────── -->
    <main class="main-content">

      <!-- Error banner -->
      <div v-if="error" class="error-banner">
        <span>&#x26A0; {{ error }}</span>
        <button @click="error = ''" class="error-dismiss">&#x2715;</button>
      </div>

      <!-- Section header -->
      <div class="section-header">
        <h2 class="section-title">Recent Boards</h2>
        <div class="section-actions">
          <!-- Cosmetic filters -->
          <button class="filter-btn">All</button>
          <button class="filter-btn">Mine</button>
          <button class="filter-btn">Shared</button>
          <!-- New board -->
          <button class="btn-new" @click="showCreate = true">
            <span class="plus-icon">+</span> New Board
          </button>
        </div>
      </div>

      <!-- Loading skeleton -->
      <div v-if="loading" class="grid">
        <div v-for="i in 6" :key="i" class="card-skeleton" />
      </div>

      <!-- Empty state -->
      <div v-else-if="!boards.length" class="empty-state">
        <div class="empty-stamp">NO BOARDS YET</div>
        <p class="empty-hint">Create your first board to get started.</p>
        <button class="btn-new-lg" @click="showCreate = true">+ Create a Board</button>
      </div>

      <!-- Board grid -->
      <div v-else class="grid">
        <button
          v-for="(board, idx) in boards"
          :key="board.board_id"
          class="board-card"
          :style="{ background: cardColor(idx) }"
          @click="openBoard(board)"
          :aria-label="`Open board: ${board.name}`"
        >
          <!-- Whiteboard surface -->
          <div class="card-canvas">
            <!-- Decorative dot grid on the "whiteboard" -->
            <div class="card-grid-dots" aria-hidden="true" />
            <!-- Simulated sticky note deco -->
            <div class="deco-sticky s1" aria-hidden="true" />
            <div class="deco-sticky s2" aria-hidden="true" />
            <div class="deco-sticky s3" aria-hidden="true" />
          </div>
          <!-- Marker tray -->
          <div class="card-tray">
            <div class="tray-info">
              <span class="card-name">{{ board.name }}</span>
              <span class="card-date">{{ formatDate(board.last_visited_at || board.created_at) }}</span>
            </div>
            <div class="tray-markers" aria-hidden="true">
              <span class="marker m-blue" />
              <span class="marker m-red" />
              <span class="marker m-green" />
            </div>
          </div>
        </button>
      </div>
    </main>

    <!-- ── Create board modal ─────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
        <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-stamp">&#x25A0; NEW BOARD</div>
          <h2 class="modal-title" id="modal-title">Name your board</h2>
          <input
            v-model="newBoardName"
            class="modal-input"
            placeholder="e.g. Competitor Analysis Q3"
            @keydown.enter="handleCreate"
            autofocus
            maxlength="80"
          />
          <div class="modal-actions">
            <button class="btn-cancel" @click="showCreate = false; newBoardName = ''">
              Cancel
            </button>
            <button class="btn-create" :disabled="creating" @click="handleCreate">
              <span v-if="creating">Creating…</span>
              <span v-else>Create Board</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── FAB new board (mobile / quick-access) ──────────────────────── -->
    <button class="fab" @click="showCreate = true" aria-label="Create new board">+</button>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;600;700&display=swap');

/* ── Root ──────────────────────────────────────────────────────────────── */
.boards-root {
  min-height: 100vh;
  background: #faf7f2;
  font-family: 'IBM Plex Mono', monospace;
  color: #0d0d0d;
  display: flex;
  flex-direction: column;
}

/* ── Topbar ────────────────────────────────────────────────────────────── */
.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 56px;
  background: #f5f0e8;
  border-bottom: 2px solid #1a1a1a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
}
.topbar-left { display: flex; align-items: center; gap: 24px; }
.topbar-right { display: flex; align-items: center; gap: 12px; }

.logo {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  user-select: none;
}
.logo-sk    { color: #2f5fe0; }
.logo-retch { color: #0d0d0d; }

/* Cosmetic nav pills */
.nav-pills { display: flex; gap: 4px; }
.nav-pill {
  padding: 4px 12px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  letter-spacing: 0.04em;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: #6b7280;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.nav-pill:hover, .nav-pill.active {
  background: #1a1a1a;
  color: #f5f0e8;
  border-color: #1a1a1a;
}

.btn-outline-sm {
  padding: 5px 12px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.05em;
  background: transparent;
  border: 1px solid #c5bfb3;
  border-radius: 2px;
  color: #6b7280;
  cursor: pointer;
}
.btn-outline-sm:hover { border-color: #1a1a1a; color: #0d0d0d; }

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 12px;
  border-left: 1px solid #c5bfb3;
}
.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 2px solid #1a1a1a;
  object-fit: cover;
}
.avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #0d0d0d;
  color: #f5f0e8;
  font-size: 13px;
  font-weight: 700;
}
.user-name {
  font-size: 12px;
  font-weight: 600;
  color: #0d0d0d;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.logout-btn {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: #6b7280;
  background: transparent;
  border: none;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}
.logout-btn:hover { color: #f43f5e; }

/* ── Hero ──────────────────────────────────────────────────────────────── */
.page-hero {
  border-bottom: 1px solid #d4c9a8;
  background: #f5f0e8;
  padding: 40px 0 32px;
}
.hero-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 32px;
}
.hero-label {
  font-size: 10px;
  letter-spacing: 0.2em;
  color: #9ca3af;
  margin-bottom: 8px;
}
.hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 48px;
  font-weight: 700;
  margin: 0 0 8px;
  line-height: 1.05;
}
.hero-dot { color: #2f5fe0; }
.hero-sub {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

/* ── Main content ──────────────────────────────────────────────────────── */
.main-content {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 32px 80px;
}

/* Error banner */
.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff1f2;
  border: 1px solid #f43f5e;
  border-radius: 2px;
  padding: 10px 14px;
  font-size: 13px;
  color: #f43f5e;
  margin-bottom: 24px;
}
.error-dismiss {
  background: transparent;
  border: none;
  color: #f43f5e;
  font-size: 14px;
  cursor: pointer;
}

/* Section header */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}
.section-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 20px;
  font-weight: 700;
  margin: 0;
}
.section-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-btn {
  padding: 5px 12px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.04em;
  background: transparent;
  border: 1px solid #c5bfb3;
  border-radius: 2px;
  color: #6b7280;
  cursor: pointer;
}
.filter-btn:hover { background: #e8e2d8; color: #0d0d0d; }

.btn-new {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  background: #0d0d0d;
  color: #f5f0e8;
  border: 2px solid #0d0d0d;
  border-radius: 2px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  box-shadow: 2px 2px 0 #6b7280;
  transition: transform 0.1s, box-shadow 0.1s;
}
.btn-new:hover { transform: translate(-1px, -1px); box-shadow: 3px 3px 0 #6b7280; }
.btn-new:active { transform: translate(1px,1px); box-shadow: 0 0 0 #6b7280; }
.plus-icon { font-size: 16px; line-height: 1; }

/* ── Board card grid ───────────────────────────────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.board-card {
  all: unset;
  display: flex;
  flex-direction: column;
  border: 2px solid #1a1a1a;
  border-radius: 2px;
  overflow: hidden;
  cursor: pointer;
  box-shadow: 3px 3px 0 #1a1a1a;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  background: #f5f0e8;
}
.board-card:hover {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0 #1a1a1a;
}
.board-card:active { transform: translate(1px,1px); box-shadow: 1px 1px 0 #1a1a1a; }
.board-card:focus-visible {
  outline: 2px solid #2f5fe0;
  outline-offset: 2px;
}

/* Card whiteboard area */
.card-canvas {
  position: relative;
  height: 140px;
  overflow: hidden;
  border-bottom: 2px solid #1a1a1a;
}
.card-grid-dots {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, #d4c9a8 1px, transparent 1px);
  background-size: 18px 18px;
}
/* Decorative sticky notes */
.deco-sticky {
  position: absolute;
  width: 42px;
  height: 42px;
  border: 1.5px solid rgba(26,26,26,0.3);
  border-radius: 2px;
  box-shadow: 2px 2px 4px rgba(0,0,0,0.08);
}
.s1 { background: #fef9c3; top: 20px; left: 24px; transform: rotate(-4deg); }
.s2 { background: #dbeafe; top: 30px; left: 80px; transform: rotate(2deg); }
.s3 { background: #fce7f3; top: 18px; left: 140px; transform: rotate(-1deg); }

/* Marker tray (card footer) */
.card-tray {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: inherit;
}
.tray-info { display: flex; flex-direction: column; gap: 2px; }
.card-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: #0d0d0d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
}
.card-date { font-size: 11px; color: #9ca3af; letter-spacing: 0.04em; }

.tray-markers { display: flex; gap: 4px; align-items: center; }
.marker {
  display: block;
  width: 6px;
  height: 28px;
  border-radius: 3px;
  border: 1px solid rgba(0,0,0,0.15);
}
.m-blue  { background: #2f5fe0; }
.m-red   { background: #f43f5e; }
.m-green { background: #4caf50; }

/* Loading skeletons */
.card-skeleton {
  height: 190px;
  background: #e8e2d8;
  border: 2px solid #c5bfb3;
  border-radius: 2px;
  animation: skeleton-pulse 1.4s ease-in-out infinite;
}
@keyframes skeleton-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }

/* Empty state */
.empty-state {
  text-align: center;
  padding: 80px 0;
}
.empty-stamp {
  font-size: 11px;
  letter-spacing: 0.2em;
  color: #9ca3af;
  border: 1px dashed #c5bfb3;
  display: inline-block;
  padding: 6px 16px;
  margin-bottom: 16px;
}
.empty-hint { font-size: 14px; color: #6b7280; margin-bottom: 24px; }
.btn-new-lg {
  padding: 12px 28px;
  background: #0d0d0d;
  color: #f5f0e8;
  border: 2px solid #0d0d0d;
  border-radius: 2px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 3px 3px 0 #6b7280;
}
.btn-new-lg:hover { box-shadow: 5px 5px 0 #6b7280; }

/* ── Create modal ──────────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(13,13,13,0.6);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-box {
  background: #f5f0e8;
  border: 2px solid #1a1a1a;
  border-radius: 2px;
  padding: 36px 32px;
  width: 400px;
  max-width: 90vw;
  box-shadow: 6px 6px 0 #1a1a1a;
}
.modal-stamp {
  font-size: 9px;
  letter-spacing: 0.15em;
  color: #6b7280;
  background: #e8e2d8;
  border: 1px solid #c5bfb3;
  display: inline-block;
  padding: 3px 8px;
  margin-bottom: 16px;
}
.modal-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 20px;
}
.modal-input {
  width: 100%;
  padding: 10px 12px;
  border: 2px solid #1a1a1a;
  border-radius: 2px;
  background: #faf7f2;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 14px;
  color: #0d0d0d;
  outline: none;
  box-sizing: border-box;
  transition: box-shadow 0.15s;
}
.modal-input:focus { box-shadow: 3px 3px 0 #2f5fe0; border-color: #2f5fe0; }
.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}
.btn-cancel {
  padding: 9px 18px;
  background: transparent;
  border: 2px solid #c5bfb3;
  border-radius: 2px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
}
.btn-cancel:hover { border-color: #1a1a1a; color: #0d0d0d; }
.btn-create {
  padding: 9px 20px;
  background: #0d0d0d;
  color: #f5f0e8;
  border: 2px solid #0d0d0d;
  border-radius: 2px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 2px 2px 0 #6b7280;
  transition: opacity 0.15s;
}
.btn-create:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-create:not(:disabled):hover { box-shadow: 3px 3px 0 #6b7280; }

/* ── FAB ──────────────────────────────────────────────────────────────── */
.fab {
  position: fixed;
  bottom: 32px;
  right: 32px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #0d0d0d;
  color: #f5f0e8;
  border: 2px solid #0d0d0d;
  font-size: 28px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 3px 3px 0 #6b7280;
  transition: transform 0.15s, box-shadow 0.15s;
  z-index: 50;
}
.fab:hover { transform: translate(-1px,-1px); box-shadow: 5px 5px 0 #6b7280; }

/* ── Responsive ─────────────────────────────────────────────────────── */
@media (max-width: 900px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
  .nav-pills { display: none; }
}
@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr; }
  .topbar { padding: 0 16px; }
  .main-content { padding: 24px 16px 80px; }
}
</style>
