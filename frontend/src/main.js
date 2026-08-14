import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/controls/dist/style.css'
import './style.css'
import App from './App.vue'

createApp(App).use(createPinia()).use(router).mount('#app')
