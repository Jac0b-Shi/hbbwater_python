<template>
  <div class="history-page">
    <el-card shadow="hover">
      <template #header>
        <div class="page-header">
          <h2>历史数据查询</h2>
        </div>
      </template>

      <!-- Filter Form -->
      <el-form :model="filterForm" inline class="filter-form">
        <el-form-item label="传感器">
          <el-select v-model="filterForm.sensor_id" placeholder="选择传感器" clearable style="width: 200px">
            <el-option-group label="超声波传感器">
              <el-option 
                v-for="s in ultrasonicSensors" 
                :key="s.sensor_id" 
                :label="`${s.sensor_id} - ${s.location}`" 
                :value="s.sensor_id" 
              />
            </el-option-group>
            <el-option-group label="浸水传感器">
              <el-option 
                v-for="s in immersionSensors" 
                :key="s.sensor_id" 
                :label="`${s.sensor_id} - ${s.location}`" 
                :value="s.sensor_id" 
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="queryHistory">
            <el-icon><Search /></el-icon>查询
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
          <el-button type="success" @click="exportData" :disabled="!historyData.length">
            <el-icon><Download /></el-icon>导出
          </el-button>
        </el-form-item>
      </el-form>

      <!-- Chart -->
      <div v-if="historyData.length" class="chart-section">
        <v-chart class="history-chart" :option="chartOption" autoresize />
      </div>

      <!-- Data Table -->
      <el-table
        v-loading="loading"
        :data="paginatedData"
        stripe
        style="width: 100%"
        max-height="500"
      >
        <el-table-column prop="recorded_at" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.recorded_at) }}</template>
        </el-table-column>
        <el-table-column prop="sensor_id" label="传感器" width="150" />
        <el-table-column prop="location" label="位置" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="water_level" label="水位(cm)" width="120">
          <template #default="{ row }">{{ row.water_level?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="water_detected" label="浸水" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.water_detected !== null" :type="row.water_detected ? 'danger' : 'success'">
              {{ row.water_detected ? '是' : '否' }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="供电/电量" width="120">
          <template #default="{ row }">{{ row.external_powered ? '外接供电' : (row.battery_level?.toFixed(1) || '-') }}</template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <el-pagination
        v-if="historyData.length"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[50, 100, 200, 500]"
        layout="total, sizes, prev, pager, next"
        :total="historyData.length"
        class="pagination"
      />

      <el-empty v-if="!loading && !historyData.length" description="请选择条件查询数据" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useSensorStore } from '../stores/sensors'
import dayjs from 'dayjs'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

const sensorStore = useSensorStore()

const filterForm = ref({
  sensor_id: '',
  timeRange: []
})

const historyData = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(100)
let refreshTimer = null

const ultrasonicSensors = computed(() => sensorStore.ultrasonicSensors)
const immersionSensors = computed(() => sensorStore.immersionSensors)

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return historyData.value.slice(start, start + pageSize.value)
})

const chartOption = computed(() => {
  if (!historyData.value.length) return {}
  
  const sensor = sensorStore.sensors.find(s => s.sensor_id === filterForm.value.sensor_id)
  const isUltrasonic = sensor?.sensor_type === 'ultrasonic'
  
  const data = historyData.value
    .filter(d => isUltrasonic ? d.water_level !== null : d.water_detected !== null)
    .map(d => [d.recorded_at, isUltrasonic ? d.water_level : (d.water_detected ? 1 : 0)])
    .reverse()

  return {
    title: { text: `${sensor?.sensor_id} - ${sensor?.location}`, left: 'center' },
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'time', boundaryGap: false },
    yAxis: { 
      type: 'value', 
      name: isUltrasonic ? '水位(cm)' : '浸水状态',
      min: isUltrasonic ? 0 : -0.1,
      max: isUltrasonic ? null : 1.1
    },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [{
      name: isUltrasonic ? '水位' : '浸水',
      type: isUltrasonic ? 'line' : 'scatter',
      smooth: true,
      symbol: isUltrasonic ? 'none' : 'circle',
      symbolSize: isUltrasonic ? 0 : 10,
      data: data
    }]
  }
})

const formatTime = (time) => dayjs(time).format('YYYY-MM-DD HH:mm:ss')

const getStatusType = (status) => {
  const map = { normal: 'success', warning: 'warning', danger: 'danger', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { normal: '正常', warning: '预警', danger: '危险', alarm: '告警', offline: '离线' }
  return map[status] || status
}

const queryHistory = async () => {
  if (!filterForm.value.sensor_id) {
    ElMessage.warning('请选择传感器')
    return
  }
  
  loading.value = true
  try {
    const params = { limit: 10000 }
    if (filterForm.value.timeRange?.length === 2) {
      params.start_time = filterForm.value.timeRange[0]
      params.end_time = filterForm.value.timeRange[1]
    }
    
    const response = await sensorStore.fetchReadings(filterForm.value.sensor_id, params)
    historyData.value = response.items.map(item => ({
      ...item,
      location: sensorStore.sensors.find(s => s.sensor_id === item.sensor_id)?.location || ''
    }))
    currentPage.value = 1
  } catch (error) {
    ElMessage.error('查询失败')
  } finally {
    loading.value = false
  }
}

const resetFilter = () => {
  filterForm.value = { sensor_id: '', timeRange: [] }
  historyData.value = []
}

const exportData = () => {
  const sensor = sensorStore.sensors.find(s => s.sensor_id === filterForm.value.sensor_id)
  const csvContent = [
    ['时间', '传感器ID', '位置', '状态', '水位(cm)', '浸水', '供电/电量', '信号(dBm)'].join(','),
    ...historyData.value.map(row => [
      formatTime(row.recorded_at),
      row.sensor_id,
      sensor?.location || '',
      row.status,
      row.water_level ?? '',
      row.water_detected ?? '',
      row.external_powered ? '外接供电' : (row.battery_level ?? ''),
      row.signal_strength ?? ''
    ].join(','))
  ].join('\n')
  
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `sensor_data_${filterForm.value.sensor_id}_${dayjs().format('YYYYMMDD')}.csv`
  link.click()
  ElMessage.success('导出成功')
}

onMounted(() => {
  sensorStore.fetchSensors()
  refreshTimer = setInterval(() => {
    sensorStore.fetchSensors()
    if (filterForm.value.sensor_id) {
      queryHistory()
    }
  }, 10000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.page-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.filter-form {
  background: #f5f7fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.chart-section {
  height: 400px;
  margin-bottom: 20px;
}

.history-chart {
  width: 100%;
  height: 100%;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
</style>
