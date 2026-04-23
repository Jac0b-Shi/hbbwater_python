import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import { useAccountStore } from '../stores/account'
import { pinia } from '../stores'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', layout: 'auth', publicOnly: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { title: '注册', layout: 'auth', publicOnly: true }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: { title: '监控仪表盘', requiresAuth: true }
  },
  {
    path: '/sensors',
    name: 'Sensors',
    component: () => import('../views/Sensors.vue'),
    meta: { title: '传感器管理', requiresAuth: true }
  },
  {
    path: '/sensors/ultrasonic',
    name: 'UltrasonicSensors',
    component: () => import('../views/Sensors.vue'),
    meta: { title: '超声波传感器', filter: 'ultrasonic', requiresAuth: true }
  },
  {
    path: '/sensors/immersion',
    name: 'ImmersionSensors',
    component: () => import('../views/Sensors.vue'),
    meta: { title: '浸水传感器', filter: 'immersion', requiresAuth: true }
  },
  {
    path: '/sensors/:id',
    name: 'SensorDetail',
    component: () => import('../views/SensorDetail.vue'),
    meta: { title: '传感器详情', requiresAuth: true }
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('../views/Alerts.vue'),
    meta: { title: '告警管理', requiresAuth: true }
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/History.vue'),
    meta: { title: '历史数据', requiresAuth: true }
  },
  {
    path: '/users',
    name: 'Users',
    component: () => import('../views/UserManagement.vue'),
    meta: { title: '用户管理', requiresAuth: true, allowedRoles: ['super_admin'] }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue'),
    meta: { title: '系统设置', requiresAuth: true, allowedRoles: ['super_admin'] }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Profile.vue'),
    meta: { title: '个人设置', requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach(async (to) => {
  document.title = to.meta.title ? `${to.meta.title} - 水浸监测系统` : '水浸监测系统'

  const accountStore = useAccountStore(pinia)
  await accountStore.initializeAuth()

  if (to.meta.requiresAuth && !accountStore.isAuthenticated) {
    return {
      path: '/login',
      query: { redirect: to.fullPath }
    }
  }

  if (to.meta.publicOnly && accountStore.isAuthenticated) {
    return to.query.redirect || '/'
  }

  if (to.meta.allowedRoles?.length && !accountStore.hasAnyRole(to.meta.allowedRoles)) {
    return '/'
  }

  return true
})

export default router
