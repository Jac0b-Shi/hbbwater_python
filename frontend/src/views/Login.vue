<template>
  <div class="auth-page">
    <div class="auth-panel brand-panel">
      <div class="brand-badge">HBBWATER</div>
      <h1>校园水浸监测系统</h1>
      <p>
        登录后可按权限访问监控、告警、传感器管理和系统配置。
        超级管理员负责用户与系统设置，管理员负责传感器，普通用户仅查看。
      </p>
      <div class="brand-points">
        <div class="point-card">
          <strong>实时监测</strong>
          <span>统一查看超声波与浸水传感器状态</span>
        </div>
        <div class="point-card">
          <strong>角色隔离</strong>
          <span>登录后自动按权限裁剪菜单与操作</span>
        </div>
        <div class="point-card">
          <strong>注册校验</strong>
          <span>新账号通过邮箱验证码完成注册</span>
        </div>
      </div>
    </div>

    <div class="auth-panel form-panel">
      <div class="panel-header">
        <h2>账号登录</h2>
        <p>使用用户名或邮箱登录系统</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submitLogin">
        <el-form-item label="登录名 / 邮箱" prop="login">
          <el-input v-model="form.login" size="large" placeholder="请输入用户名或邮箱" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password size="large" placeholder="请输入密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" class="submit-btn" :loading="accountStore.saving" @click="submitLogin">
            登录系统
          </el-button>
        </el-form-item>
      </el-form>

      <div class="panel-footer">
        <span>还没有账号？</span>
        <router-link to="/register">去注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAccountStore } from '../stores/account'

const route = useRoute()
const router = useRouter()
const accountStore = useAccountStore()
const formRef = ref(null)

const form = ref({
  login: '',
  password: ''
})

const rules = {
  login: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const submitLogin = async () => {
  await formRef.value.validate()
  try {
    await accountStore.login(form.value)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || accountStore.error || '登录失败')
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  background:
    radial-gradient(circle at top left, rgba(47, 111, 237, 0.22), transparent 34%),
    radial-gradient(circle at bottom right, rgba(16, 185, 129, 0.16), transparent 28%),
    linear-gradient(135deg, #eef4fb 0%, #f8fbff 50%, #eef8f4 100%);
}

.auth-panel {
  padding: 48px;
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
  background: rgba(22, 33, 62, 0.08);
  color: #16213e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.24em;
}

.brand-panel h1 {
  margin: 0;
  font-size: 46px;
  line-height: 1.08;
  color: #14213d;
}

.brand-panel p {
  max-width: 620px;
  margin: 0;
  color: #51627a;
  font-size: 16px;
  line-height: 1.8;
}

.brand-points {
  display: grid;
  gap: 14px;
  max-width: 620px;
}

.point-card {
  display: grid;
  gap: 6px;
  padding: 18px 20px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(20, 33, 61, 0.08);
  box-shadow: 0 18px 44px rgba(20, 33, 61, 0.06);
}

.point-card strong {
  color: #14213d;
}

.point-card span {
  color: #64748b;
}

.form-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: rgba(255, 255, 255, 0.74);
  backdrop-filter: blur(12px);
  border-left: 1px solid rgba(20, 33, 61, 0.08);
}

.panel-header {
  margin-bottom: 24px;
}

.panel-header h2 {
  margin: 0 0 10px;
  font-size: 32px;
  color: #14213d;
}

.panel-header p {
  margin: 0;
  color: #64748b;
}

.submit-btn {
  width: 100%;
  height: 48px;
}

.panel-footer {
  margin-top: 20px;
  color: #64748b;
}

.panel-footer a {
  margin-left: 6px;
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
}

@media (max-width: 980px) {
  .auth-page {
    grid-template-columns: 1fr;
  }

  .brand-panel {
    padding-bottom: 0;
  }

  .form-panel {
    border-left: none;
    border-top: 1px solid rgba(20, 33, 61, 0.08);
  }
}

@media (max-width: 640px) {
  .auth-panel {
    padding: 28px 20px;
  }

  .brand-panel h1 {
    font-size: 34px;
  }
}
</style>
