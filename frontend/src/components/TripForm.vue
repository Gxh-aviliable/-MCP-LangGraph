<template>
  <div class="trip-form">
    <h2>📝 旅行信息表</h2>
    
    <el-form :model="form" label-width="120px" @submit.prevent="handleSubmit">
      <!-- 城市输入 -->
      <el-form-item label="目的地城市" required>
        <el-input
          v-model="form.city"
          placeholder="请输入目的地城市，如：北京、上海、杭州"
          clearable
          class="full-width"
        />
        <div class="hint-text">💡 输入任意城市名称，系统将为您规划行程</div>
      </el-form-item>

      <!-- 日期选择 -->
      <el-form-item label="旅行日期" required>
        <div class="date-range">
          <el-date-picker
            v-model="form.start_date"
            type="date"
            placeholder="开始日期"
            value-format="YYYY-MM-DD"
            class="date-picker"
          />
          <span class="date-separator">至</span>
          <el-date-picker
            v-model="form.end_date"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            class="date-picker"
          />
        </div>
        <div class="date-info" v-if="tripDays > 0">
          {{ tripDays }} 天 {{ tripDaysText }}
        </div>
      </el-form-item>

      <!-- 兴趣爱好输入 -->
      <el-form-item label="兴趣爱好" required>
        <div class="interest-input-group">
          <div class="input-row">
            <el-input
              v-model="interestInput"
              placeholder="输入兴趣爱好，如：故宫、西湖、美食等"
              @keyup.enter="handleAddInterest"
              class="interest-input"
            />
            <el-button 
              type="primary" 
              @click="handleAddInterest"
              class="add-btn"
            >
              + 添加
            </el-button>
          </div>
          <div class="hint-text">💡 可以输入多个兴趣爱好，用"添加"按钮逐个添加</div>
        </div>
        
        <div class="interest-tags" v-if="form.interests.length > 0">
          <el-tag
            v-for="(item, index) in form.interests"
            :key="index"
            closable
            @close="handleRemoveInterest(index)"
            class="interest-tag"
            type="success"
          >
            {{ item }}
          </el-tag>
        </div>
      </el-form-item>

      <!-- 住宿类型 -->
      <el-form-item label="住宿类型">
        <el-radio-group v-model="form.accommodation_type">
          <el-radio
            v-for="type in accommodationTypes"
            :key="type.name"
            :label="type.name"
            class="radio-button"
          >
            {{ type.name }}
            <div class="radio-description">{{ type.description }}</div>
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <!-- 每日预算 -->
      <el-form-item label="每日预算">
        <div class="budget-input">
          <el-input-number
            v-model="form.budget_per_day"
            :min="0"
            :max="10000"
            :step="100"
            controls-position="right"
            placeholder="输入每日预算（元）"
          />
          <span class="currency-unit">元/天</span>
        </div>
        <div class="budget-hint" v-if="form.budget_per_day">
          总预算估算：¥ {{ (form.budget_per_day * tripDays).toLocaleString() }}
        </div>
      </el-form-item>

      <!-- 交通方式 -->
      <el-form-item label="交通方式">
        <el-select
          v-model="form.transportation_mode"
          placeholder="请选择交通方式"
          class="full-width"
        >
          <el-option label="地铁+出租车" value="地铁+出租车" />
          <el-option label="公交车" value="公交车" />
          <el-option label="打车出行" value="打车出行" />
          <el-option label="自驾车" value="自驾车" />
          <el-option label="步行" value="步行" />
          <el-option label="混合出行" value="混合出行" />
        </el-select>
      </el-form-item>

      <!-- 操作按钮 -->
      <el-form-item>
        <div class="button-group">
          <el-button
            type="primary"
            size="large"
            @click="handleSubmit"
            :disabled="!isFormValid"
            class="submit-btn"
          >
            🚀 开始规划
          </el-button>
          <el-button
            @click="handleReset"
            size="large"
            class="reset-btn"
          >
            🔄 重置表单
          </el-button>
        </div>
      </el-form-item>

      <!-- 表单提示 -->
      <div class="form-hint">
        <el-alert
          title="✨ 提示"
          type="info"
          :closable="false"
          description="AI 智能体将根据您的需求：
• 🎯 搜索实时景点信息
• 🌤️ 查询天气预报数据
• 🏨 推荐优质酒店
• 📅 生成详细行程安排
最后将为您生成完整的旅行计划！"
        />
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useTripStore } from '../stores/tripStore'
import { tripAPI, createWebSocketConnection } from '../utils/api'
import { ElMessage } from 'element-plus'

const store = useTripStore()

// 表单数据
const form = ref({
  city: '',
  start_date: '',
  end_date: '',
  interests: [],
  accommodation_type: '',
  budget_per_day: null,
  transportation_mode: ''
})

// 兴趣爱好输入框
const interestInput = ref('')

// 参考数据（仅用于住宿类型）
const accommodationTypes = ref([])

// 计算属性
const tripDays = computed(() => {
  if (!form.value.start_date || !form.value.end_date) {
    return 0
  }
  const start = new Date(form.value.start_date)
  const end = new Date(form.value.end_date)
  return Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1
})

const tripDaysText = computed(() => {
  const days = tripDays.value
  if (days <= 1) return '（一日游）'
  if (days <= 3) return '（短途旅行）'
  if (days <= 7) return '（周末旅行）'
  if (days <= 15) return '（长途旅行）'
  return '（超长旅行）'
})

const isFormValid = computed(() => {
  return form.value.city &&
    form.value.start_date &&
    form.value.end_date &&
    form.value.interests.length > 0 &&
    tripDays.value > 0
})

// 方法
const loadReferenceData = async () => {
  try {
    // 只需要加载住宿类型
    const accommodationRes = await tripAPI.getAccommodationTypes()
    accommodationTypes.value = accommodationRes.data.data || []
  } catch (error) {
    console.error('加载参考数据失败:', error)
    ElMessage.error('加载参考数据失败，请刷新页面重试')
  }
}

const handleAddInterest = () => {
  const interest = interestInput.value.trim()
  if (!interest) {
    ElMessage.warning('请输入兴趣爱好')
    return
  }
  
  if (form.value.interests.includes(interest)) {
    ElMessage.warning('该兴趣爱好已添加')
    return
  }
  
  form.value.interests.push(interest)
  interestInput.value = ''
  ElMessage.success(`已添加：${interest}`)
}

const handleRemoveInterest = (index) => {
  const removed = form.value.interests[index]
  form.value.interests.splice(index, 1)
  ElMessage.success(`已移除：${removed}`)
}

const handleSubmit = async () => {
  if (!isFormValid.value) {
    ElMessage.warning('请完整填写表单信息')
    return
  }

  store.setLoading(true)
  store.clearProgressMessages()
  store.clearError()

  try {
    // 使用 WebSocket 建立连接以接收实时进度
    const ws = createWebSocketConnection((message) => {
      console.log('收到消息:', message)

      if (message.type === 'progress') {
        store.addProgressMessage(message)
      } else if (message.type === 'success') {
        store.setTripPlan(message.data)
        store.setLoading(false)
        ElMessage.success(message.message)
      } else if (message.type === 'error') {
        store.setLoading(false)
        store.setError(message.message)
        ElMessage.error(message.message)
        ws.close()
      } else if (message.type === 'warning') {
        store.addProgressMessage(message)
      }
    })

    // 等待 WebSocket 连接建立
    await new Promise(resolve => {
      const checkConnection = () => {
        if (ws.readyState === WebSocket.OPEN) {
          resolve()
        } else if (ws.readyState === WebSocket.CONNECTING) {
          setTimeout(checkConnection, 100)
        } else {
          resolve() // 连接失败，使用 HTTP 备选方案
        }
      }
      checkConnection()
    })

    // 如果 WebSocket 未连接，使用 HTTP API
    if (ws.readyState !== WebSocket.OPEN) {
      const response = await tripAPI.planTrip(form.value)
      if (response.data.success) {
        store.setTripPlan(response.data.data)
        ElMessage.success('行程规划成功！')
      } else {
        store.setError(response.data.message)
        ElMessage.error(response.data.message)
      }
      store.setLoading(false)
    } else {
      // 发送规划请求到 WebSocket
      ws.send(JSON.stringify({
        action: 'plan',
        data: form.value
      }))
    }
  } catch (error) {
    console.error('规划失败:', error)
    store.setLoading(false)
    store.setError('规划过程出错，请稍后重试')
    ElMessage.error('规划失败，请检查网络连接')
  }
}

const handleReset = () => {
  form.value = {
    city: '',
    start_date: '',
    end_date: '',
    interests: [],
    accommodation_type: '',
    budget_per_day: null,
    transportation_mode: ''
  }
  store.resetForm()
}

// 生命周期
onMounted(() => {
  loadReferenceData()
})
</script>

<style scoped>
.trip-form {
  padding: 30px;
}

.trip-form h2 {
  font-size: 24px;
  margin-bottom: 30px;
  color: #333;
  text-align: center;
}

.full-width {
  width: 100%;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-picker {
  flex: 1;
}

.date-separator {
  color: #999;
  font-weight: bold;
}

.date-info {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.hint-text {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
  font-style: italic;
}

.interest-input-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.interest-input {
  flex: 1;
}

.add-btn {
  min-width: 80px;
}

.interest-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.interest-tag {
  cursor: pointer;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-picker {
  flex: 1;
}

.date-separator {
  color: #999;
  font-weight: bold;
}

.date-info {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.radio-button {
  display: block;
  margin: 10px 0;
}

.radio-description {
  font-size: 12px;
  color: #999;
  margin-left: 24px;
}

.budget-input {
  display: flex;
  align-items: center;
  gap: 10px;
}

.currency-unit {
  color: #666;
  font-weight: bold;
}

.budget-hint {
  font-size: 12px;
  color: #67c23a;
  margin-top: 5px;
  font-weight: bold;
}

.button-group {
  display: flex;
  gap: 15px;
  justify-content: center;
}

.submit-btn,
.reset-btn {
  flex: 1;
  max-width: 150px;
  height: 40px;
  font-size: 16px;
  font-weight: bold;
}

.form-hint {
  margin-top: 30px;
}

@media (max-width: 768px) {
  .trip-form {
    padding: 20px;
  }

  .trip-form h2 {
    font-size: 20px;
    margin-bottom: 20px;
  }

  .button-group {
    flex-direction: column;
  }

  .submit-btn,
  .reset-btn {
    max-width: 100%;
  }

  .date-range {
    flex-direction: column;
  }

  .date-picker {
    width: 100%;
  }
}
</style>
