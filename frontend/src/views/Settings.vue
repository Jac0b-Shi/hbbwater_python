<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <!-- System Settings -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span>系统配置</span>
          </template>
          <el-form :model="systemConfig" label-width="150px">
            <el-form-item label="热数据保留天数">
              <el-input-number v-model="systemConfig.data_retention_days" :min="7" :max="30" />
              <span class="form-hint">天</span>
            </el-form-item>
            <el-form-item label="离线判定时间">
              <el-input-number v-model="systemConfig.offline_timeout_minutes" :min="10" :max="180" />
              <span class="form-hint">分钟</span>
            </el-form-item>
            <el-form-item label="告警冷却时间">
              <el-input-number v-model="systemConfig.alert_cooldown_minutes" :min="5" :max="120" />
              <span class="form-hint">分钟</span>
            </el-form-item>
            <el-form-item label="自动归档">
              <el-switch v-model="systemConfig.archive_enabled" />
            </el-form-item>
            <el-form-item label="数据统计">
              <el-switch v-model="systemConfig.summary_enabled" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSystemConfig">保存配置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- Notification Settings -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span>通知设置</span>
          </template>
          <!-- 隐藏的诱饵输入框 - 必须放在表单最前面才能捕获浏览器自动填充 -->
          <div style="position: fixed; top: -1000px; left: -1000px; opacity: 0; pointer-events: none;">
            <input type="text" name="email" autocomplete="email" />
            <input type="text" name="username" autocomplete="username" />
            <input type="password" name="password" autocomplete="current-password" />
            <input type="password" name="new-password" autocomplete="new-password" />
          </div>
          <el-form :model="notifyConfig" label-width="150px">
            <el-form-item label="邮件通知">
              <el-switch v-model="notifyConfig.email_enabled" />
              <span class="form-hint" style="margin-left: 10px; color: #67c23a;">通过 WordPress 发送</span>
            </el-form-item>
            <el-form-item label="SMTP服务器">
              <el-input v-model="notifyConfig.smtp_host" placeholder="smtp.example.com" />
            </el-form-item>
            <el-form-item label="SMTP端口">
              <el-input-number v-model="notifyConfig.smtp_port" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item label="发件人邮箱">
              <el-input 
                ref="smtpUserInput"
                v-model="notifyConfig.smtp_user" 
                placeholder="alert@example.com" 
                autocomplete="one-time-code" 
                name="smtp-user-field" 
                readonly
                @focus="handleInputFocus($event, 'smtpUserInput')"
                @click="handleInputClick('smtpUserInput')"
              />
            </el-form-item>
            <el-form-item label="SMTP密码/授权码">
              <el-input 
                v-model="notifyConfig.smtp_password" 
                type="password"
                show-password
                placeholder="邮箱授权码或密码" 
                autocomplete="new-password" 
                name="smtp-pass-field"
              />
            </el-form-item>
            <el-form-item label="使用SSL/TLS">
              <el-switch v-model="notifyConfig.smtp_ssl" />
              <span class="form-hint">{{ notifyConfig.smtp_ssl ? 'SSL加密（推荐）' : '明文传输' }}</span>
            </el-form-item>
            <el-form-item label="测试邮箱">
              <el-input 
                v-model="testEmailAddress" 
                placeholder="接收测试邮件的邮箱地址" 
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="testEmail" :disabled="!notifyConfig.email_enabled || !testEmailAddress.trim()">测试邮件</el-button>
              <el-button @click="saveNotifyConfig">保存配置</el-button>
            </el-form-item>
            <el-divider />
            <el-form-item label="Webhook通知">
              <el-switch v-model="notifyConfig.webhook_enabled" />
            </el-form-item>
            <el-form-item label="Webhook URL">
              <el-input v-model="notifyConfig.webhook_url" placeholder="https://example.com/webhook" />
            </el-form-item>
            <el-form-item>
              <el-tooltip content="敬请期待" placement="top">
                <el-button disabled>测试 Webhook</el-button>
              </el-tooltip>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- Database Stats -->
    <el-row :gutter="20" class="mt-4">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>数据库统计</span>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="热数据表">{{ dbStats.readings_count?.toLocaleString() }} 条</el-descriptions-item>
            <el-descriptions-item label="归档数据">{{ dbStats.archive_count?.toLocaleString() }} 条</el-descriptions-item>
            <el-descriptions-item label="小时汇总">{{ dbStats.hourly_count?.toLocaleString() }} 条</el-descriptions-item>
            <el-descriptions-item label="日汇总">{{ dbStats.daily_count?.toLocaleString() }} 条</el-descriptions-item>
          </el-descriptions>
          <div class="db-actions">
            <el-tooltip content="敬请期待" placement="top">
              <el-button type="primary" disabled>
                <el-icon><Tools /></el-icon>执行维护任务
              </el-button>
            </el-tooltip>
            <el-tooltip content="敬请期待" placement="top">
              <el-button type="warning" disabled>
                <el-icon><Rank /></el-icon>优化数据表
              </el-button>
            </el-tooltip>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- System Info -->
    <el-row :gutter="20" class="mt-4">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>系统信息</span>
          </template>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="系统版本">v1.0.0</el-descriptions-item>
            <el-descriptions-item label="API版本">v1</el-descriptions-item>
            <el-descriptions-item label="数据库">MySQL 8.0</el-descriptions-item>
            <el-descriptions-item label="后端">FastAPI</el-descriptions-item>
            <el-descriptions-item label="前端">Vue 3 + Element Plus</el-descriptions-item>
            <el-descriptions-item label="Web服务器">Caddy</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const systemConfig = ref({
  data_retention_days: 14,
  offline_timeout_minutes: 60,
  alert_cooldown_minutes: 30,
  archive_enabled: true,
  summary_enabled: true
})

const notifyConfig = ref({
  email_enabled: false,
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  smtp_ssl: true,
  webhook_enabled: false,
  webhook_url: ''
})

watch(() => notifyConfig.value.smtp_ssl, (val) => {
  notifyConfig.value.smtp_port = val ? 465 : 587
})

const testEmailAddress = ref('')

const dbStats = ref({
  readings_count: 0,
  archive_count: 0,
  hourly_count: 0,
  daily_count: 0
})

const smtpUserInput = ref(null)

// 处理输入框focus事件 - 移除readonly以允许输入
const handleInputFocus = (event, refName) => {
  if (refName === 'smtpUserInput' && smtpUserInput.value && smtpUserInput.value.input) {
    smtpUserInput.value.input.removeAttribute('readonly')
  }
}

// 处理输入框点击事件
const handleInputClick = (refName) => {
  if (refName === 'smtpUserInput' && smtpUserInput.value && smtpUserInput.value.input) {
    smtpUserInput.value.input.removeAttribute('readonly')
    smtpUserInput.value.input.focus()
  }
}

const maintenanceLoading = ref(false)
const optimizeLoading = ref(false)

const saveSystemConfig = async () => {
  try {
    await axios.post('/api/config/system', systemConfig.value)
    ElMessage.success('系统配置已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + getErrorMessage(error))
  }
}

const saveNotifyConfig = async () => {
  try {
    await axios.post('/api/config/notification', notifyConfig.value)
    ElMessage.success('通知配置已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + getErrorMessage(error))
  }
}

const getErrorMessage = (error) => {
  if (error.response?.data?.detail) return error.response.data.detail
  if (error.response?.data?.message) return error.response.data.message
  if (typeof error.response?.data === 'string') return error.response.data
  if (error.response?.data) return JSON.stringify(error.response.data)
  return error.message || '未知错误'
}

const testEmail = async () => {
  const to = testEmailAddress.value.trim()
  if (!to) {
    ElMessage.warning('请先填写测试邮箱')
    return
  }
  try {
    const response = await axios.post('/api/config/notification/test-email', { to })
    ElMessage.success(response.data.message || '测试邮件已发送')
  } catch (error) {
    ElMessage.error('发送失败: ' + getErrorMessage(error))
  }
}

const testWebhook = async () => {
  try {
    await axios.post('/api/config/notification/test-webhook')
    ElMessage.success('测试 Webhook 已发送')
  } catch (error) {
    ElMessage.error('发送失败: ' + getErrorMessage(error))
  }
}

const runMaintenance = async () => {
  maintenanceLoading.value = true
  try {
    // TODO: Call maintenance API
    await new Promise(r => setTimeout(r, 1000))
    ElMessage.success('维护任务执行完成')
  } catch {
    ElMessage.error('维护任务执行失败')
  } finally {
    maintenanceLoading.value = false
  }
}

const optimizeTables = async () => {
  optimizeLoading.value = true
  try {
    await new Promise(r => setTimeout(r, 1000))
    ElMessage.success('数据表优化完成')
  } catch {
    ElMessage.error('优化失败')
  } finally {
    optimizeLoading.value = false
  }
}

onMounted(async () => {
  try {
    const [systemRes, notifyRes] = await Promise.all([
      axios.get('/api/config/system'),
      axios.get('/api/config/notification')
    ])
    systemConfig.value = { ...systemConfig.value, ...systemRes.data }
    notifyConfig.value = { ...notifyConfig.value, ...notifyRes.data }
    
    // 防止浏览器自动填充：保存服务器返回的正确值
    const serverUser = notifyRes.data.smtp_user || ''
    const serverPass = notifyRes.data.smtp_password || ''
    
    // 多次延迟检查并强制重置值，以应对Chrome延迟自动填充
    const delays = [100, 500, 1000, 2000]
    delays.forEach(delay => {
      setTimeout(() => {
        // 如果值被浏览器自动填充覆盖了，强制重置为服务器值
        if (notifyConfig.value.smtp_user !== serverUser) {
          notifyConfig.value.smtp_user = serverUser
        }
        if (notifyConfig.value.smtp_password !== serverPass) {
          notifyConfig.value.smtp_password = serverPass
        }
      }, delay)
    })
  } catch (error) {
    ElMessage.error('加载配置失败: ' + getErrorMessage(error))
  }
})
</script>

<style scoped>
.settings-page {
  padding: 0;
}

.mt-4 {
  margin-top: 20px;
}

.form-hint {
  margin-left: 8px;
  color: #909399;
}

.db-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.form-hint {
  color: #409eff;
}
</style>
