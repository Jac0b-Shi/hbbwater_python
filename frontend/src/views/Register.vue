<template>
  <div class="auth-page">
    <div class="auth-panel form-panel">
      <div class="panel-header">
        <h2>{{ requiresEmailVerification ? '邮箱验证注册' : '初始化超级管理员' }}</h2>
        <p>
          {{
            requiresEmailVerification
              ? '验证码会发送到系统设置里配置的发信渠道，请先确保通知设置中的邮箱配置可用。'
              : '系统当前还没有可用的超级管理员。首个用户可直接注册，无需邮箱验证码，注册完成后会自动成为超级管理员。'
          }}
        </p>
      </div>

      <el-alert
        :title="requiresEmailVerification ? '首个完成注册并成功设置密码的账号会自动成为超级管理员。' : '当前处于初始化模式，本次注册将直接创建超级管理员账号。'"
        :type="requiresEmailVerification ? 'info' : 'warning'"
        :closable="false"
        class="register-alert"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" size="large" placeholder="2-50 位，用于登录" />
        </el-form-item>
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="form.display_name" size="large" placeholder="界面显示名称" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" size="large" placeholder="name@example.com" />
        </el-form-item>
        <el-form-item v-if="requiresEmailVerification" label="邮箱验证码" prop="verification_code">
          <div class="code-row">
            <el-input v-model="form.verification_code" size="large" placeholder="请输入 6 位验证码" />
            <el-button
              size="large"
              :loading="sendingCode"
              :disabled="countdown > 0"
              @click="sendCode"
            >
              {{ countdown > 0 ? `${countdown}s 后重发` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item v-else label="初始化说明">
          <el-text type="info">当前无需验证码。完成注册后，请尽快到系统设置里配置通知邮箱。</el-text>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password size="large" placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="form.confirm_password" type="password" show-password size="large" placeholder="请再次输入密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" class="submit-btn" :loading="accountStore.saving || loadingStatus" @click="submitRegister">
            {{ requiresEmailVerification ? '完成注册' : '创建超级管理员' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="panel-footer">
        <span>已经有账号？</span>
        <router-link to="/login">返回登录</router-link>
      </div>
    </div>

    <div class="auth-panel brand-panel">
      <div class="brand-badge">REGISTER</div>
      <h1>按角色接入系统</h1>
      <p>
        注册后系统会按用户角色自动限制功能范围。
        超级管理员可管理用户与系统设置，管理员可管理传感器，普通用户保留只读访问。
      </p>
      <div class="brand-points">
        <div class="point-card">
          <strong>超级管理员</strong>
          <span>用户管理、权限分配、系统设置、全部业务管理</span>
        </div>
        <div class="point-card">
          <strong>管理员</strong>
          <span>传感器管理、状态切换、告警处理</span>
        </div>
        <div class="point-card">
          <strong>用户</strong>
          <span>查看仪表盘、历史数据、告警和个人资料</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAccountStore } from '../stores/account'
import { validatePassword } from '../utils/password'

const route = useRoute()
const router = useRouter()
const accountStore = useAccountStore()
const formRef = ref(null)
const sendingCode = ref(false)
const countdown = ref(0)
const loadingStatus = ref(false)
let countdownTimer = null

const form = ref({
  username: '',
  display_name: '',
  email: '',
  verification_code: '',
  password: '',
  confirm_password: ''
})

const requiresEmailVerification = computed(() => accountStore.registrationStatus.requires_email_verification)

const rules = computed(() => ({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
  verification_code: requiresEmailVerification.value
    ? [{ required: true, message: '请输入验证码', trigger: 'blur' }]
    : [],
  password: [{
    validator: (_, value, callback) => {
      const error = validatePassword(value, { requiredMessage: '请输入密码' })
      callback(error ? new Error(error) : undefined)
    },
    trigger: 'blur'
  }],
  confirm_password: [{ required: true, message: '请再次输入密码', trigger: 'blur' }]
}))

const startCountdown = () => {
  countdown.value = 60
  countdownTimer = window.setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

const loadRegistrationStatus = async () => {
  loadingStatus.value = true
  try {
    await accountStore.fetchRegistrationStatus()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || accountStore.error || '注册状态加载失败')
  } finally {
    loadingStatus.value = false
  }
}

const sendCode = async () => {
  if (!requiresEmailVerification.value) {
    ElMessage.info('当前为初始化模式，无需邮箱验证码')
    return
  }

  if (!form.value.email.trim()) {
    ElMessage.warning('请先填写邮箱')
    return
  }

  sendingCode.value = true
  try {
    await accountStore.requestRegisterCode(form.value.email.trim())
    ElMessage.success('验证码已发送，请检查邮箱')
    startCountdown()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || accountStore.error || '验证码发送失败')
  } finally {
    sendingCode.value = false
  }
}

const submitRegister = async () => {
  await formRef.value.validate()

  if (form.value.password !== form.value.confirm_password) {
    ElMessage.error('两次输入的密码不一致')
    return
  }

  const passwordError = validatePassword(form.value.password, { requiredMessage: '请输入密码' })
  if (passwordError) {
    ElMessage.error(passwordError)
    return
  }

  try {
    await accountStore.register({
      username: form.value.username.trim(),
      display_name: form.value.display_name.trim(),
      email: form.value.email.trim(),
      verification_code: requiresEmailVerification.value ? form.value.verification_code.trim() : null,
      password: form.value.password
    })
    ElMessage.success(requiresEmailVerification.value ? '注册成功' : '超级管理员创建成功')
    router.push(route.query.redirect || '/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || accountStore.error || '注册失败')
  }
}

onMounted(async () => {
  await loadRegistrationStatus()
})

onBeforeUnmount(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }
})
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 0.94fr 1.06fr;
  background:
    radial-gradient(circle at top right, rgba(34, 197, 94, 0.16), transparent 24%),
    radial-gradient(circle at left center, rgba(59, 130, 246, 0.12), transparent 26%),
    linear-gradient(135deg, #f4f8ff 0%, #fcfdfd 48%, #eef8f3 100%);
}

.auth-panel {
  padding: 44px 48px;
}

.form-panel {
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(14px);
}

.panel-header {
  margin-bottom: 18px;
}

.panel-header h2 {
  margin: 0 0 10px;
  font-size: 32px;
  color: #14213d;
}

.panel-header p {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.register-alert {
  margin-bottom: 18px;
}

.code-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  width: 100%;
}

.submit-btn {
  width: 100%;
  height: 48px;
}

.panel-footer {
  margin-top: 18px;
  color: #64748b;
}

.panel-footer a {
  margin-left: 6px;
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
}

.brand-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 20px;
}

.brand-badge {
  width: fit-content;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(5, 150, 105, 0.1);
  color: #065f46;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.2em;
}

.brand-panel h1 {
  margin: 0;
  font-size: 44px;
  color: #14213d;
}

.brand-panel p {
  max-width: 560px;
  margin: 0;
  color: #51627a;
  line-height: 1.8;
  font-size: 16px;
}

.brand-points {
  display: grid;
  gap: 14px;
  max-width: 560px;
}

.point-card {
  display: grid;
  gap: 8px;
  padding: 18px 20px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(20, 33, 61, 0.08);
  box-shadow: 0 18px 44px rgba(20, 33, 61, 0.06);
}

.point-card strong {
  color: #14213d;
}

.point-card span {
  color: #64748b;
}

@media (max-width: 980px) {
  .auth-page {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .auth-panel {
    padding: 28px 20px;
  }

  .code-row {
    grid-template-columns: 1fr;
  }

  .brand-panel h1 {
    font-size: 34px;
  }
}
</style>
