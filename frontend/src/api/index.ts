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
    console.log('[chatStream] 开始请求, request:', request)
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      console.error('[chatStream] 请求失败:', response.status)
      callbacks.onError?.(`请求失败: ${response.status}`)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      console.error('[chatStream] 无法获取 reader')
      callbacks.onError?.('无法获取响应流')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    // 解析单个事件块的辅助函数
    const processEventBlock = (eventBlock: string) => {
      if (!eventBlock.trim()) return

      let eventType = 'message'
      let eventData = ''

      const lines = eventBlock.split('\n')
      for (const line of lines) {
        const trimmedLine = line.trim()
        if (trimmedLine.startsWith('event:')) {
          eventType = trimmedLine.substring(6).trim()
        } else if (trimmedLine.startsWith('data:')) {
          eventData = trimmedLine.substring(5).trim()
        }
      }

      if (!eventData) return

      try {
        const data = JSON.parse(eventData)

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
      } catch (parseError) {
        console.error('[chatStream] JSON 解析失败:', parseError, 'eventData:', eventData)
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()

        if (value) {
          buffer += decoder.decode(value, { stream: true })

          // SSE 格式: 每个事件块以 \n\n 结尾
          // 我们需要正确分割事件块
          // 事件块格式: event: xxx\ndata: yyy\n\n
          let endIndex: number
          while ((endIndex = buffer.indexOf('\n\n')) !== -1) {
            const eventBlock = buffer.substring(0, endIndex)
            buffer = buffer.substring(endIndex + 2)
            processEventBlock(eventBlock)
          }
        }

        if (done) {
          // 处理剩余的 buffer（可能有不完整的事件）
          if (buffer.trim()) {
            processEventBlock(buffer)
          }
          break
        }
      }
    } catch (error: any) {
      console.error('[chatStream] 读取错误:', error)
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