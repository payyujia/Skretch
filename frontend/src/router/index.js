import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// Lazy-load pages so the canvas bundle isn't pulled on the login page
const LoginPage      = () => import('../pages/LoginPage.vue')
const BoardsMenuPage = () => import('../pages/BoardsMenuPage.vue')
const Canvas  = () => import('../pages/Canvas.vue')

const routes = [
  {
    path: '/',
    name: 'login',
    component: LoginPage,
    meta: { public: true },
  },
  {
    path: '/boards',
    name: 'boards',
    component: BoardsMenuPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/board/:id',
    name: 'canvas',
    component: Canvas,
    props: (route) => ({ boardId: Number(route.params.id) }),
    meta: { requiresAuth: true },
  },
  // Catch-all → back to root
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ── Navigation guard ──────────────────────────────────────────────────────────
router.beforeEach((to) => {
  const auth = useAuthStore()

  // Handle OAuth callback: /?token=<jwt>
  if (to.path === '/' && to.query.token) {
    auth.handleCallback(to.query.token)
    return { name: 'boards', replace: true }
  }

  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login' }
  }

  // Already logged in, don't show login page again
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'boards' }
  }
})

export default router
