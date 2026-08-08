import { defineStore } from 'pinia'
import * as api from '../api/client'
import { nextPosition, defaultSpawnPosition } from '../utils/layout'

let seq = 0
const clientId = (prefix) => `${prefix}-${++seq}-${Math.random().toString(36).slice(2, 7)}`

/**
 * Every node keeps a permanent client-side `id` (used as the vue-flow key and
 * for edge references) plus a `serverId` that's null until the backend has
 * confirmed it. This means creating a node, editing it, and having it synced
 * never causes a re-key/remount — it just fills in `serverId` in place.
 */
export const useBoardStore = defineStore('board', {
  state: () => ({
    nodes: [],
    edges: [],
    selectedNodeId: null,
    editingNodeId: null,
  }),

  getters: {
    selectedNode: (state) => state.nodes.find((n) => n.id === state.selectedNodeId) || null,
    byServerId: (state) => (serverId) => state.nodes.find((n) => n.serverId === serverId),
  },

  actions: {
    async fetchBoard() {
      const board = await api.getBoard()
      this.nodes = board.nodes.map((n) => ({ ...n, serverId: n.id, thinking: false, justPlaced: false }))
      this.edges = board.edges.map((e) => this._edgeFromServer(e))
    },

    _edgeFromServer(e) {
      const source = this.byServerId(e.source_id)?.id ?? e.source_id
      const target = this.byServerId(e.target_id)?.id ?? e.target_id
      return { id: e.id, source, target }
    },

    // --- creating & editing (optimistic, local-first) ---
    spawnNode({ x, y, createdBy = 'user' } = {}) {
      const id = clientId('local')
      this.nodes.push({ id, serverId: null, content: '', x, y, createdBy, thinking: false, justPlaced: false })
      this.selectedNodeId = id
      this.editingNodeId = id
      return id
    },

    spawnFrom(originId, direction) {
      const origin = this.nodes.find((n) => n.id === originId)
      const pos = origin ? nextPosition(origin, direction, this.nodes) : defaultSpawnPosition()
      return this.spawnNode({ x: pos.x, y: pos.y })
    },

    setContentLocal(id, content) {
      const node = this.nodes.find((n) => n.id === id)
      if (node) node.content = content
    },

    /** Empty content discards the node (a blank sticky note isn't worth keeping);
     * otherwise creates it on first save or patches it after that. */
    async commitNode(id, content) {
      const node = this.nodes.find((n) => n.id === id)
      if (!node) return
      const trimmed = content.trim()
      if (!trimmed) {
        await this.deleteNode(id)
        return
      }
      node.content = trimmed
      if (!node.serverId) {
        const saved = await api.createNode({ content: trimmed, x: node.x, y: node.y, created_by: node.createdBy })
        node.serverId = saved.id
      } else {
        await api.updateNode(node.serverId, { content: trimmed })
      }
    },

    select(id) {
      this.selectedNodeId = id
    },
    startEditing(id) {
      this.selectedNodeId = id
      this.editingNodeId = id
    },
    stopEditing() {
      this.editingNodeId = null
    },
    deselect() {
      this.selectedNodeId = null
      this.editingNodeId = null
    },

    async moveNode(id, x, y) {
      const node = this.nodes.find((n) => n.id === id)
      if (!node) return
      node.x = x
      node.y = y
      if (node.serverId) await api.updateNode(node.serverId, { x, y })
    },

    async deleteNode(id) {
      const node = this.nodes.find((n) => n.id === id)
      this.nodes = this.nodes.filter((n) => n.id !== id)
      this.edges = this.edges.filter((e) => e.source !== id && e.target !== id)
      if (this.selectedNodeId === id) this.selectedNodeId = null
      if (this.editingNodeId === id) this.editingNodeId = null
      if (node?.serverId) await api.deleteNode(node.serverId)
    },

    // --- edges ---
    async addEdge(sourceId, targetId) {
      if (sourceId === targetId) return
      if (this.edges.some((e) => e.source === sourceId && e.target === targetId)) return
      const source = this.nodes.find((n) => n.id === sourceId)
      const target = this.nodes.find((n) => n.id === targetId)
      if (!source?.serverId || !target?.serverId) return
      const saved = await api.createEdge({ source_id: source.serverId, target_id: target.serverId })
      this.edges.push({ id: saved.id, source: sourceId, target: targetId })
    },

    async deleteEdge(id) {
      this.edges = this.edges.filter((e) => e.id !== id)
      await api.deleteEdge(id)
    },

    // --- live events from the agent's websocket ---
    applyThinking({ tempId, x, y }) {
      this.nodes.push({ id: tempId, serverId: null, content: '', x, y, createdBy: 'agent', thinking: true, justPlaced: false })
    },

    applyPlaced({ tempId, node }) {
      const local = this.nodes.find((n) => n.id === tempId)
      if (!local) return
      local.serverId = node.id
      local.content = node.content
      local.x = node.x
      local.y = node.y
      local.thinking = false
      local.justPlaced = true
      setTimeout(() => { local.justPlaced = false }, 900)
    },

    applyUpdated({ node }) {
      const local = this.byServerId(node.id)
      if (!local) return
      local.content = node.content
      local.x = node.x
      local.y = node.y
    },

    applyDeleted({ id }) {
      const local = this.byServerId(id)
      if (!local) return
      this.nodes = this.nodes.filter((n) => n.id !== local.id)
      this.edges = this.edges.filter((e) => e.source !== local.id && e.target !== local.id)
    },

    applyEdgeAdded({ edge }) {
      if (this.edges.some((e) => e.id === edge.id)) return
      this.edges.push(this._edgeFromServer(edge))
    },
  },
})
