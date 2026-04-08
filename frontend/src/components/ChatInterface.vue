<template>
  <div class="chat-interface">
    <!-- 模式切换 -->
    <div class="mode-switch">
      <span class="mode-label">规划模式：</span>
      <button
        :class="['mode-btn', { active: agentMode === 'smart' }]"
        @click="switchMode('smart')"
        title="高效流水线模式，快速生成行程"
      >
        智能模式
      </button>
      <button
        :class="['mode-btn', { active: agentMode === 'react' }]"
        @click="switchMode('react')"
        title="ReAct推理模式，动态决策更智能"
      >
        ReAct 模式
      </button>
      <button
        v-if="sessionId"
        class="mode-btn new-session-btn"
        @click="startNewSession"
        title="清除当前对话，开始新会话"
      >
        重新开始
      </button>
    </div>

    <!-- 消息列表 -->
    <div class="messages-container" ref="messagesContainer">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message', msg.role]"
      >
        <div class="message-content">
          <div class="message-avatar">
            {{ msg.role === 'user' ? '👤' : '🤖' }}
          </div>
          <div class="message-text">
            {{ msg.content }}
          </div>
        </div>

        <!-- 行程卡片 -->
        <div v-if="msg.plan" class="plan-card">
          <PlanCard :plan="msg.plan" />
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading && !streaming" class="message assistant">
        <div class="message-content">
          <div class="message-avatar">🤖</div>
          <div class="message-text loading">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>

      <!-- 流式输出状态 -->
      <div v-if="streaming" class="message assistant">
        <div class="message-content">
          <div class="message-avatar">🤖</div>
          <div class="message-text streaming">
            {{ streamingContent || '正在思考...' }}
            <span class="streaming-indicator">▊</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-wrapper">
        <input
          v-model="userInput"
          @keyup.enter="sendMessage"
          placeholder="输入您的旅行需求..."
          :disabled="loading || streaming || stage === 'done'"
        />
        <button
          @click="sendMessage"
          :disabled="!userInput.trim() || loading || streaming || stage === 'done'"
        >
          发送
        </button>
      </div>

      <!-- 快捷回复提示 -->
      <div v-if="quickReplies.length > 0" class="quick-replies">
        <span
          v-for="(reply, index) in quickReplies"
          :key="index"
          @click="userInput = reply; sendMessage()"
          class="quick-reply"
        >
          {{ reply }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { api, type ChatResponse, type Message, type CollectedInfo } from '../api'
import PlanCard from './PlanCard.vue'

// 状态
const messages = ref<Message[]>([])
const userInput = ref('')
const loading = ref(false)
const streaming = ref(false)  // 流式输出状态
const streamingContent = ref('')  // 流式输出的临时内容
const sessionId = ref<string | null>(null)
const stage = ref<string>('greeting')
const collectedInfo = ref<CollectedInfo | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const agentMode = ref<'smart' | 'react'>('smart')  // Agent 模式

// localStorage 键名
const STORAGE_KEY = 'travel_chat_session'

// 快捷回复
const quickReplies = computed(() => {
  if (stage.value === 'collecting') {
    return ['北京', '上海', '杭州', '下周出发', '玩3天']
  }
  if (stage.value === 'confirming') {
    return ['是的，生成吧', '再想想']
  }
  if (stage.value === 'refining') {
    return ['确认满意', '第一天景点太多', '换个便宜的酒店']
  }
  return []
})

// 加载保存的会话
async function loadSavedSession() {
  const saved = localStorage.getItem(STORAGE_KEY)
  console.log('[loadSavedSession] saved:', saved)

  if (saved) {
    try {
      const data = JSON.parse(saved)
      console.log('[loadSavedSession] parsed data:', data)

      // 检查时间戳是否在24小时内
      if (data.sessionId && Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
        // 先验证会话是否有效
        try {
          console.log('[loadSavedSession] checking session:', data.sessionId)
          const status = await api.getChatStatus(data.sessionId)
          console.log('[loadSavedSession] status response:', status)

          if (status.success) {
            // 会话有效，恢复
            sessionId.value = data.sessionId
            stage.value = status.stage
            // 恢复之前选择的模式
            if (data.agentMode) {
              agentMode.value = data.agentMode
            }
            console.log('[loadSavedSession] session restored, mode:', agentMode.value)
          } else {
            // 会话已过期，清除
            console.log('[loadSavedSession] session expired, clearing')
            clearSession()
          }
        } catch (e) {
          // 网络错误或其他问题，清除旧会话
          console.error('[loadSavedSession] error checking session:', e)
          clearSession()
        }
      } else {
        // 时间过期或无 sessionId，清除
        console.log('[loadSavedSession] timestamp expired or no sessionId, clearing')
        clearSession()
      }
    } catch (e) {
      console.error('[loadSavedSession] parse error:', e)
      clearSession()
    }
  } else {
    console.log('[loadSavedSession] no saved session')
  }
}

// 保存会话
function saveSession() {
  if (sessionId.value) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      sessionId: sessionId.value,
      agentMode: agentMode.value,
      timestamp: Date.now()
    }))
  }
}

// 清除会话
function clearSession() {
  sessionId.value = null
  localStorage.removeItem(STORAGE_KEY)
  messages.value = []
  stage.value = 'greeting'
  collectedInfo.value = null
  // 不重置 agentMode，保留用户选择的模式
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 切换模式（会清除当前会话）
async function switchMode(mode: 'smart' | 'react') {
  if (agentMode.value === mode) return

  // 如果有进行中的会话，提示用户
  if (sessionId.value && stage.value !== 'done') {
    if (!confirm('切换模式将清除当前对话，确定要切换吗？')) {
      return
    }
  }

  agentMode.value = mode
  console.log('[Mode] 切换到', mode, '模式')
  await createNewSession()
}

// 重新开始新会话
async function startNewSession() {
  if (sessionId.value && stage.value !== 'done') {
    if (!confirm('确定要重新开始吗？当前对话将被清除。')) {
      return
    }
  }
  await createNewSession()
}

// 创建新会话（使用流式输出）
async function createNewSession() {
  clearSession()
  streaming.value = true
  streamingContent.value = ''
  loading.value = true

  try {
    await api.chatStream(
      { message: '', agent_mode: agentMode.value },
      {
        onSession: (sid) => {
          sessionId.value = sid
          saveSession()
          console.log('[Session] 新会话已创建，模式:', agentMode.value)
        },
        onMessage: (content) => {
          streamingContent.value = content
          messages.value = [{
            role: 'assistant',
            content: content
          }]
          scrollToBottom()
        },
        onStage: (newStage, collected, missing) => {
          stage.value = newStage
        },
        onError: (errorMsg) => {
          streaming.value = false
          streamingContent.value = ''
          loading.value = false
          messages.value.push({
            role: 'assistant',
            content: '抱歉，创建会话失败，请重试。'
          })
          scrollToBottom()
        },
        onDone: () => {
          streaming.value = false
          streamingContent.value = ''
          loading.value = false
          scrollToBottom()
        }
      }
    )
  } catch (error) {
    console.error('[Session] 创建新会话失败:', error)
    streaming.value = false
    streamingContent.value = ''
    loading.value = false
    messages.value.push({
      role: 'assistant',
      content: '抱歉，创建会话失败，请重试。'
    })
    scrollToBottom()
  }
}

// 发送消息（使用流式输出）
async function sendMessage() {
  const message = userInput.value.trim()
  if (!message || loading.value || streaming.value || stage.value === 'done') return

  // 添加用户消息
  messages.value.push({ role: 'user', content: message })
  userInput.value = ''
  scrollToBottom()

  // 开始流式输出
  streaming.value = true
  streamingContent.value = ''
  loading.value = true

  // 临时消息索引（用于流式更新）
  let tempMessageIndex = -1

  try {
    await api.chatStream(
      {
        session_id: sessionId.value || undefined,
        message,
        agent_mode: agentMode.value
      },
      {
        onSession: (sid) => {
          sessionId.value = sid
          saveSession()
        },
        onMessage: (content) => {
          // 第一次收到消息时，添加临时消息
          if (tempMessageIndex === -1) {
            messages.value.push({
              role: 'assistant',
              content: ''
            })
            tempMessageIndex = messages.value.length - 1
          }
          // 更新消息内容
          streamingContent.value = content
          if (tempMessageIndex >= 0) {
            messages.value[tempMessageIndex].content = content
          }
          scrollToBottom()
        },
        onStage: (newStage, collected, missing) => {
          stage.value = newStage
          collectedInfo.value = collected
        },
        onPlan: (plan) => {
          // 如果有行程，附加到最后一条消息
          if (tempMessageIndex >= 0) {
            messages.value[tempMessageIndex].plan = plan
          }
        },
        onError: (errorMsg) => {
          streaming.value = false
          streamingContent.value = ''
          messages.value.push({
            role: 'assistant',
            content: `抱歉，发生了错误：${errorMsg}`
          })
          scrollToBottom()
        },
        onDone: () => {
          streaming.value = false
          streamingContent.value = ''
          loading.value = false

          // 如果完成，清除会话
          if (stage.value === 'done') {
            setTimeout(() => {
              clearSession()
            }, 3000)
          }
          scrollToBottom()
        }
      }
    )
  } catch (error: any) {
    streaming.value = false
    streamingContent.value = ''
    loading.value = false
    messages.value.push({
      role: 'assistant',
      content: '网络错误，请检查连接后重试。'
    })
    scrollToBottom()
  }
}

// 初始化
onMounted(async () => {
  console.log('[onMounted] starting initialization...')
  loading.value = true

  try {
    await loadSavedSession()
    console.log('[onMounted] loadSavedSession done, sessionId:', sessionId.value)

    // 如果是新会话，获取问候消息（使用流式输出）
    if (!sessionId.value) {
      console.log('[onMounted] fetching greeting via stream...')
      streaming.value = true
      streamingContent.value = ''

      await api.chatStream(
        { message: '', agent_mode: agentMode.value },
        {
          onSession: (sid) => {
            sessionId.value = sid
            saveSession()
            console.log('[onMounted] session created:', sid)
          },
          onMessage: (content) => {
            streamingContent.value = content
            messages.value = [{
              role: 'assistant',
              content: content
            }]
          },
          onStage: (newStage) => {
            stage.value = newStage
          },
          onError: (errorMsg) => {
            console.error('[onMounted] stream error:', errorMsg)
            streaming.value = false
            streamingContent.value = ''
            loading.value = false
            messages.value.push({
              role: 'assistant',
              content: '您好！我是旅行规划助手，可以帮您规划行程。请告诉我您想去哪里旅行？'
            })
          },
          onDone: () => {
            streaming.value = false
            streamingContent.value = ''
            loading.value = false
            console.log('[onMounted] greeting displayed')
            scrollToBottom()
          }
        }
      )
    } else {
      // 恢复会话时显示提示
      console.log('[onMounted] restoring session')
      loading.value = false
      messages.value.push({
        role: 'assistant',
        content: '欢迎回来！请继续告诉我您的旅行需求。'
      })
      scrollToBottom()
    }
  } catch (error) {
    console.error('[onMounted] initialization error:', error)
    streaming.value = false
    streamingContent.value = ''
    loading.value = false
    messages.value.push({
      role: 'assistant',
      content: '您好！我是旅行规划助手，可以帮您规划行程。请告诉我您想去哪里旅行？'
    })
    clearSession()
    scrollToBottom()
  } finally {
    console.log('[onMounted] initialization complete')
  }
})

// 监听消息变化，滚动到底部
watch(messages, scrollToBottom, { deep: true })
</script>

<style scoped>
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 900px;
  margin: 0 auto;
  background: #fff;
}

/* 模式切换样式 */
.mode-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
}

.mode-label {
  font-size: 14px;
  color: #666;
}

.mode-btn {
  padding: 8px 16px;
  border: 1px solid #ddd;
  border-radius: 20px;
  background: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:hover:not(:disabled) {
  border-color: #3498db;
  background: #ecf5ff;
}

.mode-btn.active {
  background: #3498db;
  color: white;
  border-color: #3498db;
}

.mode-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mode-btn.new-session-btn {
  margin-left: 16px;
  background: #e74c3c;
  color: white;
  border-color: #e74c3c;
}

.mode-btn.new-session-btn:hover {
  background: #c0392b;
  border-color: #c0392b;
}

.mode-hint {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message.user {
  align-items: flex-end;
}

.message.assistant {
  align-items: flex-start;
}

.message-content {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: 80%;
}

.message.user .message-content {
  flex-direction: row-reverse;
}

.message-avatar {
  font-size: 24px;
  line-height: 1;
}

.message-text {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.5;
}

.message.user .message-text {
  background: #3498db;
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-text {
  background: #f1f3f4;
  color: #333;
  border-bottom-left-radius: 4px;
}

.message-text.loading {
  display: flex;
  gap: 4px;
  padding: 16px 20px;
}

.dot {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* 流式输出样式 */
.message-text.streaming {
  position: relative;
}

.streaming-indicator {
  animation: blink 1s infinite;
  color: #3498db;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.plan-card {
  max-width: 90%;
  margin-top: 8px;
}

.input-area {
  padding: 16px 20px;
  border-top: 1px solid #eee;
  background: #fafafa;
}

.input-wrapper {
  display: flex;
  gap: 12px;
}

.input-wrapper input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #ddd;
  border-radius: 24px;
  font-size: 15px;
  outline: none;
}

.input-wrapper input:focus {
  border-color: #3498db;
}

.input-wrapper input:disabled {
  background: #f5f5f5;
}

.input-wrapper button {
  padding: 12px 24px;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 24px;
  font-size: 15px;
  cursor: pointer;
  transition: background 0.2s;
}

.input-wrapper button:hover:not(:disabled) {
  background: #2980b9;
}

.input-wrapper button:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
}

.quick-replies {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.quick-reply {
  padding: 6px 14px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 16px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-reply:hover {
  border-color: #3498db;
  background: #ecf5ff;
}
</style>