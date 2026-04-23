import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

const numericFields = ['water_level', 'battery_level']

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : value
}

function normalizeNumericFields(item) {
  if (!item) return item
  return numericFields.reduce((normalized, field) => {
    if (field in normalized) {
      normalized[field] = toNumber(normalized[field])
    }
    return normalized
  }, { ...item })
}

export const useDashboardStore = defineStore('dashboard', () => {
  // State
  const stats = ref({
    total_sensors: 0,
    online_sensors: 0,
    offline_sensors: 0,
    active_alerts: 0,
    today_readings: 0,
    ultrasonic_sensors: 0,
    immersion_sensors: 0
  })
  const recentReadings = ref([])
  const recentAlerts = ref([])
  const sensorStatus = ref([])
  const loading = ref(false)
  const error = ref(null)
  const lastFetch = ref(null)

  // Getters
  const dashboardStats = computed(() => stats.value)
  
  const onlineRate = computed(() => {
    if (stats.value.total_sensors === 0) return 0
    return Math.round((stats.value.online_sensors / stats.value.total_sensors) * 100)
  })
  
  const hasAlerts = computed(() => stats.value.active_alerts > 0)
  
  const criticalSensors = computed(() => 
    sensorStatus.value.filter(s => s.status === 'danger' || s.status === 'alarm')
  )

  // Actions
  async function fetchStats() {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.get('/api/dashboard/stats')
      stats.value = response.data
      lastFetch.value = new Date()
      return response.data
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch dashboard stats:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchRecentReadings(limit = 20) {
    try {
      const response = await axios.get('/api/dashboard/recent-readings', {
        params: { limit }
      })
      recentReadings.value = response.data.map(normalizeNumericFields)
      return recentReadings.value
    } catch (err) {
      console.error('Failed to fetch recent readings:', err)
      throw err
    }
  }

  async function fetchRecentAlerts(limit = 10) {
    try {
      const response = await axios.get('/api/dashboard/alerts/recent', {
        params: { limit }
      })
      recentAlerts.value = response.data
      return response.data
    } catch (err) {
      console.error('Failed to fetch recent alerts:', err)
      throw err
    }
  }

  async function fetchSensorStatus() {
    try {
      const response = await axios.get('/api/dashboard/sensor-status')
      sensorStatus.value = response.data.map(normalizeNumericFields)
      return sensorStatus.value
    } catch (err) {
      console.error('Failed to fetch sensor status:', err)
      throw err
    }
  }

  async function refreshAll() {
    await Promise.all([
      fetchStats(),
      fetchRecentReadings(),
      fetchRecentAlerts(),
      fetchSensorStatus()
    ])
  }

  return {
    // State
    stats,
    recentReadings,
    recentAlerts,
    sensorStatus,
    loading,
    error,
    lastFetch,
    // Getters
    dashboardStats,
    onlineRate,
    hasAlerts,
    criticalSensors,
    // Actions
    fetchStats,
    fetchRecentReadings,
    fetchRecentAlerts,
    fetchSensorStatus,
    refreshAll
  }
})
