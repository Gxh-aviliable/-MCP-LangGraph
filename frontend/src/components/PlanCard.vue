<template>
  <div class="plan-card">
    <div class="plan-header">
      <h3>📋 {{ plan.city }} 旅行计划</h3>
      <p class="plan-date">{{ plan.start_date }} 至 {{ plan.end_date }}</p>
    </div>

    <!-- 每日行程 -->
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
          </span>
        </div>
      </div>
    </div>

    <!-- 预算 -->
    <div class="budget" v-if="plan.budget">
      <span class="budget-label">预算估算:</span>
      <span class="budget-value">¥{{ plan.budget.total }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  plan: any
}>()
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

.days-list {
  padding: 12px;
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

.budget {
  padding: 12px 16px;
  background: #f0f9eb;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.budget-label {
  color: #67c23a;
  font-size: 13px;
}

.budget-value {
  font-weight: bold;
  color: #67c23a;
  font-size: 16px;
}
</style>