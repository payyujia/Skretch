import { StickyNote, Frame, Image } from 'lucide-vue-next'
export const colorOptions = [
  { name: 'purple', hex: 'rgb(216 180 254)' },
  { name: 'yellow', hex: 'rgb(252 211 77)' },
  { name: 'mint', hex: 'rgb(110 231 183)' },
  { name: 'blue', hex: 'rgb(125 211 252)' },
  { name: 'coral', hex: 'rgb(253 164 175)' },
]
export const NODE_TYPES = [
  { type: 'sticky', label: 'Sticky note', icon: StickyNote, defaultData: () => ({color: colorOptions.map(c=>c.name)[Math.floor(Math.random()*colorOptions.length)],reactions: {}, rotation:[-1,0,1][Math.floor(Math.random() * 3)] }) },
  { type: 'frame', label: 'Frame', icon: Frame, defaultData: () => ({color:'coral'}) },
  { type: 'image', label: 'Image', icon: Image, defaultData: () => ({ image: null, caption: '', embedding: null }) },
]
export const nodeTypeMeta = (type) => NODE_TYPES.find((t) => t.type === type) || NODE_TYPES[0]

