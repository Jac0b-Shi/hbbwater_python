import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Dashboard',
      component: Dashboard,
      meta: { title: '监控仪表盘' }
    },
    {
      path: '/sensors',
      name: 'Sensors',
      component: () => import('../views/Sensors.vue'),
      meta: { title: '传感器管理' }
    },
    {
      path: '/sensors/ultrasonic',
      name: 'UltrasonicSensors',
      component: () => import('../views/Sensors.vue'),
      meta: { title: '超声波传感器', filter: 'ultrasonic' }
    },
    {
      path: '/sensors/immersion',
      name: 'ImmersionSensors',
      component: () => import('../views/Sensors.vue'),
      meta: { title: '浸水传感器', filter: 'immersion' }
    },
    {
      path: '/sensors/:id',
      name: 'SensorDetail',
      component: () => import('../views/SensorDetail.vue'),
      meta: { title: '传感器详情' }
    },
    {
      path: '/alerts',
      name: 'Alerts',
      component: () => import('../views/Alerts.vue'),
      meta: { title: '告警管理' }
    },
    {
      path: '/history',
      name: 'History',
      component: () => import('../views/History.vue'),
      meta: { title: '历史数据' }
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../views/Settings.vue'),
      meta: { title: '系统设置' }
    },
    {
      path: '/profile',
      name: 'Profile',
      component: () => import('../views/Profile.vue'),
      meta: { title: '个人设置' }
    }
  ],
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - 水浸监测系统` : '水浸监测系统'
  next()
})

export default router
