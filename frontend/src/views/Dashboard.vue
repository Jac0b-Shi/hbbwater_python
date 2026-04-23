<template>
  <div class="dashboard">
    <!-- Stats Cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon total">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardStore.stats.total_sensors }}</div>
            <div class="stat-label">传感器总数</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon online">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardStore.stats.online_sensors }}</div>
            <div class="stat-label">在线传感器</div>
            <div class="stat-rate">{{ dashboardStore.onlineRate }}%</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon alert">
            <el-icon><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardStore.stats.active_alerts }}</div>
            <div class="stat-label">活动告警</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon data">
            <el-icon><DataLine /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardStore.stats.today_readings }}</div>
            <div class="stat-label">今日数据</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Main Content -->
    <el-row :gutter="20" class="main-row">
      <!-- Sensor Status Table -->
      <el-col :xs="24" :lg="16">
        <el-card class="status-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>传感器状态</span>
              <el-button type="primary" size="small" @click="refreshStatus">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </template>
          <el-table :data="dashboardStore.sensorStatus" stripe style="width: 100%">
            <el-table-column prop="sensor_id" label="传感器ID" width="150" />
            <el-table-column prop="location" label="位置" />
            <el-table-column prop="sensor_type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="row.sensor_type === 'ultrasonic' ? 'primary' : 'warning'">
                  {{ row.sensor_type === 'ultrasonic' ? '超声波' : '浸水' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_online" label="在线" width="80">
              <template #default="{ row }">
                <el-icon :size="20" :color="row.is_online ? '#67c23a' : '#f56c6c'">
                  <CircleCheck v-if="row.is_online" />
                  <CircleClose v-else />
                </el-icon>
              </template>
            </el-table-column>
            <el-table-column prop="water_level" label="水位(cm)" width="120">
              <template #default="{ row }">
                {{ row.water_level !== null ? row.water_level.toFixed(1) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="供电/电量" width="120">
              <template #default="{ row }">
                <span v-if="row.external_powered">外接供电</span>
                <el-progress 
                  v-else-if="row.battery_level !== null"
                  :percentage="Math.round(row.battery_level)"
                  :color="getBatteryColor"
                  :show-text="false"
                  style="width: 50px"
                />
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- Recent Alerts -->
      <el-col :xs="24" :lg="8">
        <el-card class="alerts-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最新告警</span>
              <el-button type="primary" link @click="$router.push('/alerts')">
                查看全部
              </el-button>
            </div>
          </template>
          <div class="alert-list">
            <div 
              v-for="alert in dashboardStore.recentAlerts" 
              :key="alert.id"
              class="alert-item"
              :class="alert.severity"
            >
              <div class="alert-header">
                <el-tag size="small" :type="getSeverityType(alert.severity)">
                  {{ getSeverityText(alert.severity) }}
                </el-tag>
                <span class="alert-time">{{ formatTime(alert.created_at) }}</span>
              </div>
              <div class="alert-content">{{ alert.message }}</div>
              <div class="alert-location">
                <el-icon><Location /></el-icon>
                {{ alert.location }}
              </div>
            </div>
            <el-empty v-if="dashboardStore.recentAlerts.length === 0" description="暂无告警" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Readings -->
    <el-row :gutter="20" class="bottom-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近数据</span>
              <el-radio-group v-model="dataFilter" size="small">
                <el-radio-button label="all">全部</el-radio-button>
                <el-radio-button label="ultrasonic">超声波</el-radio-button>
                <el-radio-button label="immersion">浸水</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="reading in filteredReadings.slice(0, 10)"
              :key="reading.id"
              :type="getReadingType(reading.status)"
              :timestamp="formatTime(reading.recorded_at)"
            >
              <div class="reading-item">
                <span class="reading-sensor">{{ reading.sensor_id }}</span>
                <span class="reading-location">{{ reading.location }}</span>
                <span v-if="reading.water_level !== null" class="reading-value">
                  水位: {{ reading.water_level.toFixed(1) }}cm
                </span>
                <span v-if="reading.water_detected !== null" class="reading-value">
                  状态: {{ reading.water_detected ? '浸水' : '正常' }}
                </span>
                <el-tag size="small" :type="getStatusType(reading.status)">
                  {{ getStatusText(reading.status) }}
                </el-tag>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { formatUtc8DateTime, SHORT_DATE_TIME_FORMAT } from '../utils/time'

const dashboardStore = useDashboardStore()
const dataFilter = ref('all')
let refreshInterval = null

const filteredReadings = computed(() => {
  if (dataFilter.value === 'all') {
    return dashboardStore.recentReadings
  }
  return dashboardStore.recentReadings.filter(r => r.sensor_type === dataFilter.value)
})

const getStatusType = (status) => {
  const map = {
    normal: 'success',
    warning: 'warning',
    danger: 'danger',
    alarm: 'danger',
    offline: 'info'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    normal: '正常',
    warning: '预警',
    danger: '危险',
    alarm: '告警',
    offline: '离线'
  }
  return map[status] || status
}

const getSeverityType = (severity) => {
  const map = {
    low: 'info',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return map[severity] || 'info'
}

const getSeverityText = (severity) => {
  const map = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '紧急'
  }
  return map[severity] || severity
}

const getReadingType = (status) => {
  if (status === 'danger' || status === 'alarm') return 'danger'
  if (status === 'warning') return 'warning'
  return 'primary'
}

const getBatteryColor = (percentage) => {
  if (percentage < 20) return '#f56c6c'
  if (percentage < 40) return '#e6a23c'
  return '#67c23a'
}

const formatTime = (time) => {
  return formatUtc8DateTime(time, SHORT_DATE_TIME_FORMAT)
}

const refreshStatus = async () => {
  await dashboardStore.refreshAll()
}

onMounted(async () => {
  await dashboardStore.refreshAll()
  // Auto refresh every 5 seconds for near real-time updates
  refreshInterval = setInterval(() => {
    dashboardStore.refreshAll()
  }, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.dashboard {
  padding-bottom: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 10px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  margin-right: 16px;
}

.stat-icon.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-icon.online {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  color: white;
}

.stat-icon.alert {
  background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%);
  color: white;
}

.stat-icon.data {
  background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}

.stat-rate {
  font-size: 12px;
  color: #67c23a;
  margin-top: 4px;
}

.main-row {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-card {
  min-height: 500px;
}

.alert-list {
  max-height: 500px;
  overflow-y: auto;
}

.alert-item {
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 12px;
  background: #f5f7fa;
  border-left: 4px solid #909399;
}

.alert-item.critical {
  border-left-color: #f56c6c;
  background: #fef0f0;
}

.alert-item.high {
  border-left-color: #e6a23c;
  background: #fdf6ec;
}

.alert-item.medium {
  border-left-color: #e6a23c;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.alert-time {
  font-size: 12px;
  color: #909399;
}

.alert-content {
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
}

.alert-location {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}

.reading-item {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.reading-sensor {
  font-weight: 500;
  color: #303133;
}

.reading-location {
  color: #909399;
  font-size: 13px;
}

.reading-value {
  color: #409eff;
  font-weight: 500;
}
</style>
