<template>
  <div class="sensors-page">
    <el-card shadow="hover">
      <template #header>
        <div class="page-header">
          <h2>传感器管理</h2>
          <div class="header-actions">
            <el-input
              v-model="searchQuery"
              placeholder="搜索传感器..."
              prefix-icon="Search"
              clearable
              style="width: 200px; margin-right: 12px;"
            />
            <el-button type="primary" @click="showAddDialog = true">
              <el-icon><Plus /></el-icon>添加传感器
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="sensorStore.loading"
        :data="filteredSensors"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="sensor_id" label="传感器ID" width="150" sortable />
        <el-table-column prop="sensor_type" label="类型" width="120" sortable>
          <template #default="{ row }">
            <el-tag :type="row.sensor_type === 'ultrasonic' ? 'primary' : 'warning'">
              <el-icon v-if="row.sensor_type === 'ultrasonic'"><ScaleToOriginal /></el-icon>
              <el-icon v-else><Warning /></el-icon>
              {{ row.sensor_type === 'ultrasonic' ? '超声波' : '浸水' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="安装位置" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="预警阈值" width="150">
          <template #default="{ row }">
            <div v-if="row.sensor_type === 'ultrasonic'">
              <div>预警: {{ row.warning_level }}cm</div>
              <div>危险: {{ row.danger_level }}cm</div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              @change="(val) => toggleActive(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="上报间隔" width="150">
          <template #default="{ row }">
            <div>正常: {{ formatInterval(row.normal_interval) }}</div>
            <div>预警: {{ formatInterval(row.alert_interval) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDetail(row)">
              详情
            </el-button>
            <el-button type="primary" link @click="editSensor(row)">
              编辑
            </el-button>
            <el-button type="danger" link @click="deleteSensor(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          :total="filteredSensors.length"
        />
      </div>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingSensor ? '编辑传感器' : '添加传感器'"
      width="600px"
    >
      <el-form :model="form" label-width="120px" :rules="rules" ref="formRef">
        <el-form-item label="传感器ID" prop="sensor_id">
          <el-input v-model="form.sensor_id" placeholder="如: ultrasonic_001" :disabled="editingSensor" />
        </el-form-item>
        <el-form-item label="传感器类型" prop="sensor_type">
          <el-radio-group v-model="form.sensor_type">
            <el-radio-button label="ultrasonic">超声波</el-radio-button>
            <el-radio-button label="immersion">浸水</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="上报方式" prop="report_method">
          <el-radio-group v-model="form.report_method">
            <el-radio-button label="http_api">HTTP API</el-radio-button>
            <el-radio-button label="webhook">Webhook</el-radio-button>
            <el-tooltip content="敬请期待" placement="top">
              <el-radio-button label="mqtt" disabled>MQTT</el-radio-button>
            </el-tooltip>
            <el-tooltip content="敬请期待" placement="top">
              <el-radio-button label="coap" disabled>CoAP</el-radio-button>
            </el-tooltip>
            <el-tooltip content="敬请期待" placement="top">
              <el-radio-button label="udp_binary" disabled>UDP二进制</el-radio-button>
            </el-tooltip>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.report_method === 'webhook'" label="Webhook地址">
          <div class="webhook-box">
            <el-input
              :model-value="webhookDisplayUrl"
              readonly
            />
            <el-button type="primary" @click="copyWebhookUrl">
              <el-icon><CopyDocument /></el-icon> 复制
            </el-button>
          </div>
          <div class="webhook-hint">
            传感器通过 POST 此地址上报 JSON 数据，<el-link type="primary" @click="showWebhookExample = true">查看示例</el-link>
          </div>
        </el-form-item>
        <el-form-item label="安装位置" prop="location">
          <el-input v-model="form.location" placeholder="如: 图书馆地下室" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="3" />
        </el-form-item>
        <template v-if="form.sensor_type === 'ultrasonic'">
          <el-form-item label="预警水位(cm)">
            <el-input-number v-model="form.warning_level" :min="0" :max="500" />
          </el-form-item>
          <el-form-item label="危险水位(cm)">
            <el-input-number v-model="form.danger_level" :min="0" :max="500" />
          </el-form-item>
        </template>
        <el-form-item label="正常上报间隔">
          <el-input-number v-model="form.normal_interval" :min="60" :step="60" />
          <span class="input-hint">秒 (默认1800秒=30分钟)</span>
        </el-form-item>
        <el-form-item label="预警上报间隔">
          <el-input-number v-model="form.alert_interval" :min="60" :step="60" />
          <span class="input-hint">秒 (默认300秒=5分钟)</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveSensor">保存</el-button>
      </template>
    </el-dialog>

    <!-- Webhook JSON Example Dialog -->
    <el-dialog
      v-model="showWebhookExample"
      title="Webhook JSON 示例"
      width="500px"
    >
      <div class="webhook-example">
        <p>传感器向 Webhook 地址发送如下 JSON 结构体即可自动解析：</p>
        <pre><code>{{ webhookExample }}</code></pre>
        <ul class="webhook-notes">
          <li><code>timestamp</code> 可选，默认为服务器接收时间</li>
          <li><code>status</code> 可选，默认为 <code>normal</code></li>
          <li>超声波传感器：需包含 <code>water_level</code>（水位 cm）</li>
          <li>浸水传感器：需包含 <code>water_detected</code>（是否浸水）</li>
        </ul>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSensorStore } from '../stores/sensors'
import { CopyDocument } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const sensorStore = useSensorStore()

const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const showAddDialog = ref(false)
const editingSensor = ref(null)
const formRef = ref(null)
const newWebhookToken = ref('')

const form = ref({
  sensor_id: '',
  sensor_type: 'ultrasonic',
  report_method: 'http_api',
  location: '',
  description: '',
  warning_level: 30,
  danger_level: 50,
  normal_interval: 1800,
  alert_interval: 300,
  is_active: true
})

const showWebhookExample = ref(false)

const webhookDisplayUrl = computed(() => {
  const token = editingSensor.value?.webhook_token || newWebhookToken.value
  if (!token) return ''
  return `${window.location.origin}/api/sensors/webhook/${token}`
})

const copyWebhookUrl = async () => {
  try {
    await navigator.clipboard.writeText(webhookDisplayUrl.value)
    ElMessage.success('Webhook 地址已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

const webhookExample = computed(() => {
  if (form.value.sensor_type === 'ultrasonic') {
    return JSON.stringify({
      water_level: 25.5,
      battery_level: 85,
      signal_strength: -70,
      status: 'normal',
      timestamp: '2024-01-01T12:00:00Z'
    }, null, 2)
  }
  return JSON.stringify({
    water_detected: true,
    duration: 120,
    severity: 'high',
    status: 'danger',
    timestamp: '2024-01-01T12:00:00Z'
  }, null, 2)
})

const rules = {
  sensor_id: [{ required: true, message: '请输入传感器ID', trigger: 'blur' }],
  sensor_type: [{ required: true, message: '请选择传感器类型', trigger: 'change' }],
  location: [{ required: true, message: '请输入安装位置', trigger: 'blur' }]
}

const filter = computed(() => route.meta.filter)

const filteredSensors = computed(() => {
  let data = sensorStore.sensors
  
  if (filter.value) {
    data = data.filter(s => s.sensor_type === filter.value)
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    data = data.filter(s => 
      s.sensor_id.toLowerCase().includes(query) ||
      s.location.toLowerCase().includes(query)
    )
  }
  
  return data
})

const formatInterval = (seconds) => {
  if (seconds >= 3600) {
    return `${Math.floor(seconds / 3600)}小时`
  } else if (seconds >= 60) {
    return `${Math.floor(seconds / 60)}分钟`
  }
  return `${seconds}秒`
}

const toggleActive = async (sensor, value) => {
  try {
    await sensorStore.updateSensor(sensor.sensor_id, { is_active: value })
    ElMessage.success('状态已更新')
  } catch (error) {
    ElMessage.error('更新失败')
    sensor.is_active = !value
  }
}

const viewDetail = (sensor) => {
  router.push(`/sensors/${sensor.sensor_id}`)
}

const editSensor = (sensor) => {
  editingSensor.value = sensor
  form.value = { ...sensor }
  showAddDialog.value = true
}

const deleteSensor = async (sensor) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除传感器 ${sensor.sensor_id} 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await sensorStore.deleteSensor(sensor.sensor_id)
    ElMessage.success('删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const saveSensor = async () => {
  await formRef.value.validate()
  
  try {
    const payload = { ...form.value }
    if (form.value.report_method === 'webhook' && newWebhookToken.value) {
      payload.webhook_token = newWebhookToken.value
    }
    console.log('[DEBUG] Saving sensor, payload:', payload)  // Debug log
    if (editingSensor.value) {
      await sensorStore.updateSensor(form.value.sensor_id, payload)
      ElMessage.success('更新成功')
    } else {
      await sensorStore.createSensor(payload)
      ElMessage.success('创建成功')
    }
    showAddDialog.value = false
    resetForm()
  } catch (error) {
    console.error('[DEBUG] Save error:', error.response?.data || error)
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const resetForm = () => {
  editingSensor.value = null
  newWebhookToken.value = ''
  form.value = {
    sensor_id: '',
    sensor_type: 'ultrasonic',
    report_method: 'http_api',
    location: '',
    description: '',
    warning_level: 30,
    danger_level: 50,
    normal_interval: 1800,
    alert_interval: 300,
    is_active: true
  }
}

const ensureWebhookToken = () => {
  if (!editingSensor.value?.webhook_token && !newWebhookToken.value) {
    newWebhookToken.value = generateWebhookToken()
  }
}

const generateWebhookToken = () => {
  const chars = '0123456789abcdef'
  let token = ''
  for (let i = 0; i < 16; i++) {
    token += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return token
}

watch(showAddDialog, (val) => {
  if (!val) {
    resetForm()
  } else if (form.value.report_method === 'webhook') {
    ensureWebhookToken()
  }
})

watch(() => form.value.report_method, (val) => {
  if (val === 'webhook') {
    ensureWebhookToken()
  }
})

onMounted(() => {
  sensorStore.fetchSensors()
})
</script>

<style scoped>
.sensors-page {
  padding: 0;
}

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
  align-items: center;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.input-hint {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

.webhook-box {
  display: flex;
  gap: 8px;
}

.webhook-box .el-input {
  flex: 1;
}

.webhook-hint {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

.webhook-example pre {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
}

.webhook-notes {
  margin-top: 12px;
  padding-left: 18px;
  color: #606266;
  font-size: 13px;
}

.webhook-notes li {
  margin-bottom: 6px;
}

.webhook-notes code {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  color: #409eff;
}
</style>
