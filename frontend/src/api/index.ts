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
  agent_mode?: 'smart' | 'react'  // Agent模式：smart(智能规划)/react(ReAct推理)
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

// SSE 事件回调
export interface StreamCallbacks {
  onSession?: (sessionId: string) => void
  onMessage?: (content: string) => void
  onStage?: (stage: string, collectedInfo: CollectedInfo | null, missingFields: string[]) => void
  onPlan?: (plan: any) => void
  onError?: (message: string) => void
  onDone?: () => void
}

// ===================== API 函数 =====================

export const api = {
  // 对话式 API
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await axios.post(`${API_BASE}/chat`, request)
    return response.data
  },

  // 流式对话 API
  async chatStream(request: ChatRequest, callbacks: StreamCallbacks): Promise<void> {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      callbacks.onError?.(`请求失败: ${response.status}`)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      callbacks.onError?.('无法获取响应流')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // 解析 SSE 事件
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''  // 保留不完整的部分

        for (const line of lines) {
          if (!line.trim()) continue

          const eventMatch = line.match(/^event:\s*(\w+)\ndata:\s*(.+)$/s)
          if (eventMatch) {
            const eventType = eventMatch[1]
            const data = JSON.parse(eventMatch[2])

            switch (eventType) {
              case 'session':
                callbacks.onSession?.(data.session_id)
                break
              case 'message':
                callbacks.onMessage?.(data.content)
                break
              case 'stage':
                callbacks.onStage?.(data.stage, data.collected_info, data.missing_fields || [])
                break
              case 'plan':
                callbacks.onPlan?.(data.plan)
                break
              case 'error':
                callbacks.onError?.(data.message)
                break
              case 'done':
                callbacks.onDone?.()
                break
            }
          }
        }
      }
    } catch (error: any) {
      callbacks.onError?.(error.message || '流式读取错误')
    }
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