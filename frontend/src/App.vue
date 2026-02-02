<template>
  <div class="app-container">
    <!-- 背景 -->
    <div class="background"></div>
    
    <!-- 主容器 -->
    <div class="main-content">
      <!-- 标题 -->
      <header class="header">
        <div class="header-content">
          <h1>🚀 AI 智能旅行规划助手</h1>
          <p>基于多智能体的个性化旅行规划</p>
        </div>
      </header>

      <!-- 主区域 -->
      <div class="content-wrapper">
        <!-- 左侧：表单 -->
        <div class="form-section" v-if="!showResult">
          <TripForm />
        </div>

        <!-- 右侧：结果或加载状态 -->
        <div class="result-section" v-if="showResult">
          <TripResult />
        </div>

        <!-- 全屏加载对话框 -->
        <el-dialog
          v-model="store.isLoading"
          title="正在规划行程..."
          width="600px"
          :close-on-click-modal="false"
          :close-on-press-escape="false"
          :show-close="false"
        >
          <div class="loading-dialog">
            <div class="spinner"></div>
            <p class="status-text">AI 智能体正在为您规划行程，请稍候...</p>
            
            <!-- 进度消息 -->
            <div class="progress-messages" v-if="store.progressMessages.length > 0">
              <div class="progress-item" v-for="(msg, index) in store.progressMessages" :key="index">
                <el-icon class="progress-icon">
                  <Check />
                </el-icon>
                <span>{{ msg.message || msg }}</span>
              </div>
            </div>
          </div>
        </el-dialog>

        <!-- 错误提示 -->
        <el-alert
          v-if="store.error"
          :title="store.error"
          type="error"
          closable
          @close="store.clearError"
          class="error-alert"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useTripStore } from './stores/tripStore'
import TripForm from './components/TripForm.vue'
import TripResult from './components/TripResult.vue'
import { Check } from '@element-plus/icons-vue'

const store = useTripStore()

const showResult = computed(() => {
  return store.tripPlan !== null && !store.isLoading
})
</script>

<style scoped>
.app-container {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
}

.background {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  z-index: -1;
}

.main-content {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  padding: 40px 20px;
  text-align: center;
  color: white;
}

.header-content h1 {
  font-size: 48px;
  font-weight: bold;
  margin-bottom: 10px;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
}

.header-content p {
  font-size: 18px;
  opacity: 0.9;
}

.content-wrapper {
  flex: 1;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 20px;
  display: flex;
  gap: 30px;
}

.form-section,
.result-section {
  flex: 1;
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.error-alert {
  margin-top: 20px;
}

/* 加载对话框 */
.loading-dialog {
  text-align: center;
  padding: 40px 0;
}

.spinner {
  width: 50px;
  height: 50px;
  margin: 0 auto 20px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.status-text {
  font-size: 16px;
  color: #666;
  margin: 20px 0;
}

.progress-messages {
  margin-top: 20px;
  text-align: left;
  max-height: 200px;
  overflow-y: auto;
}

.progress-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  font-size: 14px;
  color: #333;
}

.progress-icon {
  color: #67c23a;
  margin-right: 10px;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .content-wrapper {
    flex-direction: column;
  }
  
  .header-content h1 {
    font-size: 36px;
  }
  
  .header-content p {
    font-size: 16px;
  }
}

@media (max-width: 768px) {
  .header {
    padding: 20px 10px;
  }
  
  .header-content h1 {
    font-size: 28px;
  }
  
  .form-section,
  .result-section {
    padding: 20px;
  }
  
  .content-wrapper {
    padding: 10px;
    gap: 10px;
  }
}
</style>
