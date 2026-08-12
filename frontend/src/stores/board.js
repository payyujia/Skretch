import { defineStore } from 'pinia'
import * as api from '../api/client'
import { nextPosition, defaultSpawnPosition } from '../utils/layout'
import { nodeTypeMeta } from '../utils/nodeTypes'

let seq = 0
const clientId = (prefix) => `${prefix}-${++seq}-${Math.random().toString(36).slice(2, 7)}`

// Node types that toggle between an edit state and a rendered/preview state
// (and so benefit from starting in edit mode right after creation). Image
// and frame don't have that toggle — their inputs are always live, so each
// of those focuses its own first input on mount instead; see their
// onMounted hooks.
const EDIT_ON_CREATE_TYPES = new Set(['document'])

/**
 * Every node keeps a permanent client-side `id` (used as the vue-flow key)
 * plus a `serverId` that's null until the backend has confirmed it. This
 * means creating a node, editing it, and having it synced never causes a
 * re-key/remount — it just fills in `serverId` in place.
 *
 * Grouping is done via `parentId`: a node with `type: 'frame'` is a
 * container, and any node whose `parentId` equals a frame's client `id` is
 * a member of it. There's no separate edge/link concept anymore — frames
 * are the only relationship the board (or the agent) has.
 *
 * 1 creation path:createnodeoftype
 */
export const useBoardStore = defineStore('board', {
  state: () => ({
    nodes: [],
    selectedNodeId: null,
    editingNodeId: null,
    past: [],
    future: [],
  }),

  getters: {
    selectedNode: (state) => state.nodes.find((n) => n.id === state.selectedNodeId) || null,
    byServerId: (state) => (serverId) => state.nodes.find((n) => n.serverId === serverId),
    childrenOf: (state) => (frameId) => state.nodes.filter((n) => n.parentId === frameId),
    canUndo: (state) => state.past.length > 0,
    canRedo: (state) => state.future.length > 0,
  },

  actions: {
    async fetchBoard() {
      const board = await api.getBoard()
      const byServerId = new Map()
      const withoutParent = board.nodes.map((n) => {
        const local = { ...n, serverId: n.id, parentId: null, thinking: false, justPlaced: false }
        byServerId.set(n.id, local)
        return local
      })
      // parent_id from the server refers to another node's *server* id — resolve
      // it to that node's local client id, same indirection serverId already
      // handles for everything else.
      for (const n of withoutParent) {
        n.parentId = n.parent_id ? (byServerId.get(n.parent_id)?.id ?? null) : null
      }
      this.nodes = withoutParent
    },

    setContentLocal(id, content) {
      const node = this.nodes.find((n) => n.id === id)
      if (node) node.content = content
    },

    /** Empty content discards the node (a blank note isn't worth keeping);
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
        const parent = node.parentId ? this.nodes.find((n) => n.id === node.parentId) : null
        const saved = await api.createNode({
          type: node.type, content: trimmed, data: node.data || {},
          x: node.x, y: node.y, created_by: node.createdBy,
          parent_id: parent?.serverId ?? null,
        })
        node.serverId = saved.id
      } else {
        await api.updateNode(node.serverId, { content: trimmed })
      }
    },

    // --- every other node type: create immediately with real data ---
    async createNodeOfType(type, x, y, createdBy = 'user', parentId = null) {
      this.checkpoint()
      const data = nodeTypeMeta(type).defaultData()
      return this._createFullNode(type, x, y, data, createdBy, parentId)
    },

    async _createFullNode(type, x, y, data, createdBy, parentId) {
      const parent = parentId ? this.nodes.find((n) => n.id === parentId) : null
      const saved = await api.createNode({
        type, content: '', data, x, y, created_by: createdBy,
        parent_id: parent?.serverId ?? null,
      })
      const id = clientId(type)
      this.nodes.push({ id, serverId: saved.id, type, content: saved.content, data: saved.data, x, y, parentId: parentId ?? null, createdBy, thinking: false, justPlaced: false })
      this.selectedNodeId = id
      if (EDIT_ON_CREATE_TYPES.has(type)) this.editingNodeId = id
      return id
    },

    async updateNodeContent(id, content) {
      const node = this.nodes.find((n) => n.id === id)
      if (!node) return
      node.content = content
      if (node.serverId) await api.updateNode(node.serverId, { content })
    },

    /** Shallow-merges `patch` into the node's data and persists the merged result. */
    async updateNodeData(id, patch) {
      const node = this.nodes.find((n) => n.id === id)
      if (!node) return
      node.data = { ...node.data, ...patch }
      if (node.serverId) await api.updateNode(node.serverId, { data: node.data })
    },

    /** Move a node into a frame, or pass `null` to pop it out to the top
     * level. `set_parent_id: true` is required by the backend to distinguish
     * "change parent to null" from "don't touch parent" on a PATCH. */
    async reparentNode(id, frameId) {
      const node = this.nodes.find((n) => n.id === id)
      if (!node) return
      const frame = frameId ? this.nodes.find((n) => n.id === frameId) : null
      node.parentId = frame?.id ?? null
      if (node.serverId) {
        await api.updateNode(node.serverId, { parent_id: frame?.serverId ?? null, set_parent_id: true })
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
      // Deleting a frame shouldn't take its contents with it — orphan children
      // back to the top level locally too, matching the backend's behavior.
      for (const child of this.nodes.filter((n) => n.parentId === id)) {
        child.parentId = null
      }
      this.nodes = this.nodes.filter((n) => n.id !== id)
      if (this.selectedNodeId === id) this.selectedNodeId = null
      if (this.editingNodeId === id) this.editingNodeId = null
      if (node?.serverId) await api.deleteNode(node.serverId)
    },

    // --- live events from the agent's websocket ---
    applyThinking({ tempId, x, y, parentId = null }) {
      this.nodes.push({ id: tempId, serverId: null, type: 'note', content: '', data: {}, x, y, parentId, createdBy: 'agent', thinking: true, justPlaced: false })
    },

    applyPlaced({ tempId, node }) {
      const local = this.nodes.find((n) => n.id === tempId)
      if (!local) return
      local.serverId = node.id
      local.type = node.type
      local.content = node.content
      local.data = node.data
      local.x = node.x
      local.y = node.y
      local.parentId = node.parent_id ? (this.byServerId(node.parent_id)?.id ?? null) : null
      local.thinking = false
      local.justPlaced = true
      setTimeout(() => { local.justPlaced = false }, 900)
    },

    applyUpdated({ node }) {
      const local = this.byServerId(node.id)
      if (!local) return
      local.content = node.content
      local.data = node.data
      local.x = node.x
      local.y = node.y
      local.parentId = node.parent_id ? (this.byServerId(node.parent_id)?.id ?? null) : null
    },

    applyDeleted({ id }) {
      const local = this.byServerId(id)
      if (!local) return
      for (const child of this.nodes.filter((n) => n.parentId === local.id)) {
        child.parentId = null
      }
      this.nodes = this.nodes.filter((n) => n.id !== local.id)
    },

    // --- undo / redo ---
    // Call checkpoint() right before a user-initiated mutation. Undo/redo then
    // reconciles toward a saved snapshot by replaying the same create/update/
    // delete actions used everywhere else, so the backend never drifts out of
    // sync with what's on screen. Strokes need no special case here anymore —
    // they're just nodes, so the same node-reconcile logic covers them.
    checkpoint() {
      this.past.push(this._snapshot())
      if (this.past.length > 40) this.past.shift()
      this.future = []
    },

    _snapshot() {
      return {
        nodes: this.nodes.map((n) => ({
          id: n.id, type: n.type, content: n.content,
          data: JSON.parse(JSON.stringify(n.data || {})),
          x: n.x, y: n.y, parentId: n.parentId, createdBy: n.createdBy,
        })),
      }
    },

    async undo() {
      if (!this.past.length) return
      const target = this.past.pop()
      this.future.push(this._snapshot())
      await this._reconcile(target)
    },

    async redo() {
      if (!this.future.length) return
      const target = this.future.pop()
      this.past.push(this._snapshot())
      await this._reconcile(target)
    },

    async _reconcile(target) {
      const targetNodeIds = new Set(target.nodes.map((n) => n.id))
      for (const n of [...this.nodes]) {
        if (!targetNodeIds.has(n.id)) await this.deleteNode(n.id)
      }
      // Two passes: create/patch content+position first so every target node
      // has a serverId, then reconcile parentId — a node can be reparented to
      // a frame that was itself just (re)created in this same pass.
      for (const tn of target.nodes) {
        const existing = this.nodes.find((n) => n.id === tn.id)
        if (!existing) {
          const saved = await api.createNode({
            type: tn.type, content: tn.content, data: tn.data, x: tn.x, y: tn.y, created_by: tn.createdBy,
          })
          this.nodes.push({
            id: tn.id, serverId: saved.id, type: tn.type, content: tn.content, data: tn.data,
            x: tn.x, y: tn.y, parentId: null, createdBy: tn.createdBy, thinking: false, justPlaced: false,
          })
        } else {
          if (existing.content !== tn.content) {
            existing.content = tn.content
            if (existing.serverId) await api.updateNode(existing.serverId, { content: tn.content })
          }
          if (JSON.stringify(existing.data) !== JSON.stringify(tn.data)) {
            existing.data = tn.data
            if (existing.serverId) await api.updateNode(existing.serverId, { data: tn.data })
          }
          if (existing.x !== tn.x || existing.y !== tn.y) {
            existing.x = tn.x
            existing.y = tn.y
            if (existing.serverId) await api.updateNode(existing.serverId, { x: tn.x, y: tn.y })
          }
        }
      }
      for (const tn of target.nodes) {
        const existing = this.nodes.find((n) => n.id === tn.id)
        if (existing && existing.parentId !== tn.parentId) {
          await this.reparentNode(existing.id, tn.parentId)
        }
      }
    },
  },
})