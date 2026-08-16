<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const guestLoading = ref(false)
const error = ref(null)

async function handleGuestLogin() {
  error.value = null
  guestLoading.value = true
  try {
    const boardId = await auth.loginAsGuest()
    router.push(boardId ? { name: 'canvas', params: { id: boardId } } : { name: 'boards' })
  } catch (err) {
    error.value = err.message || 'Guest sign-in failed.'
  } finally {
    guestLoading.value = false
  }
}
</script>

<template>
  <div class="login-shell">

    <!-- ── Left: brand panel (intentionally empty — fill later) ── -->
    <div class="brand-panel" />

    <!-- ── Right: auth card ── -->
    <div class="auth-panel">
      <div class="auth-card">

        <!-- Card heading -->
        <div class="auth-heading">
          <h1 class="auth-title">Welcome</h1>
          <p class="auth-sub">Sign in to continue to your boards.</p>
        </div>

        <!-- Google sign-in — styled per Google Identity brand guidelines -->
        <button class="gsi-material-button" type="button" @click="auth.loginWithGoogle()">
          <div class="gsi-material-button-state" />
          <div class="gsi-material-button-content-wrapper">
            <div class="gsi-material-button-icon">
              <svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.35-8.16 2.35-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                <path fill="none" d="M0 0h48v48H0z"/>
              </svg>
            </div>
            <span class="gsi-material-button-contents">Sign in with Google</span>
          </div>
        </button>

        <!-- Divider -->
        <div class="divider-row">
          <span class="divider-line" />
          <span class="divider-text">or</span>
          <span class="divider-line" />
        </div>

        <!-- Guest sign-in -->
        <button class="guest-btn" type="button" :disabled="guestLoading" @click="handleGuestLogin">
          {{ guestLoading ? 'Entering…' : 'Sign in as guest' }}
        </button>

        <!-- Error -->
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>

      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Shell: two-column split ── */
.login-shell {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100dvh;
}

@media (max-width: 720px) {
  .login-shell {
    grid-template-columns: 1fr;
  }
  .brand-panel {
    display: none !important;
  }
}

.brand-panel {
  background: var(--canvas-bg);
}

.auth-panel {
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 28px;
  border-left: 1px solid var(--border);
}

.auth-card {
  width: 100%;
  max-width: 380px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.auth-heading {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.auth-title {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: clamp(26px, 4vw, 34px);
  color: var(--ink);
  letter-spacing: -0.01em;
  line-height: 1.1;
  margin: 0;
}

.auth-sub {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

/* ── Google button — per Google Identity Services brand guidelines ──
   https://developers.google.com/identity/branding-guidelines
   White surface, #747775 border/text, Roboto, 40px min height, 8px icon gutter. */
.gsi-material-button {
  -webkit-appearance: none;
  appearance: none;
  background-color: WHITE;
  border: 1px solid #747775;
  border-radius: 4px;
  box-sizing: border-box;
  color: #1f1f1f;
  cursor: pointer;
  font-family: Roboto, arial, sans-serif;
  font-size: 14px;
  font-weight: 500;
  height: 40px;
  letter-spacing: 0.25px;
  outline: none;
  overflow: hidden;
  padding: 0 12px;
  position: relative;
  text-align: center;
  transition: background-color .218s, border-color .218s, box-shadow .218s;
  vertical-align: middle;
  width: 100%;
}

.gsi-material-button .gsi-material-button-content-wrapper {
  align-items: center;
  display: flex;
  flex-direction: row;
  height: 100%;
  justify-content: center;
  position: relative;
  width: 100%;
}

.gsi-material-button .gsi-material-button-icon {
  height: 20px;
  margin-right: 12px;
  min-width: 20px;
  width: 20px;
}

.gsi-material-button .gsi-material-button-contents {
  flex-grow: 1;
  font-family: Roboto, arial, sans-serif;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: top;
}

.gsi-material-button .gsi-material-button-state {
  transition: opacity .218s;
  bottom: 0;
  left: 0;
  opacity: 0;
  position: absolute;
  right: 0;
  top: 0;
  background-color: #1f1f1f;
}

.gsi-material-button:hover .gsi-material-button-state {
  opacity: 4%;
}

.gsi-material-button:active .gsi-material-button-state {
  opacity: 12%;
}

.gsi-material-button:disabled {
  cursor: default;
  background-color: #ffffff61;
  border-color: #1f1f1f1f;
}

.gsi-material-button:disabled .gsi-material-button-contents,
.gsi-material-button:disabled .gsi-material-button-icon {
  opacity: 38%;
}

/* ── Divider ── */
.divider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: var(--border);
}

.divider-text {
  font-family: var(--font-body);
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Guest button ── */
.guest-btn {
  height: 44px;
  width: 100%;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  background: var(--canvas-bg);
  color: var(--ink);
  font-family: var(--font-body);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, transform 0.1s;
}

.guest-btn:hover:not(:disabled) {
  background: var(--surface);
  border-color: var(--ink);
}

.guest-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.guest-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ── Error ── */
.auth-error {
  font-family: var(--font-body);
  font-size: 12.5px;
  color: var(--danger);
  background: var(--danger-tint);
  border: 1px solid color-mix(in oklab, var(--danger), transparent 65%);
  padding: 8px 12px;
  border-radius: var(--radius);
  margin: 0;
}
</style>
