<template>
  <div class="alerts-page">
    <el-card shadow="hover">
      <template #header>
        <div class="page-header">
          <h2>告警管理</h2>
          <div class="header-actions">
            <el-tag v-if="!accountStore.canResolveAlerts" effect="plain" type="info">当前账号仅可查看</el-tag>
            <el-radio-group v-model="filterStatus" size="small">
              <el-radio-button label="all">全部</el-radio-button>
              <el-radio-button label="active">未处理</el-radio-button>
              <el-radio-button label="resolved">已处理</el-radio-button>
            </el-radio-group>
            <el-button type="primary" size="small" @click="refreshAlerts">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- Alert Stats -->
      <el-row :gutter="20" class="stats-row">
        <el-col :xs="12" :sm="6">
          <div class="stat-box">
            <div class="stat-number critical">{{ alertStore.criticalAlerts.length }}</div>
            <div class="stat-label">紧急告警</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-box">
            <div class="stat-number high">{{ alertStore.highAlerts.length }}</div>
            <div class="stat-label">高优先级</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-box">
            <div class="stat-number medium">{{ alertStore.activeAlerts.filter(a => a.severity === 'medium').length }}</div>
            <div class="stat-label">中优先级</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-box">
            <div class="stat-number total">{{ alertStore.unresolvedCount }}</div>
            <div class="stat-label">未处理总数</div>
          </div>
        </el-col>
      </el-row>

      <!-- Alerts Table -->
      <el-table
        v-loading="alertStore.loading"
        :data="filteredAlerts"
        stripe
        style="width: 100%"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="alert-detail">
              <p><strong>详细信息:</strong></p>
              <pre>{{ JSON.stringify(row.details, null, 2) }}</pre>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="severity" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="getSeverityType(row.severity)">
              {{ getSeverityText(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="alert_type" label="类型" width="150">
          <template #default="{ row }">
            <el-tag effect="plain">{{ getAlertTypeText(row.alert_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sensor_id" label="传感器" width="150" />
        <el-table-column prop="message" label="消息" show-overflow-tooltip />
        <el-table-column prop="is_resolved" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_resolved ? 'success' : 'danger'">
              {{ row.is_resolved ? '已处理' : '未处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.is_resolved && accountStore.canResolveAlerts"
              type="primary" 
              size="small" 
              @click="resolveAlert(row)"
            >
              处理
            </el-button>
            <span v-else-if="!row.is_resolved" class="resolved-info">只读</span>
            <span v-else class="resolved-info">
              处理人: {{ row.resolved_by }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Resolve Dialog -->
    <el-dialog v-model="showResolveDialog" title="处理告警" width="400px">
      <el-form :model="resolveForm">
        <el-form-item label="处理人">
          <el-input v-model="resolveForm.resolved_by" placeholder="请输入处理人姓名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResolveDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmResolve">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '../stores/account'
import { useAlertStore } from '../stores/alerts'
import dayjs from 'dayjs'

const accountStore = useAccountStore()
const alertStore = useAlertStore()

const filterStatus = ref('active')
const showResolveDialog = ref(false)
const currentAlert = ref(null)
const resolveForm = ref({ resolved_by: '' })
let refreshTimer = null

const filteredAlerts = computed(() => {
  if (filterStatus.value === 'active') {
    return alertStore.activeAlerts
  } else if (filterStatus.value === 'resolved') {
    return alertStore.alerts.filter(a => a.is_resolved)
  }
  return alertStore.alerts
})

const getSeverityType = (severity) => {
  const map = { low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[severity] || 'info'
}

const getSeverityText = (severity) => {
  const map = { low: '低', medium: '中', high: '高', critical: '紧急' }
  return map[severity] || severity
}

const getAlertTypeText = (type) => {
  const map = {
    high_water: '高水位',
    water_detected: '浸水检测',
    sensor_offline: '传感器离线',
    low_battery: '低电量'
  }
  return map[type] || type
}

const formatTime = (time) => dayjs(time).format('YYYY-MM-DD HH:mm:ss')

const refreshAlerts = () => {
  alertStore.fetchAlerts()
}

const resolveAlert = (alert) => {
  currentAlert.value = alert
  resolveForm.value.resolved_by = accountStore.displayName
  showResolveDialog.value = true
}

const confirmResolve = async () => {
  if (!resolveForm.value.resolved_by) {
    ElMessage.warning('请输入处理人')
    return
  }
  
  try {
    await alertStore.resolveAlert(currentAlert.value.id, resolveForm.value.resolved_by)
    ElMessage.success('告警已处理')
    showResolveDialog.value = false
  } catch {
    ElMessage.error('处理失败')
  }
}

onMounted(() => {
  alertStore.fetchAlerts()
  refreshTimer = setInterval(() => {
    alertStore.fetchAlerts()
  }, 10000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-box {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.stat-number {
  font-size: 32px;
  font-weight: 600;
  margin-bottom: 8px;
}

.stat-number.critical { color: #f56c6c; }
.stat-number.high { color: #e6a23c; }
.stat-number.medium { color: #409eff; }
.stat-number.total { color: #67c23a; }

.stat-label {
  color: #909399;
  font-size: 14px;
}

.alert-detail {
  padding: 10px 20px;
  background: #f5f7fa;
  border-radius: 4px;
}

.alert-detail pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
}

.resolved-info {
  font-size: 12px;
  color: #909399;
}
</style>
