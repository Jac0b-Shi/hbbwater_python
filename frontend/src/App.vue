<template>
  <router-view v-if="isAuthLayout" />

  <div v-else class="app-wrapper">
    <el-container class="main-container">
      <el-aside width="220px" class="sidebar">
        <div class="logo">
          <el-icon size="32"><Drizzling /></el-icon>
          <span class="logo-text">水浸监测系统</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          :collapse="isCollapse"
          :collapse-transition="false"
          router
        >
          <el-menu-item index="/">
            <el-icon><Odometer /></el-icon>
            <template #title>监控仪表盘</template>
          </el-menu-item>

          <el-menu-item index="/water-map">
            <el-icon><LocationFilled /></el-icon>
            <template #title>水位地图</template>
          </el-menu-item>

          <el-sub-menu index="/sensors">
            <template #title>
              <el-icon><Cpu /></el-icon>
              <span>传感器管理</span>
            </template>
            <el-menu-item index="/sensors">全部传感器</el-menu-item>
            <el-menu-item index="/sensors/ultrasonic">超声波传感器</el-menu-item>
            <el-menu-item index="/sensors/immersion">浸水传感器</el-menu-item>
          </el-sub-menu>

          <el-menu-item index="/alerts">
            <el-icon><Bell /></el-icon>
            <template #title>
              <span>告警管理</span>
              <el-badge v-if="alertStore.unresolvedCount > 0" :value="alertStore.unresolvedCount" class="alert-badge" />
            </template>
          </el-menu-item>

          <el-menu-item index="/history">
            <el-icon><TrendCharts /></el-icon>
            <template #title>历史数据</template>
          </el-menu-item>

          <el-menu-item v-if="accountStore.canManageUsers" index="/users">
            <el-icon><UserFilled /></el-icon>
            <template #title>用户管理</template>
          </el-menu-item>

          <el-menu-item v-if="accountStore.canAccessSettings" index="/settings">
            <el-icon><Setting /></el-icon>
            <template #title>系统设置</template>
          </el-menu-item>
        </el-menu>

        <div class="sidebar-footer">
          <el-tag size="small" type="info">{{ accountStore.roleLabel }}</el-tag>
          <el-text type="info" size="small">{{ APP_VERSION }}</el-text>
        </div>
      </el-aside>

      <el-container>
        <el-header class="main-header">
          <div class="header-left">
            <el-icon class="collapse-btn" @click="toggleCollapse">
              <Fold v-if="!isCollapse" />
              <Expand v-else />
            </el-icon>
            <breadcrumb />
          </div>
          <div class="header-right">
            <el-tag v-if="!accountStore.canManageSensors" effect="plain" round>只读模式</el-tag>
            <el-tooltip content="刷新数据" placement="bottom">
              <el-icon class="header-icon" @click="refreshData"><Refresh /></el-icon>
            </el-tooltip>
            <el-tooltip content="全屏" placement="bottom">
              <el-icon class="header-icon" @click="toggleFullscreen"><FullScreen /></el-icon>
            </el-tooltip>
            <el-dropdown trigger="click">
              <span class="user-info">
                <el-avatar :size="32" :src="accountStore.avatarUrl" :icon="UserFilled" />
                <span class="username">{{ accountStore.displayName }}</span>
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="$router.push('/profile')">个人设置</el-dropdown-item>
                  <el-dropdown-item v-if="accountStore.canManageUsers" @click="$router.push('/users')">用户管理</el-dropdown-item>
                  <el-dropdown-item v-if="accountStore.canAccessSettings" @click="$router.push('/settings')">系统设置</el-dropdown-item>
                  <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade-transform" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAlertStore } from './stores/alerts'
import { useAccountStore } from './stores/account'
import Breadcrumb from './components/Breadcrumb.vue'
import { APP_VERSION } from './constants/appMeta'

const route = useRoute()
const router = useRouter()
const alertStore = useAlertStore()
const accountStore = useAccountStore()

const isCollapse = ref(false)

const activeMenu = computed(() => route.path)
const isAuthLayout = computed(() => route.meta.layout === 'auth')

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const refreshData = () => {
  window.location.reload()
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

const handleLogout = async () => {
  await accountStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-wrapper {
  height: 100vh;
  width: 100vw;
}

.main-container {
  height: 100%;
}

.sidebar {
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.el-menu-vertical {
  flex: 1;
  border-right: none;
  background: transparent;
}

.el-menu-vertical :deep(.el-menu-item),
.el-menu-vertical :deep(.el-sub-menu__title) {
  color: #a6aab3;
}

.el-menu-vertical :deep(.el-menu-item:hover),
.el-menu-vertical :deep(.el-sub-menu__title:hover) {
  background: rgba(255,255,255,0.05);
  color: #fff;
}

.el-menu-vertical :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(64,158,255,0.2) 0%, transparent 100%);
  color: #409eff;
  border-right: 3px solid #409eff;
}

.sidebar-footer {
  padding: 16px;
  text-align: center;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: grid;
  gap: 10px;
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #606266;
}

.collapse-btn:hover {
  color: #409eff;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.header-icon {
  font-size: 20px;
  cursor: pointer;
  color: #606266;
}

.header-icon:hover {
  color: #409eff;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.username {
  font-size: 14px;
  color: #606266;
}

.main-content {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}

.alert-badge :deep(.el-badge__content) {
  top: 10px;
  right: 30px;
}

.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.3s;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
