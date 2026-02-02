import axios from 'axios'

const API_BASE_URL = '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000 // 5分钟超时
})

export const setupInterceptors = () => {
  api.interceptors.response.use(
    response => response,
    error => {
      if (error.response?.status === 503) {
        console.error('服务不可用，请稍后重试')
      }
      return Promise.reject(error)
    }
  )
}

// API 接口
export const tripAPI = {
  // 获取热门城市
  getCities: () => api.get('/cities'),
  
  // 获取兴趣分类
  getInterests: () => api.get('/interests'),
  
  // 获取住宿类型
  getAccommodationTypes: () => api.get('/accommodation-types'),
  
  // 生成旅行计划
  planTrip: (data) => api.post('/plan', data),
  
  // 健康检查
  healthCheck: () => api.get('/health')
}

// WebSocket 连接
export const createWebSocketConnection = (onMessage) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/plan`
  
  const ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log('WebSocket 已连接')
  }
  
  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      onMessage(message)
    } catch (e) {
      console.error('WebSocket 消息解析失败:', e)
    }
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket 错误:', error)
  }
  
  ws.onclose = () => {
    console.log('WebSocket 已断开')
  }
  
  return ws
}
