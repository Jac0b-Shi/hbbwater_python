import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

export const useAlertStore = defineStore('alerts', () => {
  // State
  const alerts = ref([])
  const loading = ref(false)
  const error = ref(null)
  const lastFetch = ref(null)

  // Getters
  const allAlerts = computed(() => alerts.value)
  const activeAlerts = computed(() => alerts.value.filter(a => !a.is_resolved))
  const unresolvedCount = computed(() => activeAlerts.value.length)
  
  const criticalAlerts = computed(() => 
    activeAlerts.value.filter(a => a.severity === 'critical')
  )
  
  const highAlerts = computed(() => 
    activeAlerts.value.filter(a => a.severity === 'high')
  )

  // Actions
  async function fetchAlerts(params = {}) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.get('/api/alerts/', { params })
      alerts.value = response.data
      lastFetch.value = new Date()
      return response.data
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch alerts:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchActiveAlerts() {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.get('/api/alerts/active')
      alerts.value = response.data
      lastFetch.value = new Date()
      return response.data
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch active alerts:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function resolveAlert(alertId, resolvedBy) {
    try {
      const response = await axios.post(`/api/alerts/${alertId}/resolve`, {
        resolved_by: resolvedBy
      })
      
      // Update local state
      const index = alerts.value.findIndex(a => a.id === alertId)
      if (index !== -1) {
        alerts.value[index] = response.data
      }
      
      return response.data
    } catch (err) {
      console.error('Failed to resolve alert:', err)
      throw err
    }
  }

  function addAlert(alert) {
    alerts.value.unshift(alert)
  }

  function clearAlerts() {
    alerts.value = []
  }

  return {
    // State
    alerts,
    loading,
    error,
    lastFetch,
    // Getters
    allAlerts,
    activeAlerts,
    unresolvedCount,
    criticalAlerts,
    highAlerts,
    // Actions
    fetchAlerts,
    fetchActiveAlerts,
    resolveAlert,
    addAlert,
    clearAlerts
  }
})
