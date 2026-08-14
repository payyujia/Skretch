import { ref, onUnmounted } from 'vue'
import { useBoardStore } from '../stores/board'

const BASE_WS = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws')

/**
 * Manages the /ws/board/:boardId presence WebSocket connection.
 *
 * Lifecycle: call connect(boardId) when entering a board, the composable
 * cleans up automatically when the component is unmounted.
 *
 * Inbound events dispatched to boardStore:
 *   node_created  → applyPlaced
 *   node_updated  → applyUpdated
 *   node_deleted  → applyDeleted
 *   presence      → applyPresence
 *
 * Outbound events sent by this composable:
 *   cursor_move   (throttled, ~30 fps)
 */
export function useBoardPresence() {
  const board = useBoardStore()
  const isConnected = ref(false)
  let ws = null
  let heartbeatTimer = null
  let cursorTimer = null
  let pendingCursor = null

  // ── Inbound event dispatch ────────────────────────────────────────────────
  function handleMessage(raw) {
    let msg
    try { msg = JSON.parse(raw) } catch { return }

    switch (msg.type) {
      case 'node_created':
        board.applyPlaced({ tempId: null, node: msg.node })
        break
      case 'node_updated':
        board.applyUpdated({ node: msg.node })
        break
      case 'node_deleted':
        board.applyDeleted({ id: msg.id })
        break
      case 'presence':
        board.applyPresence(msg.users ?? [])
        break
      // 'pong' — heartbeat reply, no action needed
    }
  }

  // ── Outbound: throttled cursor broadcast ─────────────────────────────────
  function sendCursor(x, y) {
    pendingCursor = { x, y }
    if (!cursorTimer) {
      cursorTimer = setTimeout(() => {
        if (ws?.readyState === WebSocket.OPEN && pendingCursor) {
          ws.send(JSON.stringify({ type: 'cursor_move', x: pendingCursor.x, y: pendingCursor.y }))
        }
        pendingCursor = null
        cursorTimer = null
      }, 33) // ~30 fps
    }
  }

  // ── Connection management ─────────────────────────────────────────────────
  function connect(boardId) {
    if (ws) disconnect()
    const token = localStorage.getItem('skretch_token')
    const url = `${BASE_WS}/ws/board/${boardId}${token ? `?token=${token}` : ''}`
    ws = new WebSocket(url)

    ws.onopen = () => {
      isConnected.value = true
      // Keepalive ping every 25s
      heartbeatTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
      }, 25_000)
    }

    ws.onmessage = (e) => handleMessage(e.data)

    ws.onclose = () => {
      isConnected.value = false
      board.clearPresence()
      clearInterval(heartbeatTimer)
    }

    ws.onerror = (e) => {
      console.error('[presence ws] error', e)
    }
  }

  function disconnect() {
    clearInterval(heartbeatTimer)
    clearTimeout(cursorTimer)
    ws?.close()
    ws = null
    isConnected.value = false
    board.clearPresence()
  }

  onUnmounted(disconnect)

  return {
    isConnected,
    connect,
    disconnect,
    sendCursor,
  }
}
