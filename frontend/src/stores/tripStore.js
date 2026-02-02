import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTripStore = defineStore('trip', () => {
  // 状态
  const tripRequest = ref({
    city: '',
    start_date: '',
    end_date: '',
    interests: [],
    accommodation_type: '',
    budget_per_day: null,
    transportation_mode: ''
  })
  
  const tripPlan = ref(null)
  const isLoading = ref(false)
  const error = ref('')
  const progressMessages = ref([])
  
  // 计算属性
  const isValid = computed(() => {
    return tripRequest.value.city && 
           tripRequest.value.start_date && 
           tripRequest.value.end_date &&
           tripRequest.value.interests.length > 0
  })
  
  const tripDays = computed(() => {
    if (!tripRequest.value.start_date || !tripRequest.value.end_date) {
      return 0
    }
    const start = new Date(tripRequest.value.start_date)
    const end = new Date(tripRequest.value.end_date)
    return Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1
  })
  
  // 方法
  const setTripRequest = (data) => {
    tripRequest.value = { ...tripRequest.value, ...data }
  }
  
  const setTripPlan = (plan) => {
    tripPlan.value = plan
  }
  
  const setLoading = (value) => {
    isLoading.value = value
  }
  
  const setError = (message) => {
    error.value = message
  }
  
  const clearError = () => {
    error.value = ''
  }
  
  const addProgressMessage = (message) => {
    progressMessages.value.push(message)
  }
  
  const clearProgressMessages = () => {
    progressMessages.value = []
  }
  
  const resetForm = () => {
    tripRequest.value = {
      city: '',
      start_date: '',
      end_date: '',
      interests: [],
      accommodation_type: '',
      budget_per_day: null,
      transportation_mode: ''
    }
    tripPlan.value = null
    error.value = ''
    progressMessages.value = []
  }
  
  return {
    // 状态
    tripRequest,
    tripPlan,
    isLoading,
    error,
    progressMessages,
    
    // 计算属性
    isValid,
    tripDays,
    
    // 方法
    setTripRequest,
    setTripPlan,
    setLoading,
    setError,
    clearError,
    addProgressMessage,
    clearProgressMessages,
    resetForm
  }
})
