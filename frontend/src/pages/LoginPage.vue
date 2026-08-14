<script setup>
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="login-root">
    <!-- LEFT — brand panel -->
    <div class="brand-panel">
      <!-- scanline texture overlay -->
      <div class="scanlines" aria-hidden="true" />
      <!-- grid dots decoration -->
      <div class="grid-dots" aria-hidden="true" />

      <div class="brand-inner">
        <div class="wordmark">
          <span class="wordmark-sk">SK</span><span class="wordmark-retch">RETCH</span>
        </div>

        <p class="tagline">
          <span class="cursor-blink">_</span> Cast a wider net.
        </p>

        <div class="feature-list" aria-label="Feature highlights">
          <div class="feature-item">
            <span class="feature-bullet">&#x25B6;</span>
            AI-powered infinite canvas
          </div>
          <div class="feature-item">
            <span class="feature-bullet">&#x25B6;</span>
            Real-time multiplayer boards
          </div>
          <div class="feature-item">
            <span class="feature-bullet">&#x25B6;</span>
            Export to Google Docs &amp; Slides
          </div>
        </div>

        <!-- decorative ticker -->
        <div class="ticker" aria-hidden="true">
          <span class="ticker-track">
            BRAINSTORM &nbsp;&#x2022;&nbsp; RESEARCH &nbsp;&#x2022;&nbsp;
            COLLABORATE &nbsp;&#x2022;&nbsp; EXPORT &nbsp;&#x2022;&nbsp;
            BRAINSTORM &nbsp;&#x2022;&nbsp; RESEARCH &nbsp;&#x2022;&nbsp;
            COLLABORATE &nbsp;&#x2022;&nbsp; EXPORT &nbsp;&#x2022;&nbsp;
          </span>
        </div>

        <p class="copyright">&#xa9; 2026 SKRETCH &mdash; ALL RIGHTS RESERVED</p>
      </div>
    </div>

    <!-- RIGHT — login card -->
    <div class="auth-panel">
      <div class="auth-card">
        <!-- card header stamp -->
        <div class="card-stamp">&#x25A0; SECURE SIGN-IN</div>

        <h1 class="card-title">Welcome back.</h1>
        <p class="card-subtitle">
          Sign in to access your boards and continue where you left off.
        </p>

        <div class="divider-rule" />

        <!-- Google login button -->
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

        <!-- cosmetic divider -->
        <div class="or-divider">
          <span class="or-line" /><span class="or-text">OR</span><span class="or-line" />
        </div>

        <!-- static guest button — cosmetic only -->
        <button class="btn-guest" disabled aria-disabled="true">
          Continue as Guest <span class="coming-soon">COMING SOON</span>
        </button>

        <p class="legal-note">
          By signing in you agree to our
          <a href="#" class="legal-link">Terms of Service</a> and
          <a href="#" class="legal-link">Privacy Policy</a>.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Import retro fonts ──────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;600;700&display=swap');

/* ── Root layout: full-viewport split ──────────────────────────────────── */
.login-root {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  font-family: 'IBM Plex Mono', monospace;
}

/* ═══════════════════ LEFT — BRAND PANEL ══════════════════════════════════ */
.brand-panel {
  position: relative;
  flex: 0 0 55%;
  background: #0d0d0d;
  color: #f5f0e8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* Scanlines overlay */
.scanlines {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    to bottom,
    transparent,
    transparent 2px,
    rgba(255, 255, 255, 0.025) 2px,
    rgba(255, 255, 255, 0.025) 4px
  );
  pointer-events: none;
  z-index: 1;
}

/* Dot grid decoration (bottom-right quadrant) */
.grid-dots {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 260px;
  height: 260px;
  background-image: radial-gradient(circle, rgba(255,255,255,0.12) 1px, transparent 1px);
  background-size: 20px 20px;
  pointer-events: none;
  z-index: 1;
}

.brand-inner {
  position: relative;
  z-index: 2;
  padding: 48px;
  max-width: 520px;
}

/* Wordmark */
.wordmark {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 72px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
  margin-bottom: 24px;
  user-select: none;
}
.wordmark-sk     { color: #2f5fe0; }
.wordmark-retch  { color: #f5f0e8; }

/* Tagline */
.tagline {
  font-size: 18px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--border-strong);
  margin-bottom: 36px;
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #2f5fe0;
  font-weight: 700;
}
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* Feature list */
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 48px;
}
.feature-item {
  font-size: 13px;
  color: #9ca3af;
  letter-spacing: 0.05em;
}
.feature-bullet {
  color: #2f5fe0;
  margin-right: 10px;
  font-size: 10px;
}

/* Scrolling ticker tape */
.ticker {
  overflow: hidden;
  border-top: 1px solid rgba(255,255,255,0.1);
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding: 8px 0;
  margin-bottom: 24px;
}
.ticker-track {
  display: inline-block;
  white-space: nowrap;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: rgba(245, 240, 232, 0.35);
  animation: ticker-scroll 18s linear infinite;
}
@keyframes ticker-scroll {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}

/* Copyright */
.copyright {
  font-size: 10px;
  letter-spacing: 0.1em;
  color: rgba(245, 240, 232, 0.25);
  margin: 0;
}

/* ═══════════════════ RIGHT — AUTH PANEL ══════════════════════════════════ */
.auth-panel {
  flex: 1;
  background: #faf7f2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

/* Card */
.auth-card {
  width: 100%;
  max-width: 380px;
  background: #f5f0e8;
  border: 2px solid #1a1a1a;
  border-radius: 2px;
  padding: 40px 36px;
  position: relative;
  /* subtle drop-shadow for paper depth */
  box-shadow: 4px 4px 0 #1a1a1a;
}

/* Stamp label in corner */
.card-stamp {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--muted);
  background: #e8e2d8;
  border: 1px solid #c5bfb3;
  display: inline-block;
  padding: 3px 8px;
  margin-bottom: 20px;
}

.card-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 30px;
  font-weight: 700;
  color: #0d0d0d;
  margin: 0 0 8px 0;
  line-height: 1.1;
}

.card-subtitle {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 24px 0;
  line-height: 1.5;
}

.divider-rule {
  height: 1px;
  background: #1a1a1a;
  margin-bottom: 24px;
}

/* Google button */
.btn-google {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  padding: 13px 20px;
  background: #0d0d0d;
  color: #f5f0e8;
  border: 2px solid #0d0d0d;
  border-radius: 2px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, transform 0.1s ease;
  box-shadow: 3px 3px 0 var(--muted);
}
.btn-google:hover {
  background: #1a1a1a;
  transform: translate(-1px, -1px);
  box-shadow: 4px 4px 0 var(--muted);
}
.btn-google:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--muted);
}
.google-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* OR divider */
.or-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px 0;
}
.or-line {
  flex: 1;
  height: 1px;
  background: #c5bfb3;
}
.or-text {
  font-size: 11px;
  letter-spacing: 0.1em;
  color: #9ca3af;
}

/* Guest button (cosmetic/disabled) */
.btn-guest {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 12px 20px;
  background: transparent;
  color: #9ca3af;
  border: 2px dashed #c5bfb3;
  border-radius: 2px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  letter-spacing: 0.03em;
  cursor: not-allowed;
  margin-bottom: 20px;
}
.coming-soon {
  font-size: 9px;
  letter-spacing: 0.1em;
  background: #e8e2d8;
  border: 1px solid #c5bfb3;
  padding: 2px 6px;
  color: var(--muted);
}

/* Legal note */
.legal-note {
  font-size: 11px;
  color: #9ca3af;
  text-align: center;
  line-height: 1.6;
  margin: 0;
}
.legal-link {
  color: #2f5fe0;
  text-decoration: underline;
}

/* ── Responsive: stack on narrow screens ── */
@media (max-width: 768px) {
  .login-root { flex-direction: column; }
  .brand-panel { flex: 0 0 35%; }
  .wordmark { font-size: 48px; }
}
</style>
