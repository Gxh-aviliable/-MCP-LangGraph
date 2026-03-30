import axios from 'axios'

const API_BASE = 'http://localhost:8000/api'

// ===================== 类型定义 =====================

export interface PlanRequest {
  city: string
  start_date: string
  end_date: string
  interests: string[]
  accommodation_type?: string
  budget_per_day?: number
  transportation_mode?: string
}

export interface FeedbackRequest {
  session_id: string
  message: string
}

export interface ChatRequest {
  session_id?: string
  message: string
}

export interface CollectedInfo {
  city?: string
  start_date?: string
  end_date?: string
  interests?: string[]
  budget_per_day?: number
  accommodation_type?: string
}

export interface ChatResponse {
  success: boolean
  session_id: string
  reply: string
  stage: 'greeting' | 'collecting' | 'confirming' | 'planning' | 'refining' | 'done'
  collected_info: CollectedInfo | null
  missing_fields: string[]
  plan: any | null
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  plan?: any  // 如果这条消息包含行程
}

// ===================== API 函数 =====================

export const api = {
  // 对话式 API
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await axios.post(`${API_BASE}/chat`, request)
    return response.data
  },

  // 获取会话状态
  async getChatStatus(sessionId: string) {
    const response = await axios.get(`${API_BASE}/chat/${sessionId}/status`)
    return response.data
  },

  // 创建旅行规划（兼容旧版）
  async createPlan(request: PlanRequest) {
    const response = await axios.post(`${API_BASE}/plan`, request)
    return response.data
  },

  // 提交反馈（兼容旧版）
  async submitFeedback(request: FeedbackRequest) {
    const response = await axios.post(`${API_BASE}/feedback`, request)
    return response.data
  },

  // 获取当前行程（兼容旧版）
  async getPlan(sessionId: string) {
    const response = await axios.get(`${API_BASE}/plan/${sessionId}`)
    return response.data
  }
}