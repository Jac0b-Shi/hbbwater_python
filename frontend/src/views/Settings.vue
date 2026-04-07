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
                v-model="notifyConfig.smtp_user" 
                placeholder="alert@example.com" 
                autocomplete="off"
                name="smtp-user-config"
                data-lpignore="true"
                data-1p-ignore="true"
                spellcheck="false"
              />
            </el-form-item>
            <el-form-item label="SMTP密码/授权码">
              <el-input 
                :key="smtpPasswordFieldKey"
                v-model="smtpPasswordDraft" 
                type="password"
                show-password
                :placeholder="notifyConfig.smtp_password_set ? '已保存授权码；如需更新，请输入新的授权码' : '邮箱授权码或密码'"
                autocomplete="off"
                name="smtp-password-config"
                data-lpignore="true"
                data-1p-ignore="true"
                spellcheck="false"
                clearable
              />
              <span class="form-hint">{{ smtpPasswordHint }}</span>
              <el-button link type="danger" @click="clearSmtpPassword">清空已保存密码</el-button>
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
              <el-button type="primary" @click="testEmail" :disabled="!notifyConfigReady || !notifyConfig.email_enabled || !testEmailAddress.trim()" :loading="testingEmail">测试邮件</el-button>
              <el-button @click="saveNotifyConfig" :disabled="!notifyConfigReady" :loading="savingNotifyConfig">保存配置</el-button>
            </el-form-item>
            <el-divider />
            <el-form-item label="Webhook通知">
              <el-switch v-model="notifyConfig.webhook_enabled" />
            </el-form-item>
            <el-form-item label="Webhook URL">
              <el-input v-model="notifyConfig.webhook_url" placeholder="https://example.com/webhook" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="testWebhook" :disabled="!notifyConfig.webhook_enabled || !notifyConfig.webhook_url.trim()">测试 Webhook</el-button>
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
            <el-tooltip content="按保留策略归档并清理过期热数据" placement="top">
              <el-button type="primary" :loading="maintenanceLoading" @click="runMaintenance">
                <el-icon><Tools /></el-icon>执行维护任务
              </el-button>
            </el-tooltip>
            <el-tooltip content="执行 MySQL OPTIMIZE TABLE，可能需要较长时间" placement="top">
              <el-button type="warning" :loading="optimizeLoading" @click="optimizeTables">
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
import { ref, computed, onMounted, watch } from 'vue'
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
  smtp_password_set: false,
  smtp_ssl: true,
  webhook_enabled: false,
  webhook_url: ''
})

const notifyConfigReady = ref(false)
const savingNotifyConfig = ref(false)
const testingEmail = ref(false)
const smtpPasswordDraft = ref('')
const smtpPasswordFieldKey = ref(0)

const smtpPasswordHint = computed(() => {
  if (smtpPasswordDraft.value.trim()) {
    return '将使用新的授权码覆盖当前已保存值'
  }
  return notifyConfig.value.smtp_password_set ? '授权码已保存在服务器端；留空则保持不变' : '尚未保存授权码'
})

const resetSmtpPasswordDraft = () => {
  smtpPasswordDraft.value = ''
  smtpPasswordFieldKey.value += 1
}

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
  savingNotifyConfig.value = true
  try {
    const payload = {
      email_enabled: notifyConfig.value.email_enabled,
      smtp_host: notifyConfig.value.smtp_host,
      smtp_port: notifyConfig.value.smtp_port,
      smtp_user: notifyConfig.value.smtp_user,
      smtp_ssl: notifyConfig.value.smtp_ssl,
      webhook_enabled: notifyConfig.value.webhook_enabled,
      webhook_url: notifyConfig.value.webhook_url
    }

    const password = smtpPasswordDraft.value.trim()
    if (password) {
      payload.smtp_password = password
    }

    await axios.post('/api/config/notification', payload)
    resetSmtpPasswordDraft()
    notifyConfig.value.smtp_password_set = Boolean(password || notifyConfig.value.smtp_password_set)
    ElMessage.success('通知配置已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + getErrorMessage(error))
  } finally {
    savingNotifyConfig.value = false
  }
}

const clearSmtpPassword = async () => {
  try {
    await axios.post('/api/config/notification', { clear_smtp_password: true })
    resetSmtpPasswordDraft()
    notifyConfig.value.smtp_password_set = false
    ElMessage.success('已清空保存的 SMTP 密码')
  } catch (error) {
    ElMessage.error('清空失败: ' + getErrorMessage(error))
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
  testingEmail.value = true
  try {
    const response = await axios.post('/api/config/notification/test-email', { to })
    ElMessage.success(response.data.message || '测试邮件已发送')
  } catch (error) {
    ElMessage.error('发送失败: ' + getErrorMessage(error))
  } finally {
    testingEmail.value = false
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
    const response = await axios.post('/api/config/database/maintenance')
    dbStats.value = response.data.stats || dbStats.value
    ElMessage.success(response.data.message || '维护任务执行完成')
  } catch (error) {
    ElMessage.error('维护任务执行失败: ' + getErrorMessage(error))
  } finally {
    maintenanceLoading.value = false
  }
}

const optimizeTables = async () => {
  optimizeLoading.value = true
  try {
    const response = await axios.post('/api/config/database/optimize')
    dbStats.value = response.data.stats || dbStats.value
    ElMessage.success(response.data.message || '数据表优化完成')
  } catch (error) {
    ElMessage.error('优化失败: ' + getErrorMessage(error))
  } finally {
    optimizeLoading.value = false
  }
}

onMounted(async () => {
  try {
    const [systemRes, notifyRes, statsRes] = await Promise.all([
      axios.get('/api/config/system'),
      axios.get('/api/config/notification'),
      axios.get('/api/config/database/stats')
    ])
    systemConfig.value = { ...systemConfig.value, ...systemRes.data }
    notifyConfig.value = { ...notifyConfig.value, ...notifyRes.data }
    dbStats.value = { ...dbStats.value, ...statsRes.data }
    resetSmtpPasswordDraft()
    notifyConfigReady.value = true
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
</style>
