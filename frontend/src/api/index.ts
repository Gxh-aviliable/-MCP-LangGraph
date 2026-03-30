import axios from 'axios'

const API_BASE = 'http://localhost:8000/api'

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

export const api = {
  // 创建旅行规划
  async createPlan(request: PlanRequest) {
    const response = await axios.post(`${API_BASE}/plan`, request)
    return response.data
  },

  // 提交反馈
  async submitFeedback(request: FeedbackRequest) {
    const response = await axios.post(`${API_BASE}/feedback`, request)
    return response.data
  },

  // 获取当前行程
  async getPlan(sessionId: string) {
    const response = await axios.get(`${API_BASE}/plan/${sessionId}`)
    return response.data
  }
}