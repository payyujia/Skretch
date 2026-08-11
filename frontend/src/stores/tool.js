import { defineStore } from 'pinia'

export const useToolStore = defineStore('tool', {
  state: () => ({
    active: 'select', // 'select' | 'nodes' 
    pendingNodeType: null, // node type to place next, while active === 'nodes'
    chatOpen: false,
  }),

  actions: {
    setSelect() {
      this.active = 'select'
      this.pendingNodeType = null
    },
    pickNodeType(type) {
      this.active = 'nodes'
      this.pendingNodeType = type
    },
    toggleChat() {
      this.chatOpen = !this.chatOpen
    },
  },
})
