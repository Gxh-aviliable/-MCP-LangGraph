<template>
  <div class="chat-interface">
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
      <div v-if="loading" class="message assistant">
        <div class="message-content">
          <div class="message-avatar">🤖</div>
          <div class="message-text loading">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
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
          :disabled="loading || stage === 'done'"
        />
        <button
          @click="sendMessage"
          :disabled="!userInput.trim() || loading || stage === 'done'"
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
const sessionId = ref<string | null>(null)
const stage = ref<string>('greeting')
const collectedInfo = ref<CollectedInfo | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)

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
  if (saved) {
    try {
      const data = JSON.parse(saved)
      if (data.sessionId && Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
        // 会话有效（24小时内）
        sessionId.value = data.sessionId

        // 获取会话状态
        const status = await api.getChatStatus(data.sessionId)
        if (status.success) {
          stage.value = status.stage
          // 不恢复历史消息，让用户重新开始对话
        } else {
          // 会话已过期，清除
          clearSession()
        }
      } else {
        clearSession()
      }
    } catch {
      clearSession()
    }
  }
}

// 保存会话
function saveSession() {
  if (sessionId.value) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      sessionId: sessionId.value,
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
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 发送消息
async function sendMessage() {
  const message = userInput.value.trim()
  if (!message || loading.value || stage.value === 'done') return

  // 添加用户消息
  messages.value.push({ role: 'user', content: message })
  userInput.value = ''
  scrollToBottom()

  loading.value = true

  try {
    const response: ChatResponse = await api.chat({
      session_id: sessionId.value || undefined,
      message
    })

    if (response.success) {
      // 更新会话 ID
      sessionId.value = response.session_id
      stage.value = response.stage
      collectedInfo.value = response.collected_info
      saveSession()

      // 添加助手消息
      const assistantMessage: Message = {
        role: 'assistant',
        content: response.reply
      }

      // 如果有行程，附加到消息
      if (response.plan) {
        assistantMessage.plan = response.plan
      }

      messages.value.push(assistantMessage)

      // 如果完成，清除会话
      if (response.stage === 'done') {
        setTimeout(() => {
          clearSession()
        }, 3000)
      }
    } else {
      messages.value.push({
        role: 'assistant',
        content: response.reply || '抱歉，发生了错误，请重试。'
      })
    }
  } catch (error: any) {
    messages.value.push({
      role: 'assistant',
      content: '网络错误，请检查连接后重试。'
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// 初始化
onMounted(async () => {
  await loadSavedSession()

  // 如果是新会话，获取问候消息
  if (!sessionId.value) {
    loading.value = true
    try {
      const response = await api.chat({ message: '' })
      if (response.success) {
        sessionId.value = response.session_id
        stage.value = response.stage
        messages.value.push({
          role: 'assistant',
          content: response.reply
        })
        saveSession()
      }
    } catch {
      messages.value.push({
        role: 'assistant',
        content: '您好！我是旅行规划助手，可以帮您规划行程。请告诉我您想去哪里旅行？'
      })
    } finally {
      loading.value = false
      scrollToBottom()
    }
  } else {
    // 恢复会话时显示提示
    messages.value.push({
      role: 'assistant',
      content: '欢迎回来！请继续告诉我您的旅行需求。'
    })
    scrollToBottom()
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