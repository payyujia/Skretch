<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const mode = ref('login') // 'login' | 'signup'
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref(null)
const loading = ref(false)

const isLogin = computed(() => mode.value === 'login')

function toggleMode() {
  mode.value = isLogin.value ? 'signup' : 'login'
  error.value = null
  password.value = ''
  confirmPassword.value = ''
}

async function submit() {
  error.value = null
  if (!username.value.trim() || !password.value.trim()) {
    error.value = 'Username and password are required.'
    return
  }
  if (!isLogin.value && password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.'
    return
  }
  loading.value = true
  try {
    if (isLogin.value) {
      await auth.login({ username: username.value, password: password.value })
    } else {
      await auth.register({ username: username.value, password: password.value })
    }
    router.push({ name: 'boards' })
  } catch (err) {
    error.value = err.message || (isLogin.value ? 'Login failed.' : 'Sign-up failed.')
  } finally {
    loading.value = false
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
          <h1 class="auth-title">{{ isLogin ? 'Welcome back' : 'Create account' }}</h1>
          <p class="auth-sub">
            {{
              isLogin
                ? 'Sign in to continue to your boards.'
                : 'Get started — it\'s free.'
            }}
          </p>
        </div>
        <button class="btn-google" @click="auth.loginWithGoogle()">
          <svg class="google-icon" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.35-8.16 2.35-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            <path fill="none" d="M0 0h48v48H0z"/>
          </svg>
          Continue with Google
        </button>
        <!-- Form -->
        <form class="auth-form" @submit.prevent="submit" novalidate>
          <div class="field">
            <label for="username">Username</label>
            <input
              id="username"
              v-model="username"
              type="text"
              autocomplete="username"
              placeholder="you"
              :disabled="loading"
            />
          </div>

          <div class="field">
            <label for="password">Password</label>
            <input
              id="password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              placeholder="••••••••"
              :disabled="loading"
            />
          </div>

          <div v-if="!isLogin" class="field">
            <label for="confirmPassword">Confirm password</label>
            <input
              id="confirmPassword"
              v-model="confirmPassword"
              type="password"
              autocomplete="new-password"
              placeholder="••••••••"
              :disabled="loading"
            />
          </div>

          <!-- Error -->
          <p v-if="error" class="auth-error" role="alert">{{ error }}</p>

          <!-- Submit -->
          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? '…' : isLogin ? 'Sign in' : 'Create account' }}
          </button>
        </form>

        <!-- Toggle mode -->
        <p class="toggle-row">
          {{ isLogin ? 'No account yet?' : 'Already have an account?' }}
          <button type="button" class="toggle-btn" @click="toggleMode">
            {{ isLogin ? 'Sign up' : 'Sign in' }}
          </button>
        </p>

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

/* ── Left: brand panel — intentionally empty ── */
.brand-panel {
  background: var(--canvas-bg);
}

/* ── Right: auth panel ── */
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
  gap: 28px;
}

/* ── Heading ── */
.auth-heading {
  display: flex;
  flex-direction: column;
  gap: 6px;
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

/* ── Form ── */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-family: var(--font-body);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: 0.03em;
}

.field input {
  height: 42px;
  padding: 0 14px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  background: var(--canvas-bg);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s, background 0.15s;
}

.field input:focus {
  border-color: var(--ink);
  background: var(--surface);
}

.field input:disabled {
  opacity: 0.5;
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

/* ── Submit button ── */
.submit-btn {
  height: 44px;
  width: 100%;
  border: none;
  border-radius: var(--radius);
  background: var(--ink);
  color: var(--surface);
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.88;
  transform: translateY(-1px);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  background: var(--border);
  color: var(--muted);
  cursor: not-allowed;
}

/* ── Toggle row ── */
.toggle-row {
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  margin: 0;
}

.toggle-btn {
  border: none;
  background: none;
  color: var(--user-accent);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 0 2px;
  text-decoration: underline;
  transition: color 0.15s;
}

.toggle-btn:hover {
  color: color-mix(in oklab, var(--user-accent), black 15%);
}
</style>
