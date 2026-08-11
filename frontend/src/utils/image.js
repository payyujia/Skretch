const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif']
const MAX_BYTES = 8 * 1024 * 1024

/** Fast client-side check before spending a round trip on an upload the
 * server will reject anyway. Returns an error string, or null if valid. */
export function validateImageFile(file) {
  if (!ALLOWED_TYPES.includes(file.type)) return 'Use PNG, JPEG, WEBP, or GIF.'
  if (file.size > MAX_BYTES) return 'Image is too large — max 8MB.'
  return null
}
