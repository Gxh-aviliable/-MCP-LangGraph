<template>
  <div class="plan-card">
    <!-- 头部 -->
    <div class="plan-header">
      <h3>📋 {{ plan.city }} 旅行计划</h3>
      <p class="plan-date">{{ plan.start_date }} 至 {{ plan.end_date }}</p>
      <p v-if="plan.origin" class="plan-route">
        🚗 {{ plan.origin }} → {{ plan.city }}
      </p>
    </div>

    <!-- 黄历信息 -->
    <div v-if="plan.lucky_day_info" class="lucky-day-section">
      <div class="section-title">🏮 出行黄历</div>
      <div class="lucky-day-content">
        <div class="lunar-date">{{ plan.lucky_day_info.lunar_date || plan.lucky_day_info.date }}</div>
        <div class="suitable">
          <span class="label">宜：</span>
          <span class="tag suitable-tag" v-for="item in plan.lucky_day_info.suitable?.slice(0, 5)" :key="item">
            {{ item }}
          </span>
        </div>
        <div class="avoid" v-if="plan.lucky_day_info.avoid?.length">
          <span class="label">忌：</span>
          <span class="tag avoid-tag" v-for="item in plan.lucky_day_info.avoid?.slice(0, 3)" :key="item">
            {{ item }}
          </span>
        </div>
      </div>
    </div>

    <!-- 天气信息 -->
    <div v-if="plan.weather_info?.length" class="weather-section">
      <div class="section-title">☀️ 天气预报</div>
      <div class="weather-list">
        <div class="weather-item" v-for="weather in plan.weather_info" :key="weather.date">
          <span class="weather-date">{{ formatDate(weather.date) }}</span>
          <span class="weather-desc">{{ weather.day_weather }}</span>
          <span class="weather-temp">{{ weather.day_temp }}°/{{ weather.night_temp }}°</span>
        </div>
      </div>
    </div>

    <!-- 交通方案 -->
    <div v-if="plan.transport_options?.length" class="transport-section">
      <div class="section-title">🚄 交通方案</div>
      <div class="transport-options">
        <div
          class="transport-option"
          v-for="option in plan.transport_options"
          :key="option.type"
        >
          <div class="transport-icon">{{ getTransportIcon(option.type) }}</div>
          <div class="transport-info">
            <div class="transport-name">{{ option.name }}</div>
            <div class="transport-details">
              <span v-if="option.duration">⏱️ {{ option.duration }}</span>
              <span v-if="option.cost">💰 ¥{{ option.cost }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 每日行程 -->
    <div class="days-section">
      <div class="section-title">📅 每日行程</div>
      <div class="days-list">
        <div
          v-for="day in plan.days"
          :key="day.day_index"
          class="day-item"
        >
          <div class="day-header">
            <span class="day-badge">第 {{ day.day_index + 1 }} 天</span>
            <span class="day-date">{{ day.date }}</span>
          </div>
          <p class="day-desc">{{ day.description }}</p>

          <!-- 景点 -->
          <div class="attractions" v-if="day.attractions?.length">
            <span
              v-for="attr in day.attractions"
              :key="attr.name"
              class="attraction-tag"
            >
              📍 {{ attr.name }}
              <span v-if="attr.ticket_price" class="ticket-price">¥{{ attr.ticket_price }}</span>
            </span>
          </div>

          <!-- 住宿 -->
          <div v-if="day.hotel" class="hotel-info">
            🏨 {{ day.hotel.name }}
            <span v-if="day.hotel.price_range">（{{ day.hotel.price_range }}）</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 预算 -->
    <div class="budget-section" v-if="plan.budget">
      <div class="section-title">💰 预算估算</div>
      <div class="budget-details">
        <div class="budget-item" v-if="plan.budget.total_attractions">
          <span>门票</span>
          <span>¥{{ plan.budget.total_attractions }}</span>
        </div>
        <div class="budget-item" v-if="plan.budget.total_hotels">
          <span>住宿</span>
          <span>¥{{ plan.budget.total_hotels }}</span>
        </div>
        <div class="budget-item" v-if="plan.budget.total_meals">
          <span>餐饮</span>
          <span>¥{{ plan.budget.total_meals }}</span>
        </div>
        <div class="budget-item" v-if="plan.budget.total_transportation">
          <span>交通</span>
          <span>¥{{ plan.budget.total_transportation }}</span>
        </div>
        <div class="budget-total">
          <span>总计</span>
          <span class="total-amount">¥{{ plan.budget.total }}</span>
        </div>
      </div>
    </div>

    <!-- 建议 -->
    <div v-if="plan.overall_suggestions" class="suggestions-section">
      <div class="section-title">💡 温馨提示</div>
      <p class="suggestions-text">{{ plan.overall_suggestions }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  plan: any
}>()

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  if (parts.length === 3) {
    return `${parts[1]}/${parts[2]}`
  }
  return dateStr
}

function getTransportIcon(type: string): string {
  const icons: Record<string, string> = {
    train: '🚄',
    driving: '🚗',
    flight: '✈️'
  }
  return icons[type] || '🚀'
}
</script>

<style scoped>
.plan-card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.plan-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px;
}

.plan-header h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.plan-date {
  margin: 0;
  font-size: 13px;
  opacity: 0.9;
}

.plan-route {
  margin: 4px 0 0;
  font-size: 12px;
  opacity: 0.8;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #eee;
}

/* 黄历样式 */
.lucky-day-section {
  padding: 12px 16px;
  background: #fff9e6;
  border-bottom: 1px solid #eee;
}

.lucky-day-content {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.lunar-date {
  font-size: 14px;
  font-weight: 600;
  color: #d4380d;
}

.suitable, .avoid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.label {
  font-size: 12px;
  color: #666;
}

.tag {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.suitable-tag {
  background: #f6ffed;
  color: #52c41a;
}

.avoid-tag {
  background: #fff2f0;
  color: #ff4d4f;
}

/* 天气样式 */
.weather-section {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.weather-list {
  display: flex;
  gap: 12px;
  overflow-x: auto;
}

.weather-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 8px;
}

.weather-date {
  font-size: 11px;
  color: #666;
}

.weather-desc {
  font-size: 16px;
  margin: 4px 0;
}

.weather-temp {
  font-size: 12px;
  color: #333;
}

/* 交通方案样式 */
.transport-section {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.transport-options {
  display: flex;
  gap: 12px;
}

.transport-option {
  flex: 1;
  display: flex;
  gap: 8px;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.transport-icon {
  font-size: 24px;
}

.transport-info {
  flex: 1;
}

.transport-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.transport-details {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
}

.transport-details span {
  margin-right: 8px;
}

/* 每日行程样式 */
.days-section {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.days-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.day-item {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.day-badge {
  background: #3498db;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.day-date {
  color: #666;
  font-size: 12px;
}

.day-desc {
  margin: 0 0 8px;
  font-size: 13px;
  color: #333;
  line-height: 1.4;
}

.attractions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.attraction-tag {
  background: white;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #555;
  border: 1px solid #ddd;
}

.ticket-price {
  color: #ff6b00;
  font-size: 11px;
  margin-left: 4px;
}

.hotel-info {
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}

/* 预算样式 */
.budget-section {
  padding: 12px 16px;
  background: #f0f9eb;
  border-bottom: 1px solid #e0e0e0;
}

.budget-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.budget-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #666;
}

.budget-total {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #b7eb8f;
}

.total-amount {
  color: #52c41a;
  font-size: 16px;
}

/* 建议样式 */
.suggestions-section {
  padding: 12px 16px;
}

.suggestions-text {
  margin: 0;
  font-size: 13px;
  color: #666;
  line-height: 1.6;
}
</style>