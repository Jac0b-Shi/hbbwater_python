<template>
  <div class="profile-page">
    <el-row :gutter="20">
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="profile-card">
          <div class="profile-header">
            <el-avatar :size="100" :icon="UserFilled" />
            <h3>管理员</h3>
            <p class="profile-role">系统管理员</p>
          </div>
          <div class="profile-info">
            <p><el-icon><Message /></el-icon> admin@example.com</p>
            <p><el-icon><Phone /></el-icon> 未设置</p>
            <p><el-icon><Timer /></el-icon> 注册时间：2024-01-01</p>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :md="16">
        <el-card shadow="hover">
          <template #header>
            <span>编辑资料</span>
          </template>
          <el-form :model="profileForm" label-width="100px">
            <el-form-item label="用户名">
              <el-input v-model="profileForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveProfile">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        
        <el-card shadow="hover" class="mt-4">
          <template #header>
            <span>修改密码</span>
          </template>
          <el-form :model="passwordForm" label-width="100px">
            <el-form-item label="当前密码">
              <el-input v-model="passwordForm.current" type="password" show-password placeholder="请输入当前密码" />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="passwordForm.new" type="password" show-password placeholder="请输入新密码" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="passwordForm.confirm" type="password" show-password placeholder="请再次输入新密码" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="changePassword">修改密码</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UserFilled, Message, Phone, Timer } from '@element-plus/icons-vue'

const profileForm = ref({
  username: '管理员',
  email: 'admin@example.com',
  phone: ''
})

const passwordForm = ref({
  current: '',
  new: '',
  confirm: ''
})

const saveProfile = () => {
  // TODO: Call API to save profile
  ElMessage.success('资料已保存')
}

const changePassword = () => {
  if (passwordForm.value.new !== passwordForm.value.confirm) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  // TODO: Call API to change password
  ElMessage.success('密码已修改')
  passwordForm.value = { current: '', new: '', confirm: '' }
}
</script>

<style scoped>
.profile-page {
  padding: 0;
}

.profile-card {
  text-align: center;
}

.profile-header {
  padding: 20px 0;
}

.profile-header h3 {
  margin: 16px 0 8px;
  font-size: 20px;
}

.profile-role {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.profile-info {
  text-align: left;
  padding: 20px;
  border-top: 1px solid #ebeef5;
}

.profile-info p {
  margin: 12px 0;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mt-4 {
  margin-top: 20px;
}
</style>
