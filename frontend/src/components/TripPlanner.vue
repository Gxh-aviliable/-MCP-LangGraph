<template>
  <div class="trip-planner">
    <h1>🌍 旅行规划助手</h1>

    <!-- 输入表单 -->
    <div class="form-section" v-if="!currentPlan">
      <div class="form-group">
        <label>城市</label>
        <input v-model="form.city" placeholder="例如：北京" />
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>开始日期</label>
          <input type="date" v-model="form.start_date" />
        </div>
        <div class="form-group">
          <label>结束日期</label>
          <input type="date" v-model="form.end_date" />
        </div>
      </div>

      <div class="form-group">
        <label>兴趣偏好 (逗号分隔)</label>
        <input v-model="interestsInput" placeholder="例如：历史古迹, 美食" />
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>住宿类型 (可选)</label>
          <input v-model="form.accommodation_type" placeholder="例如：中档酒店" />
        </div>
        <div class="form-group">
          <label>每日预算 (可选)</label>
          <input type="number" v-model.number="form.budget_per_day" placeholder="例如：500" />
        </div>
      </div>

      <button @click="createPlan" :disabled="loading" class="btn-primary">
        {{ loading ? '规划中...' : '开始规划' }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div class="loading" v-if="loading">
      <div class="spinner"></div>
      <p>正在为您规划行程，请稍候...</p>
    </div>

    <!-- 错误提示 -->
    <div class="error" v-if="error">
      <p>❌ {{ error }}</p>
      <button @click="error = null" class="btn-secondary">关闭</button>
    </div>

    <!-- 规划结果 -->
    <div class="plan-result" v-if="currentPlan && !loading">
      <div class="plan-header">
        <h2>📋 {{ currentPlan.city }} 旅行计划</h2>
        <p>{{ currentPlan.start_date }} 至 {{ currentPlan.end_date }}</p>
      </div>

      <!-- 每日行程 -->
      <div class="days-container">
        <div class="day-card" v-for="day in currentPlan.days" :key="day.day_index">
          <div class="day-header">
            <span class="day-badge">第 {{ day.day_index + 1 }} 天</span>
            <span class="day-date">{{ day.date }}</span>
          </div>
          <p class="day-desc">{{ day.description }}</p>

          <!-- 景点 -->
          <div class="section">
            <h4>🏞️ 景点</h4>
            <div class="attraction" v-for="attr in day.attractions" :key="attr.name">
              <div class="attraction-name">{{ attr.name }}</div>
              <div class="attraction-info">
                <span>📍 {{ attr.address }}</span>
                <span>⏱️ {{ attr.visit_duration }}分钟</span>
                <span>🎫 ¥{{ attr.ticket_price }}</span>
              </div>
            </div>
          </div>

          <!-- 餐饮 -->
          <div class="section" v-if="day.meals?.length">
            <h4>🍽️ 餐饮</h4>
            <div class="meal" v-for="meal in day.meals" :key="meal.type">
              <span class="meal-type">{{ mealTypeLabel(meal.type) }}</span>
              <span class="meal-name">{{ meal.name }}</span>
              <span class="meal-cost">¥{{ meal.estimated_cost }}</span>
            </div>
          </div>

          <!-- 酒店 -->
          <div class="section" v-if="day.hotel">
            <h4>🏨 酒店</h4>
            <div class="hotel">
              <div class="hotel-name">{{ day.hotel.name }}</div>
              <div class="hotel-info">
                <span>{{ day.hotel.address }}</span>
                <span>{{ day.hotel.price_range }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 天气信息 -->
      <div class="weather-section" v-if="currentPlan.weather_info?.length">
        <h3>🌤️ 天气预报</h3>
        <div class="weather-cards">
          <div class="weather-card" v-for="w in currentPlan.weather_info" :key="w.date">
            <div class="weather-date">{{ w.date }}</div>
            <div class="weather-main">
              <span class="weather-icon">{{ getWeatherIcon(w.day_weather) }}</span>
              <span>{{ w.day_weather }}</span>
            </div>
            <div class="weather-temp">
              {{ w.night_temp }}°C ~ {{ w.day_temp }}°C
            </div>
            <div class="weather-wind">{{ w.wind_direction }}风 {{ w.wind_power }}</div>
          </div>
        </div>
      </div>

      <!-- 预算 -->
      <div class="budget-section" v-if="currentPlan.budget">
        <h3>💰 预算估算</h3>
        <div class="budget-items">
          <div class="budget-item">
            <span>景点门票</span>
            <span>¥{{ currentPlan.budget.total_attractions }}</span>
          </div>
          <div class="budget-item">
            <span>酒店住宿</span>
            <span>¥{{ currentPlan.budget.total_hotels }}</span>
          </div>
          <div class="budget-item">
            <span>餐饮费用</span>
            <span>¥{{ currentPlan.budget.total_meals }}</span>
          </div>
          <div class="budget-total">
            <span>总计</span>
            <span>¥{{ currentPlan.budget.total }}</span>
          </div>
        </div>
      </div>

      <!-- 总体建议 -->
      <div class="suggestions" v-if="currentPlan.overall_suggestions">
        <h3>💡 建议</h3>
        <p>{{ currentPlan.overall_suggestions }}</p>
      </div>

      <!-- 反馈区域 -->
      <div class="feedback-section">
        <h3>💬 修改建议</h3>
        <div class="feedback-input">
          <input
            v-model="feedbackMessage"
            placeholder="例如：第一天景点有点多，酒店换个近一点的"
            @keyup.enter="submitFeedback"
          />
          <button @click="submitFeedback" :disabled="feedbackLoading" class="btn-secondary">
            {{ feedbackLoading ? '处理中...' : '提交' }}
          </button>
        </div>
        <div class="feedback-hints">
          <span @click="feedbackMessage = '确认满意'">✅ 确认满意</span>
          <span @click="feedbackMessage = '第一天景点有点多'">🗓️ 调整第一天</span>
          <span @click="feedbackMessage = '换个便宜点的酒店'">🏨 换酒店</span>
        </div>
      </div>

      <!-- 重新规划按钮 -->
      <button @click="resetPlan" class="btn-reset">重新规划</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { api, type PlanRequest } from '../api'

// 表单数据
const form = ref<PlanRequest>({
  city: '',
  start_date: '',
  end_date: '',
  interests: [],
  accommodation_type: '',
  budget_per_day: undefined,
  transportation_mode: ''
})

const interestsInput = ref('')

// 状态
const loading = ref(false)
const feedbackLoading = ref(false)
const error = ref<string | null>(null)
const sessionId = ref('')
const currentPlan = ref<any>(null)
const feedbackMessage = ref('')

// 创建规划
async function createPlan() {
  if (!form.value.city || !form.value.start_date || !form.value.end_date) {
    error.value = '请填写城市和日期'
    return
  }

  loading.value = true
  error.value = null

  try {
    // 处理兴趣偏好
    form.value.interests = interestsInput.value
      .split(/[,，]/)
      .map(s => s.trim())
      .filter(s => s)

    const result = await api.createPlan(form.value)

    if (result.success) {
      sessionId.value = result.session_id
      currentPlan.value = result.plan
    } else {
      error.value = result.error || '规划失败，请重试'
    }
  } catch (e: any) {
    error.value = e.message || '网络错误'
  } finally {
    loading.value = false
  }
}

// 提交反馈
async function submitFeedback() {
  if (!feedbackMessage.value.trim() || !sessionId.value) return

  feedbackLoading.value = true

  try {
    const result = await api.submitFeedback({
      session_id: sessionId.value,
      message: feedbackMessage.value
    })

    if (result.success) {
      currentPlan.value = result.plan
      feedbackMessage.value = ''
    } else {
      error.value = result.error || '反馈处理失败'
    }
  } catch (e: any) {
    error.value = e.message || '网络错误'
  } finally {
    feedbackLoading.value = false
  }
}

// 重置
function resetPlan() {
  currentPlan.value = null
  sessionId.value = ''
  feedbackMessage.value = ''
}

// 辅助函数
function mealTypeLabel(type: string) {
  const labels: Record<string, string> = {
    breakfast: '早餐',
    lunch: '午餐',
    dinner: '晚餐',
    snack: '小吃'
  }
  return labels[type] || type
}

function getWeatherIcon(weather: string) {
  if (weather.includes('晴')) return '☀️'
  if (weather.includes('云') || weather.includes('阴')) return '☁️'
  if (weather.includes('雨')) return '🌧️'
  if (weather.includes('雪')) return '❄️'
  return '🌤️'
}
</script>

<style scoped>
.trip-planner {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

h1 {
  text-align: center;
  color: #2c3e50;
  margin-bottom: 30px;
}

/* 表单样式 */
.form-section {
  background: #f8f9fa;
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #555;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #3498db;
  box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* 按钮 */
.btn-primary {
  width: 100%;
  padding: 12px;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #2980b9;
}

.btn-primary:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 8px 16px;
  background: #95a5a6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-reset {
  width: 100%;
  padding: 12px;
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 8px;
  margin-top: 20px;
  cursor: pointer;
}

/* 加载状态 */
.loading {
  text-align: center;
  padding: 40px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 错误提示 */
.error {
  background: #fee;
  color: #c00;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 规划结果 */
.plan-result {
  background: white;
}

.plan-header {
  text-align: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #eee;
}

.plan-header h2 {
  margin: 0;
  color: #2c3e50;
}

.plan-header p {
  color: #7f8c8d;
  margin: 8px 0 0;
}

/* 每日行程卡片 */
.days-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 24px;
}

.day-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 16px;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.day-badge {
  background: #3498db;
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.day-date {
  color: #7f8c8d;
  font-size: 14px;
}

.day-desc {
  color: #555;
  margin: 0 0 16px;
  line-height: 1.5;
}

.section {
  margin-bottom: 12px;
}

.section h4 {
  margin: 0 0 8px;
  color: #2c3e50;
  font-size: 14px;
}

.attraction, .meal, .hotel {
  background: white;
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.attraction-name, .hotel-name {
  font-weight: 500;
  color: #2c3e50;
  margin-bottom: 4px;
}

.attraction-info, .hotel-info {
  font-size: 12px;
  color: #7f8c8d;
  display: flex;
  gap: 12px;
}

.meal {
  display: flex;
  align-items: center;
  gap: 12px;
}

.meal-type {
  background: #e8f4f8;
  color: #3498db;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.meal-name {
  flex: 1;
}

.meal-cost {
  color: #e67e22;
  font-weight: 500;
}

/* 天气 */
.weather-section {
  margin-bottom: 24px;
}

.weather-section h3 {
  margin-bottom: 12px;
  color: #2c3e50;
}

.weather-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.weather-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px;
  border-radius: 10px;
  text-align: center;
}

.weather-date {
  font-size: 12px;
  opacity: 0.9;
}

.weather-icon {
  font-size: 28px;
  display: block;
  margin: 4px 0;
}

.weather-temp {
  font-size: 16px;
  font-weight: 500;
  margin: 4px 0;
}

.weather-wind {
  font-size: 12px;
  opacity: 0.9;
}

/* 预算 */
.budget-section {
  background: #f0f9eb;
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 24px;
}

.budget-section h3 {
  margin: 0 0 12px;
  color: #67c23a;
}

.budget-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.budget-item, .budget-total {
  display: flex;
  justify-content: space-between;
}

.budget-total {
  font-weight: bold;
  border-top: 1px dashed #c2e7b0;
  padding-top: 8px;
  margin-top: 4px;
}

/* 建议 */
.suggestions {
  background: #fdf6ec;
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 24px;
}

.suggestions h3 {
  margin: 0 0 8px;
  color: #e6a23c;
}

.suggestions p {
  margin: 0;
  color: #555;
  line-height: 1.6;
}

/* 反馈区域 */
.feedback-section {
  background: #f4f4f5;
  padding: 16px;
  border-radius: 12px;
}

.feedback-section h3 {
  margin: 0 0 12px;
  color: #2c3e50;
}

.feedback-input {
  display: flex;
  gap: 12px;
}

.feedback-input input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.feedback-hints {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.feedback-hints span {
  background: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid #ddd;
}

.feedback-hints span:hover {
  background: #ecf5ff;
  border-color: #3498db;
}

/* 响应式 */
@media (max-width: 600px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .weather-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>