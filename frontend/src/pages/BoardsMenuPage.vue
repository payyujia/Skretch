<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  PlusCircle,
  LogOut,
  Pencil,
  Trash2,
  Search,
  MoreHorizontal,
} from 'lucide-vue-next'
import { getBoards, createBoard, deleteBoard } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const boards = ref([])
const auth = useAuthStore()

const loading = ref(false)
const error = ref(null)
const query = ref('')

const showCreate = ref(false)
const newBoardName = ref('')
const selectedTemplate = ref('blank')
const creating = ref(false)

const BOARD_TEMPLATES = [
  { key: 'blank', label: 'Blank canvas', description: 'Fresh workspace' },
  { key: 'kanban', label: 'Kanban board', description: 'Backlog, In progress, and Done' },
  { key: 'okr', label: 'OKR planning', description: 'Objective and measurable key results' },
  { key: 'retrospective', label: 'Retrospective', description: 'Team feedback on past project phases' },
]

// Accent names cycle for board cards
const ACCENTS = ['purple', 'yellow', 'mint', 'blue', 'coral']
function accentForId(id) {
  return ACCENTS[id % ACCENTS.length]
}

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return boards.value
  return boards.value.filter((b) =>
    b.name.toLowerCase().includes(q)
  )
})

onMounted(async () => {
  await loadBoards()
})

async function loadBoards() {
  loading.value = true
  error.value   = ''
  try {
    const res  = await getBoards()
    boards.value = (res.boards || []).sort(
      (a, b) => new Date(b.last_visited_at|| 0) -
                new Date(a.last_visited_at|| 0)
    )
  } catch (e) {
    error.value = 'Could not load boards. Make sure you are connected.'
  } finally {
    loading.value = false
  }
}
function openBoard(board) {
  console.log(board.board_id)
  router.push({ name: 'canvas', params: { id: board.board_id } })
}

async function handleCreate() {
  const name = newBoardName.value.trim() || 'Untitled Board'
  creating.value = true
  try {
    const board = await createBoard(name, selectedTemplate.value)
    boards.value.unshift(board)
    showCreate.value  = false
    newBoardName.value = ''
    selectedTemplate.value = 'blank'
    openBoard(board)
  } catch {
    error.value = 'Failed to create board.'
  } finally {
    creating.value = false
  }
}
async function handleDelete(id) {
  if (!confirm('Delete this board? This action cannot be undone.')) return
  try {
    await deleteBoard(id)
    boards.value = boards.value.filter((b) => b.board_id !== id)
  } catch {
    error.value = 'Failed to delete board.'
  }
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="menu-page">
    <!-- ── Topbar ── -->
    <header class="menu-topbar">
      <span class="brand">Skretch</span>

      <div class="topbar-right">
        <button type="button" class="icon-btn" title="Log out" @click="logout">
          <LogOut :size="16" />
          <span>Log out</span>
        </button>
      </div>
    </header>

    <!-- ── Body ── -->
    <main class="menu-body">
      <!-- Page headline -->
      <div class="page-headline">
        <h1>Your Boards</h1>
        <p class="page-sub">Pick up where you left off, or start something new.</p>
      </div>
      <!-- Search + New row -->
      <div class="toolbar-row">
        <div class="search-box">
          <Search :size="15" class="search-icon" />
          <input
            v-model="query"
            type="search"
            placeholder="Search boards…"
            class="search-input"
          />
        </div>
        <button type="button" class="new-board-btn" @click="showCreate = true">
          <PlusCircle :size="16" />
          <span>New board</span>
        </button>
      </div>

      <!-- Loading / error states -->
      <div v-if="loading" class="state-msg muted">Loading boards…</div>
      <div v-else-if="error" class="state-msg error">{{ error }}</div>

      <!-- Empty state -->
      <div v-else-if="!filtered.length && !query" class="empty-state">
        <p>No boards yet. Create your first one above.</p>
      </div>

      <div v-else-if="!filtered.length && query" class="empty-state">
        <p>No boards match "<strong>{{ query }}</strong>"</p>
      </div>

      <!-- Board grid -->
      <div v-else class="board-grid">
        <div
          v-for="board in filtered"
          :key="board.id"
          class="board-card"
          :data-accent="accentForId(board.id)"
          tabindex="0"
          @click="openBoard(board)">
          <div class="card-body">
            <p class="card-name">{{ board.name }}</p>
            <p class="card-meta">
            last visited at
              {{ board.last_visited_at ? new Date(board.last_visited_at).toLocaleDateString() : 'new' }}
            </p>
          </div>

          <div class="card-footer" @click.stop>
            <button type="button" class="card-action" title="Rename board">
              <Pencil :size="14" />
            </button>
            <button
              type="button"
              class="node-remove"
              title="Delete board"
              @click="handleDelete(board.board_id)"
            >
              <Trash2 :size="14" />
            </button>
          </div>
        </div>

        <!-- Create new card (ghost) -->
        <button type="button" class="board-card ghost" @click="showCreate = true">
          <PlusCircle :size="24" />
          <span>New board</span>
        </button>
      </div>
    </main>
  </div>

  <!-- ── New Board Modal ── -->
  <Teleport to="body">
    <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
      <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <h2 id="modal-title" class="modal-title">New board</h2>
        <p class="modal-sub">Give your board a name to get started.</p>

        <input
          v-model="newBoardName"
          class="modal-input"
          type="text"
          placeholder="e.g. Product Roadmap"
          maxlength="80"
          autofocus
          @keydown.enter="handleCreate"
          @keydown.esc="showCreate = false"
        />

        <div class="template-picker">
          <span class="template-label">Start from a template</span>
          <label
            v-for="template in BOARD_TEMPLATES"
            :key="template.key"
            class="template-option"
            :class="{ selected: selectedTemplate === template.key }"
          >
            <input v-model="selectedTemplate" type="radio" name="board-template" :value="template.key" />
            <span>
              <strong>{{ template.label }}</strong>
              <small>{{ template.description }}</small>
            </span>
          </label>
        </div>

        <div class="modal-actions">
          <button
            type="button"
            class="modal-btn cancel"
            @click="showCreate = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="modal-btn create"
            :disabled="creating"
            @click="handleCreate"
          >
            {{ creating ? 'Creating…' : 'Create board' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ── Layout ── */
.menu-page {
  min-height: 100dvh;
  background: var(--canvas-bg);
  display: flex;
  flex-direction: column;
}

/* ── Topbar ── */
.menu-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 28px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
}

.brand {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 18px;
  letter-spacing: 0.04em;
  color: var(--ink);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 12px;
  height: 34px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  font-family: var(--font-body);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.icon-btn:hover {
  background: var(--canvas-bg);
  color: var(--ink);
  border-color: var(--border);
}

/* ── Body ── */
.menu-body {
  flex: 1;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
  padding: 48px 28px 64px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

/* ── Headline ── */
.page-headline h1 {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: clamp(28px, 4vw, 42px);
  color: var(--ink);
  line-height: 1.1;
  letter-spacing: -0.01em;
  margin: 0 0 6px;
}

.page-sub {
  font-family: var(--font-body);
  font-size: 15px;
  color: var(--muted);
  margin: 0;
}

/* ── Toolbar row ── */
.toolbar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 200px;
  max-width: 400px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0 12px;
  height: 38px;
  transition: border-color 0.15s;
}
.search-box:focus-within {
  border-color: var(--ink);
}

.search-icon {
  color: var(--muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-family: var(--font-body);
  font-size: 13.5px;
  color: var(--ink);
  outline: none;
}
.search-input::placeholder {
  color: var(--muted);
}

.new-board-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 16px;
  border-radius: var(--radius);
  border: none;
  background: var(--ink);
  color: var(--surface);
  font-family: var(--font-body);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
}
.new-board-btn:hover {
  opacity: 0.88;
  transform: translateY(-1px);
}

/* ── States ── */
.state-msg {
  font-family: var(--font-body);
  font-size: 14px;
}
.state-msg.muted {
  color: var(--muted);
}
.state-msg.error {
  color: var(--danger);
}

.empty-state {
  color: var(--muted);
  font-family: var(--font-body);
  font-size: 14px;
}

/* ── Grid ── */
.board-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 18px;
}

/* ── Board card ── */
.board-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  min-height: 130px;
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}


.board-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.board-card:focus-visible {
  outline: 2px solid var(--user-accent);
  outline-offset: 2px;
}

.card-body {
  flex: 1;
  padding: 16px 16px 10px;
}

.card-name {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  color: var(--ink);
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 5px;
}

.card-footer {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  border-top: 1px solid var(--border);
  justify-content: flex-end;
  opacity: 0;
  transition: opacity 0.15s;
}

.board-card:hover .card-footer {
  opacity: 1;
}

.card-action {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--muted);
  border-radius: 6px;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.card-action:hover {
  background: var(--canvas-bg);
  color: var(--ink);
}
.card-action.danger:hover {
  color: var(--danger);
  background: var(--danger-tint);
}

/* Ghost card */
.board-card.ghost {
  border-style: dashed;
  background: transparent;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--muted);
  font-family: var(--font-body);
  font-size: 13.5px;
  font-weight: 500;
  min-height: 130px;
}
.board-card.ghost:hover {
  border-color: var(--ink);
  color: var(--ink);
  box-shadow: none;
  transform: none;
}

/* ── Modal ── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.modal-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) * 1.5);
  box-shadow: var(--shadow-md);
  padding: 28px 28px 24px;
  width: min(420px, calc(100vw - 40px));
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.modal-title {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 18px;
  color: var(--ink);
  margin: 0;
  letter-spacing: -0.01em;
}

.modal-sub {
  font-family: var(--font-body);
  font-size: 13.5px;
  color: var(--muted);
  margin: 0;
}

.modal-input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--canvas-bg);
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--ink);
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s;
}
.modal-input::placeholder {
  color: var(--muted);
}
.modal-input:focus {
  border-color: var(--ink);
}

.template-picker {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 4px;
}

.template-label {
  color: var(--ink);
  font-size: 12px;
  font-weight: 700;
}

.template-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.template-option.selected {
  border-color: var(--ink);
  background: var(--canvas-bg);
}

.template-option input {
  margin: 2px 0 0;
  accent-color: var(--ink);
}

.template-option span {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.template-option strong {
  color: var(--ink);
  font-size: 13px;
}

.template-option small {
  color: var(--muted);
  font-size: 11.5px;
}

.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 4px;
}

.modal-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: var(--radius);
  font-family: var(--font-body);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, background 0.15s;
}
.modal-btn.cancel {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
}
.modal-btn.cancel:hover {
  background: var(--canvas-bg);
  color: var(--ink);
  border-color: var(--ink);
}
.modal-btn.create {
  background: var(--ink);
  border: none;
  color: var(--surface);
}
.modal-btn.create:hover:not(:disabled) {
  opacity: 0.85;
}
.modal-btn.create:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
