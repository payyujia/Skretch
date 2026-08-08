const GRID = 40
const DOWN_STEP = 150
const SIDE_STEP = 260

export function defaultSpawnPosition() {
  return { x: 120, y: 120 }
}

/** Offsets a new node from `origin` in the given direction, nudging past
 * anything already occupying that spot instead of stacking nodes exactly. */
export function nextPosition(origin, direction, existingNodes) {
  const occupied = new Set(existingNodes.map((n) => key(n.x, n.y)))
  let x = direction === 'side' ? origin.x + SIDE_STEP : origin.x
  let y = direction === 'side' ? origin.y : origin.y + DOWN_STEP

  let hops = 0
  while (occupied.has(key(x, y)) && hops < 15) {
    if (direction === 'side') x += SIDE_STEP
    else y += DOWN_STEP
    hops += 1
  }
  return { x, y }
}

function key(x, y) {
  return `${Math.round(x / GRID)},${Math.round(y / GRID)}`
}
