import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'skretch_token'
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const useAuthStore = defineStore('auth', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const token = ref(localStorage.getItem(STORAGE_KEY) || null)
  const user  = ref(null)   // { id, email, name, avatar_url }

  // ── Getters ────────────────────────────────────────────────────────────────
  const isLoggedIn = computed(() => !!token.value)

  // ── Actions ────────────────────────────────────────────────────────────────

  /** Kick off the Google OAuth redirect */
  function loginWithGoogle() {
    window.location.href = `${BASE}/api/auth/google`
    console.log(window.localtion.href)
  }

  /**
   * Called by the router after Google redirects back with ?token=<jwt>.
   * Persists the token and fetches the user profile.
   */
  async function handleCallback(jwt) {
    token.value = jwt
    localStorage.setItem(STORAGE_KEY, jwt)
    await fetchMe()
  }

  /** Load /auth/me using the stored token (called on app boot if token exists) */
  async function fetchMe() {
    if (!token.value) return
    try {
      const res = await fetch(`${BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      if (!res.ok) {
        // Token is stale / invalid — clear it
        logout()
        return
      }
      user.value = await res.json()
    } catch {
      // Network error — leave token in place, retry next boot
    }
  }

  function logout() {
    token.value = null
    user.value  = null
    localStorage.removeItem(STORAGE_KEY)
  }

  // Hydrate user info when the store is first created (page refresh)
  if (token.value && !user.value) {
    fetchMe()
  }

  return { token, user, isLoggedIn, loginWithGoogle, handleCallback, fetchMe, logout }
})
