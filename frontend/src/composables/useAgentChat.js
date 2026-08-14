import { ref } from 'vue'
import { useBoardStore } from '../stores/board'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/chat'

export function useAgentChat(boardId) {
  const board = useBoardStore()
  const messages = ref([]) // { role: 'user' | 'assistant' | 'system', content, streaming? }
  const connected = ref(false)
  const sending = ref(false)

  let socket = null

  function connect() {
    const url = `${WS_BASE}?board_id=${encodeURIComponent(boardId)}`
    socket = new WebSocket(url)
    socket.onopen = () => { connected.value = true }
    socket.onclose = () => { connected.value = false }
    socket.onerror = () => { connected.value = false }
    socket.onmessage = (event) => handleEvent(JSON.parse(event.data))
  }

  function handleEvent(evt) {
    switch (evt.type) {
      case 'token': {
        const last = messages.value[messages.value.length - 1]
        if (last && last.role === 'assistant' && last.streaming) last.content += evt.content
        else messages.value.push({ role: 'assistant', content: evt.content, streaming: true })
        break
      }
      case 'message_done': {
        const last = messages.value[messages.value.length - 1]
        if (last) last.streaming = false
        sending.value = false
        break
      }
      case 'error':
        messages.value.push({ role: 'system', content: evt.message })
        sending.value = false
        break
      case 'node_thinking':
        board.applyThinking(evt)
        break
      case 'node_added':
        board.applyPlaced(evt)
        break
      case 'node_updated':
        board.applyUpdated(evt)
        break
      case 'node_deleted':
        board.applyDeleted(evt)
        break
    }
  }

  /**
   * @param {string} text
   * @param {object|null} contextNode — board node whose content is being referenced
   * @param {string[]} attachedDocNames — filenames of uploaded project documents
   */
  function send(text, contextNode, attachedDocNames = []) {
    if (!text.trim() || !socket || socket.readyState !== WebSocket.OPEN) return
    const content = contextNode
      ? `[context: node ${contextNode.serverId} — "${contextNode.content}"] ${text}`
      : text
    messages.value.push({ role: 'user', content: text })
    sending.value = true
    socket.send(JSON.stringify({
      content,
      board_id: boardId,
      attached_doc_names: attachedDocNames,
    }))
  }

  connect()

  return { messages, connected, sending, send }
}
