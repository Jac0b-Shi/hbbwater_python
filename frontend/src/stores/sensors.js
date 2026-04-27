import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { parseUtcDate } from '../utils/time'

const numericFields = [
  'water_level',
  'battery_level',
  'warning_level',
  'danger_level',
  'water_level_baseline',
  'map_x',
  'map_y',
]

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

function normalizeReading(reading) {
  return normalizeNumericFields(reading)
}

function normalizeGroup(group) {
  if (!group) return group
  return {
    ...group,
    sensors: (group.sensors || []).map(normalizeNumericFields)
  }
}

function normalizeTimeSeries(series) {
  if (!series?.data) return series
  return {
    ...series,
    data: series.data.map(point => ({
      ...point,
      value: toNumber(point.value)
    }))
  }
}

export const useSensorStore = defineStore('sensors', () => {
  // State
  const sensors = ref([])
  const groups = ref([])
  const readings = ref({})
  const timeSeries = ref({})
  const loading = ref(false)
  const error = ref(null)
  const lastFetch = ref(null)

  // Getters
  const allSensors = computed(() => sensors.value)
  const allGroups = computed(() => groups.value)
  
  const ultrasonicSensors = computed(() => 
    sensors.value.filter(s => s.sensor_type === 'ultrasonic')
  )
  
  const immersionSensors = computed(() => 
    sensors.value.filter(s => s.sensor_type === 'immersion')
  )
  
  const activeSensors = computed(() => 
    sensors.value.filter(s => s.is_active)
  )
  
  const onlineSensors = computed(() => {
    const threshold = new Date(Date.now() - 60 * 60 * 1000) // 60 minutes
    return sensors.value.filter(s => {
      const lastReading = readings.value[s.sensor_id]?.[0]
      const recordedAt = parseUtcDate(lastReading?.recorded_at)
      return recordedAt && recordedAt > threshold
    })
  })
  
  const offlineSensors = computed(() => 
    activeSensors.value.length - onlineSensors.value.length
  )

  // Actions
  async function fetchSensors(params = {}) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.get('/api/sensors/', { params })
      sensors.value = response.data.map(normalizeNumericFields)
      lastFetch.value = new Date()
      return sensors.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch sensors:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchGroups() {
    try {
      const response = await axios.get('/api/sensors/groups')
      groups.value = response.data.map(normalizeGroup)
      return groups.value
    } catch (err) {
      console.error('Failed to fetch webhook groups:', err)
      throw err
    }
  }

  async function fetchSensor(sensorId) {
    try {
      const response = await axios.get(`/api/sensors/${sensorId}`)
      return normalizeNumericFields(response.data)
    } catch (err) {
      console.error('Failed to fetch sensor:', err)
      throw err
    }
  }

  async function createSensor(sensorData) {
    try {
      const response = await axios.post('/api/sensors/', sensorData)
      const sensor = normalizeNumericFields(response.data)
      sensors.value.push(sensor)
      return sensor
    } catch (err) {
      console.error('Failed to create sensor:', err)
      throw err
    }
  }

  async function createGroup(groupData) {
    try {
      const response = await axios.post('/api/sensors/groups', groupData)
      groups.value.unshift({ ...response.data, sensors: [] })
      return response.data
    } catch (err) {
      console.error('Failed to create webhook group:', err)
      throw err
    }
  }

  async function updateGroup(groupId, groupData) {
    try {
      const response = await axios.patch(`/api/sensors/groups/${groupId}`, groupData)
      const index = groups.value.findIndex(g => g.id === groupId)
      if (index !== -1) {
        groups.value[index] = { ...groups.value[index], ...response.data }
      }
      return response.data
    } catch (err) {
      console.error('Failed to update webhook group:', err)
      throw err
    }
  }

  async function deleteGroup(groupId) {
    try {
      await axios.delete(`/api/sensors/groups/${groupId}`)
      groups.value = groups.value.filter(g => g.id !== groupId)
      sensors.value = sensors.value.map(sensor => (
        sensor.webhook_group_id === groupId
          ? { ...sensor, webhook_group_id: null, webhook_group_name: null, device_imei: null }
          : sensor
      ))
    } catch (err) {
      console.error('Failed to delete webhook group:', err)
      throw err
    }
  }

  async function updateSensor(sensorId, sensorData) {
    try {
      const response = await axios.patch(`/api/sensors/${sensorId}`, sensorData)
      const sensor = normalizeNumericFields(response.data)
      const index = sensors.value.findIndex(s => s.sensor_id === sensorId)
      if (index !== -1) {
        sensors.value[index] = sensor
      }
      return sensor
    } catch (err) {
      console.error('Failed to update sensor:', err)
      throw err
    }
  }

  async function deleteSensor(sensorId) {
    try {
      await axios.delete(`/api/sensors/${sensorId}`)
      sensors.value = sensors.value.filter(s => s.sensor_id !== sensorId)
    } catch (err) {
      console.error('Failed to delete sensor:', err)
      throw err
    }
  }

  async function fetchReadings(sensorId, params = {}) {
    try {
      const response = await axios.get(`/api/sensors/${sensorId}/readings`, { params })
      const data = {
        ...response.data,
        items: response.data.items.map(normalizeReading)
      }
      readings.value[sensorId] = data.items
      return data
    } catch (err) {
      console.error('Failed to fetch readings:', err)
      throw err
    }
  }

  async function fetchTimeSeries(sensorId, field = 'water_level', hours = 24) {
    try {
      const response = await axios.get(`/api/sensors/${sensorId}/timeseries`, {
        params: { field, hours }
      })
      const data = normalizeTimeSeries(response.data)
      timeSeries.value[`${sensorId}_${field}`] = data
      return data
    } catch (err) {
      console.error('Failed to fetch time series:', err)
      throw err
    }
  }

  async function fetchAllSensorStatus() {
    try {
      const response = await axios.get('/api/sensors/status/all')
      return response.data.map(normalizeNumericFields)
    } catch (err) {
      console.error('Failed to fetch sensor status:', err)
      throw err
    }
  }

  function updateSensorStatus(sensorId, status) {
    const sensor = sensors.value.find(s => s.sensor_id === sensorId)
    if (sensor) {
      sensor.status = status
    }
  }

  function addReading(sensorId, reading) {
    if (!readings.value[sensorId]) {
      readings.value[sensorId] = []
    }
    readings.value[sensorId].unshift(normalizeReading(reading))
    // Keep only last 100 readings
    if (readings.value[sensorId].length > 100) {
      readings.value[sensorId] = readings.value[sensorId].slice(0, 100)
    }
  }

  return {
    // State
    sensors,
    groups,
    readings,
    timeSeries,
    loading,
    error,
    lastFetch,
    // Getters
    allSensors,
    allGroups,
    ultrasonicSensors,
    immersionSensors,
    activeSensors,
    onlineSensors,
    offlineSensors,
    // Actions
    fetchSensors,
    fetchGroups,
    fetchSensor,
    createGroup,
    createSensor,
    updateGroup,
    updateSensor,
    deleteGroup,
    deleteSensor,
    fetchReadings,
    fetchTimeSeries,
    fetchAllSensorStatus,
    updateSensorStatus,
    addReading
  }
})
