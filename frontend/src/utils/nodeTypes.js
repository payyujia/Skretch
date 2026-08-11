import { StickyNote, Frame, Image } from 'lucide-vue-next'

export const NODE_TYPES = [
  { type: 'sticky', label: 'Sticky note', icon: StickyNote, defaultData: () => ({}) },
  { type: 'frame', label: 'Frame', icon: Frame, defaultData: () => ({}) },
  { type: 'image', label: 'Image', icon: Image, defaultData: () => ({ image: null, caption: '', embedding: null }) },
]

export const nodeTypeMeta = (type) => NODE_TYPES.find((t) => t.type === type) || NODE_TYPES[0]
