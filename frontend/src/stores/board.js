import { defineStore } from 'pinia'
import * as api from '../api/client'
import { nextPosition, defaultSpawnPosition } from '../utils/layout'
import { nodeTypeMeta } from '../utils/nodeTypes'

let seq = 0
const clientId = (prefix) => `${prefix}-${++seq}-${Math.random().toString(36).slice(2, 7)}`

const EDIT_ON_CREATE_TYPES = new Set(['document'])

/**
 * Single point of truth for turning a raw node — from the REST response
 * (`fetchBoard`) or a WS event (`applyPlaced`/`applyUpdated`) — into the
 * shape the store/components use. Backend fields may arrive snake_case or
 * camelCase depending on the path; normalise here
 * 
 * state = reactive data (like Vue's data())
 * getters = derived/computed values (like computed)
 * actions = methods (like methods, can be async, can mutate state)
 */
function normalizeNode(raw) {
  return {
    id: raw.id,
    type: raw.type,
    content: raw.content,
    data: raw.data || {},
    x: raw.x,
    y: raw.y,
    createdBy: raw.createdBy ?? raw.created_by,
    parentServerId: raw.parentId ?? raw.parent_id ?? null,
  }
}

export const useBoardStore = defineStore('board', {
  state: () => ({
    nodes: [],
    selectedNodeId: null,
    editingNodeId: null,
    past: [],
    future: [],
    currentBoardId: null,
    currentBoardName: '',
    presence: {},
  }),

  getters: {
    selectedNode: (state) => state.nodes.find((n) => n.id === state.selectedNodeId) || null,
    byServerId: (state) => (serverId) => state.nodes.find((n) => n.serverId === serverId),
    childrenOf: (state) => (frameId) => state.nodes.filter((n) => n.parentId === frameId),
    canUndo: (state) => state.past.length > 0,
    canRedo: (state) => state.future.length > 0,
  },

  actions: {
    async fetchBoard(boardId) {
      const id = boardId ?? this.currentBoardId
      if (!id) throw new Error('fetchBoard: no boardId provided')
      if (boardId) this.currentBoardId = boardId
      const board = await api.getBoard(id)
      this.currentBoardName = board.name ?? ''

      const byServerId = new Map()
      const localNodes = board.nodes.map((raw) => {
        const n = normalizeNode(raw)
        const local = {
          id: n.id, serverId: n.id, type: n.type, content: n.content, data: n.data,
          x: n.x, y: n.y, parentId: null, createdBy: n.createdBy,
          thinking: false, justPlaced: false,
          _parentServerId: n.parentServerId, // resolved below, then dropped
        }
        byServerId.set(n.id, local)
        return local
      })
      for (const local of localNodes) {
        local.parentId = local._parentServerId ? (byServerId.get(local._parentServerId)?.id ?? null) : null
        delete local._parentServerId
      }
      this.nodes = localNodes
    },

    setContentLocal(id, content) {
      const node = this.nodes.find((n) => n.id === id)
      if (node) node.content = content
    },

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
        }, this.currentBoardId)
        node.serverId = saved.id
      } else {
        await api.updateNode(node.serverId, { content: trimmed })
      }
    },

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
      }, this.currentBoardId)
      // WS broadcast may have inserted this node before the HTTP response arrived
      const existing = this.byServerId(saved.id)
      if (existing) {
        this.selectedNodeId = existing.id
        if (EDIT_ON_CREATE_TYPES.has(type)) this.editingNodeId = existing.id
        return existing.id
      }
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

    async updateNodeData(id, patch) {
      const node = this.nodes.find((n) => n.id === id)
      if (!node) return
      node.data = { ...node.data, ...patch }
      if (node.serverId) await api.updateNode(node.serverId, { data: node.data })
    },

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
      for (const child of this.nodes.filter((n) => n.parentId === id)) {
        child.parentId = null
      }
      this.nodes = this.nodes.filter((n) => n.id !== id)
      if (this.selectedNodeId === id) this.selectedNodeId = null
      if (this.editingNodeId === id) this.editingNodeId = null
      if (node?.serverId) await api.deleteNode(node.serverId)
    },

    // --- live events from the agent's / presence websocket ---
    applyThinking({ tempId, x, y, parentId = null, nodeType = 'sticky' }) {
      this.nodes.push({ id: tempId, serverId: null, type: nodeType, content: '', data: {}, x, y, parentId, createdBy: 'agent', thinking: true, justPlaced: false })
    },

    applyPlaced({ tempId, node }) {
      const n = normalizeNode(node)

      let local = tempId ? this.nodes.find((x) => x.id === tempId) : null
      if (!local) local = this.byServerId(n.id) // dedupe self-originated broadcast echoes
      if (!local) {
        local = {
          id: clientId(n.type), serverId: null, type: n.type, content: '',
          data: {}, x: n.x, y: n.y, parentId: null,
          createdBy: n.createdBy, thinking: false, justPlaced: false,
        }
        this.nodes.push(local)
      }

      local.serverId = n.id
      local.type = n.type
      local.content = n.content
      local.data = n.data
      local.x = n.x
      local.y = n.y
      local.parentId = n.parentServerId ? (this.byServerId(n.parentServerId)?.id ?? null) : null
      local.thinking = false
      local.justPlaced = true
      local.createdBy = n.createdBy ?? local.createdBy
      setTimeout(() => { local.justPlaced = false }, 900)
    },

    applyUpdated({ node }) {
      const n = normalizeNode(node)
      const local = this.byServerId(n.id)
      if (!local) return
      local.content = n.content
      local.data = n.data
      local.x = n.x
      local.y = n.y
      local.parentId = n.parentServerId ? (this.byServerId(n.parentServerId)?.id ?? null) : null
      local.createdBy = n.createdBy ?? local.createdBy
    },

    applyDeleted({ id }) {
      const local = this.byServerId(id)
      if (!local) return
      for (const child of this.nodes.filter((n) => n.parentId === local.id)) {
        child.parentId = null
      }
      this.nodes = this.nodes.filter((n) => n.id !== local.id)
    },

    // --- presence ---
    applyPresence(users) {
      const map = {}
      for (const u of users) map[u.userId] = u
      this.presence = map
    },

    clearPresence() {
      this.presence = {}
    },

    setBoardMeta(boardId, boardName) {
      this.currentBoardId = boardId
      if (boardName != null) this.currentBoardName = boardName
    },

    // --- undo / redo ---
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
      for (const tn of target.nodes) {
        const existing = this.nodes.find((n) => n.id === tn.id)
        if (!existing) {
          const saved = await api.createNode({
            type: tn.type, content: tn.content, data: tn.data, x: tn.x, y: tn.y, created_by: tn.createdBy,
          }, this.currentBoardId)
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