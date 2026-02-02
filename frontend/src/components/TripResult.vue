<template>
  <div class="trip-result">
    <div class="result-header">
      <h2>✨ 行程规划完成</h2>
      <el-button @click="handleReset" type="primary" plain>
        🔄 重新规划
      </el-button>
    </div>

    <div v-if="tripPlan" class="result-content">
      <!-- 基本信息 -->
      <el-card class="info-card">
        <template #header>
          <div class="card-header">
            <span>📍 行程概览</span>
          </div>
        </template>

        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">目的地</div>
            <div class="info-value">{{ tripPlan.city }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">出发日期</div>
            <div class="info-value">{{ tripPlan.start_date }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">返回日期</div>
            <div class="info-value">{{ tripPlan.end_date }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">行程天数</div>
            <div class="info-value">{{ tripPlan.days?.length || 0 }} 天</div>
          </div>
        </div>

        <!-- 总体建议 -->
        <div class="suggestions" v-if="tripPlan.overall_suggestions">
          <h4>💡 总体建议</h4>
          <p>{{ tripPlan.overall_suggestions }}</p>
        </div>
      </el-card>

      <!-- 预算信息 -->
      <el-card class="budget-card" v-if="tripPlan.budget">
        <template #header>
          <div class="card-header">
            <span>💰 预算分析</span>
          </div>
        </template>

        <div class="budget-breakdown">
          <div class="budget-item">
            <span class="budget-label">景点门票</span>
            <span class="budget-value">¥ {{ tripPlan.budget.total_attractions?.toLocaleString() || 0 }}</span>
          </div>
          <div class="budget-item">
            <span class="budget-label">酒店住宿</span>
            <span class="budget-value">¥ {{ tripPlan.budget.total_hotels?.toLocaleString() || 0 }}</span>
          </div>
          <div class="budget-item">
            <span class="budget-label">餐饮消费</span>
            <span class="budget-value">¥ {{ tripPlan.budget.total_meals?.toLocaleString() || 0 }}</span>
          </div>
          <div class="budget-item">
            <span class="budget-label">交通运输</span>
            <span class="budget-value">¥ {{ tripPlan.budget.total_transportation?.toLocaleString() || 0 }}</span>
          </div>
          <div class="budget-item total">
            <span class="budget-label">总预算</span>
            <span class="budget-value">¥ {{ tripPlan.budget.total?.toLocaleString() || 0 }}</span>
          </div>
        </div>

        <!-- 预算图表 -->
        <div class="budget-chart">
          <div class="chart-item" :style="{ width: getPercentage('attractions') + '%' }">
            <span class="chart-label">景点</span>
          </div>
          <div class="chart-item hotels" :style="{ width: getPercentage('hotels') + '%' }">
            <span class="chart-label">酒店</span>
          </div>
          <div class="chart-item meals" :style="{ width: getPercentage('meals') + '%' }">
            <span class="chart-label">餐饮</span>
          </div>
          <div class="chart-item transport" :style="{ width: getPercentage('transportation') + '%' }">
            <span class="chart-label">交通</span>
          </div>
        </div>
      </el-card>

      <!-- 天气预报 -->
      <el-card class="weather-card" v-if="tripPlan.weather_info?.length > 0">
        <template #header>
          <div class="card-header">
            <span>🌤️ 天气预报</span>
          </div>
        </template>

        <div class="weather-grid">
          <div
            v-for="weather in tripPlan.weather_info"
            :key="weather.date"
            class="weather-item"
          >
            <div class="weather-date">{{ formatDate(weather.date) }}</div>
            <div class="weather-icon">{{ getWeatherIcon(weather.day_weather) }}</div>
            <div class="weather-desc">{{ weather.day_weather }}</div>
            <div class="weather-temp">
              <span class="day-temp">{{ weather.day_temp }}°</span>
              <span class="night-temp">{{ weather.night_temp }}°</span>
            </div>
            <div class="weather-wind">
              <div>{{ weather.wind_direction }}</div>
              <div>{{ weather.wind_power }}</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 每日行程 -->
      <div class="days-container">
        <el-card
          v-for="(day, index) in tripPlan.days"
          :key="index"
          class="day-card"
        >
          <template #header>
            <div class="card-header">
              <span class="day-title">第 {{ day.day_index + 1 }} 天 - {{ day.date }}</span>
              <span class="day-date">{{ formatDate(day.date) }}</span>
            </div>
          </template>

          <div class="day-content">
            <!-- 行程描述 -->
            <div class="day-description">
              <h4>📝 行程安排</h4>
              <p>{{ day.description }}</p>
            </div>

            <!-- 景点 -->
            <div class="day-section" v-if="day.attractions?.length > 0">
              <h4>🎯 景点推荐</h4>
              <div class="attractions-list">
                <div
                  v-for="(attraction, aIndex) in day.attractions"
                  :key="aIndex"
                  class="attraction-item"
                >
                  <div class="attraction-number">{{ aIndex + 1 }}</div>
                  <div class="attraction-details">
                    <div class="attraction-name">{{ attraction.name }}</div>
                    <div class="attraction-address">📍 {{ attraction.address }}</div>
                    <div class="attraction-info">
                      <el-tag>游览时间: {{ attraction.visit_duration }}分钟</el-tag>
                      <el-tag v-if="attraction.ticket_price > 0">门票: ¥{{ attraction.ticket_price }}</el-tag>
                      <el-tag v-if="attraction.rating">评分: {{ attraction.rating }}分</el-tag>
                    </div>
                    <div v-if="attraction.description" class="attraction-desc">
                      {{ attraction.description }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 酒店 -->
            <div class="day-section" v-if="day.hotel">
              <h4>🏨 住宿安排</h4>
              <el-card class="hotel-card">
                <div class="hotel-name">{{ day.hotel.name }}</div>
                <div class="hotel-detail">
                  <div class="detail-item">
                    <span class="detail-label">地址:</span>
                    <span>{{ day.hotel.address }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">评分:</span>
                    <span>{{ day.hotel.rating }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">价格:</span>
                    <span>{{ day.hotel.price_range }} (约¥{{ day.hotel.estimated_cost }}/晚)</span>
                  </div>
                  <div class="detail-item" v-if="day.hotel.distance">
                    <span class="detail-label">距景点:</span>
                    <span>{{ day.hotel.distance }}</span>
                  </div>
                </div>
              </el-card>
            </div>

            <!-- 餐饮 -->
            <div class="day-section" v-if="day.meals?.length > 0">
              <h4>🍽️ 美食推荐</h4>
              <div class="meals-grid">
                <div
                  v-for="meal in day.meals"
                  :key="meal.type"
                  class="meal-item"
                >
                  <div class="meal-icon">{{ getMealIcon(meal.type) }}</div>
                  <div class="meal-type">{{ getMealTypeName(meal.type) }}</div>
                  <div class="meal-name">{{ meal.name }}</div>
                  <div v-if="meal.estimated_cost" class="meal-cost">
                    约 ¥{{ meal.estimated_cost }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 交通与住宿 -->
            <div class="day-footer">
              <div class="footer-item" v-if="day.transportation">
                <span class="footer-label">🚗 交通:</span>
                <span>{{ day.transportation }}</span>
              </div>
              <div class="footer-item" v-if="day.accommodation">
                <span class="footer-label">🏩 住宿:</span>
                <span>{{ day.accommodation }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 导出按钮 -->
      <div class="export-buttons">
        <el-button type="success" @click="handleExportJSON">
          📥 导出为 JSON
        </el-button>
        <el-button type="primary" @click="handlePrint">
          🖨️ 打印行程
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useTripStore } from '../stores/tripStore'
import { ElMessage } from 'element-plus'

const store = useTripStore()

const tripPlan = computed(() => store.tripPlan)

// 方法
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekDay = weekDays[date.getDay()]
  return `${dateStr} ${weekDay}`
}

const getWeatherIcon = (weather) => {
  const icons = {
    '晴': '☀️',
    '阴': '☁️',
    '雨': '🌧️',
    '雪': '❄️',
    '多云': '⛅',
    '小雨': '🌦️',
    '大雨': '⛈️',
    '阵雨': '🌧️'
  }
  return icons[weather] || '🌤️'
}

const getMealIcon = (type) => {
  const icons = {
    'breakfast': '🥐',
    'lunch': '🍜',
    'dinner': '🍽️',
    'snack': '🍰'
  }
  return icons[type] || '🍽️'
}

const getMealTypeName = (type) => {
  const names = {
    'breakfast': '早餐',
    'lunch': '午餐',
    'dinner': '晚餐',
    'snack': '小食'
  }
  return names[type] || type
}

const getPercentage = (type) => {
  const budget = tripPlan.value.budget
  const total = budget.total || 1
  let value = 0

  if (type === 'attractions') value = budget.total_attractions || 0
  else if (type === 'hotels') value = budget.total_hotels || 0
  else if (type === 'meals') value = budget.total_meals || 0
  else if (type === 'transportation') value = budget.total_transportation || 0

  return Math.max((value / total) * 100, 5) // 最少显示 5%
}

const handleReset = () => {
  store.resetForm()
}

const handleExportJSON = () => {
  const dataStr = JSON.stringify(tripPlan.value, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)
  const link = document.createElement('a')
  link.href = url
  link.download = `trip-plan-${tripPlan.value.city}-${tripPlan.value.start_date}.json`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

const handlePrint = () => {
  window.print()
  ElMessage.success('打开打印对话框')
}
</script>

<style scoped>
.trip-result {
  padding: 30px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #eee;
}

.result-header h2 {
  font-size: 24px;
  color: #333;
  margin: 0;
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.info-card,
.budget-card,
.weather-card,
.day-card {
  border: 1px solid #eee;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

/* 基本信息卡片 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.info-item {
  text-align: center;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.info-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 5px;
}

.info-value {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.suggestions {
  margin-top: 20px;
  padding: 15px;
  background: #e6f7ff;
  border-left: 4px solid #1890ff;
  border-radius: 4px;
}

.suggestions h4 {
  margin: 0 0 10px 0;
  color: #1890ff;
}

.suggestions p {
  margin: 0;
  color: #333;
  line-height: 1.6;
}

/* 预算卡片 */
.budget-breakdown {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.budget-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.budget-item.total {
  background: #e6f7ff;
  border-left: 4px solid #1890ff;
  font-weight: bold;
}

.budget-label {
  color: #666;
}

.budget-value {
  font-size: 16px;
  font-weight: bold;
  color: #f56c6c;
}

.budget-chart {
  display: flex;
  gap: 2px;
  height: 30px;
  background: #f5f7fa;
  border-radius: 4px;
  overflow: hidden;
}

.chart-item {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  min-width: 40px;
}

.chart-item.hotels {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.chart-item.meals {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.chart-item.transport {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.chart-label {
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* 天气卡片 */
.weather-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 15px;
}

.weather-item {
  text-align: center;
  padding: 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 8px;
  transition: transform 0.3s ease;
}

.weather-item:hover {
  transform: translateY(-5px);
}

.weather-date {
  font-size: 12px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.weather-icon {
  font-size: 32px;
  margin: 5px 0;
}

.weather-desc {
  font-size: 14px;
  font-weight: bold;
  margin: 5px 0;
}

.weather-temp {
  display: flex;
  justify-content: center;
  gap: 10px;
  font-size: 14px;
  margin: 8px 0;
}

.day-temp {
  color: #ff6b6b;
}

.night-temp {
  color: #4dabf7;
}

.weather-wind {
  font-size: 12px;
  opacity: 0.8;
  line-height: 1.4;
}

/* 每日行程卡片 */
.days-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.day-title {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.day-date {
  font-size: 14px;
  color: #999;
}

.day-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.day-description {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.day-description h4 {
  margin: 0 0 10px 0;
  color: #333;
}

.day-description p {
  margin: 0;
  color: #666;
  line-height: 1.6;
}

.day-section {
  border-top: 1px solid #eee;
  padding-top: 15px;
}

.day-section h4 {
  margin: 0 0 15px 0;
  color: #333;
}

/* 景点列表 */
.attractions-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.attraction-item {
  display: flex;
  gap: 15px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.attraction-number {
  width: 30px;
  height: 30px;
  min-width: 30px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-weight: bold;
}

.attraction-details {
  flex: 1;
}

.attraction-name {
  font-size: 16px;
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}

.attraction-address {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.attraction-info {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.attraction-desc {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  margin-top: 8px;
}

/* 酒店卡片 */
.hotel-card {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  border: none;
}

.hotel-name {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 15px;
}

.hotel-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-item {
  display: flex;
  gap: 10px;
}

.detail-label {
  font-weight: bold;
  min-width: 60px;
}

/* 餐饮网格 */
.meals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 15px;
}

.meal-item {
  text-align: center;
  padding: 15px;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
  border-radius: 8px;
  transition: transform 0.3s ease;
}

.meal-item:hover {
  transform: scale(1.05);
}

.meal-icon {
  font-size: 32px;
  margin-bottom: 5px;
}

.meal-type {
  font-size: 12px;
  opacity: 0.9;
  margin-bottom: 5px;
}

.meal-name {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 5px;
}

.meal-cost {
  font-size: 12px;
  opacity: 0.9;
}

/* 页脚 */
.day-footer {
  display: flex;
  gap: 20px;
  padding: 15px;
  background: #fafafa;
  border-radius: 4px;
  border-left: 3px solid #67c23a;
}

.footer-item {
  display: flex;
  gap: 8px;
  color: #333;
}

.footer-label {
  font-weight: bold;
  color: #666;
}

/* 导出按钮 */
.export-buttons {
  display: flex;
  gap: 15px;
  justify-content: center;
  margin-top: 30px;
  padding-top: 30px;
  border-top: 2px solid #eee;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .trip-result {
    padding: 15px;
  }

  .result-header {
    flex-direction: column;
    gap: 15px;
  }

  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .weather-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .meals-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .attraction-item {
    flex-direction: column;
  }

  .export-buttons {
    flex-direction: column;
  }
}

@media print {
  .result-header,
  .export-buttons {
    display: none;
  }

  .day-card {
    page-break-inside: avoid;
  }
}
</style>
