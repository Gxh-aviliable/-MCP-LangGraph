import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'

import App from './App.vue'
import { setupInterceptors } from './utils/api'

const app = createApp(App)

app.use(ElementPlus)
app.use(createPinia())

// 设置 axios 拦截器
setupInterceptors()

app.mount('#app')
