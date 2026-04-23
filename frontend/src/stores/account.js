import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

const ACCESS_TOKEN_KEY = 'hbbwater_access_token'

function applyToken(token) {
  if (token) {
    axios.defaults.headers.common.Authorization = `Bearer ${token}`
    localStorage.setItem(ACCESS_TOKEN_KEY, token)
  } else {
    delete axios.defaults.headers.common.Authorization
    localStorage.removeItem(ACCESS_TOKEN_KEY)
  }
}

export const useAccountStore = defineStore('account', () => {
  const token = ref(localStorage.getItem(ACCESS_TOKEN_KEY) || '')
  const profile = ref(null)
  const providers = ref([])
  const roles = ref([])
  const users = ref([])
  const registrationStatus = ref({
    bootstrap_mode: false,
    requires_email_verification: true
  })
  const loading = ref(false)
  const saving = ref(false)
  const authReady = ref(false)
  const error = ref(null)
  let pendingProfileRequest = null

  applyToken(token.value)

  const isAuthenticated = computed(() => Boolean(token.value && profile.value))
  const displayName = computed(() => profile.value?.display_name || profile.value?.username || '未登录')
  const avatarUrl = computed(() => profile.value?.avatar_url || '')
  const authProviderLabel = computed(() => profile.value?.auth_provider_label || '本地账户')
  const role = computed(() => profile.value?.role || 'user')
  const roleLabel = computed(() => profile.value?.role_label || '用户')
  const permissions = computed(() => profile.value?.permissions || [])
  const canManageUsers = computed(() => permissions.value.includes('users:write'))
  const canManageSensors = computed(() => permissions.value.includes('sensors:write'))
  const canResolveAlerts = computed(() => permissions.value.includes('alerts:resolve'))
  const canAccessSettings = computed(() => permissions.value.includes('settings:write'))

  function setToken(nextToken) {
    token.value = nextToken || ''
    applyToken(token.value)
  }

  function clearSession() {
    setToken('')
    profile.value = null
    providers.value = []
    roles.value = []
    users.value = []
  }

  async function fetchProfile(force = false) {
    if (pendingProfileRequest && !force) {
      return pendingProfileRequest
    }

    loading.value = true
    error.value = null

    pendingProfileRequest = (async () => {
      try {
        const [{ data: profileData }, { data: providerData }, { data: roleData }] = await Promise.all([
          axios.get('/api/account/me'),
          axios.get('/api/account/providers'),
          axios.get('/api/account/roles')
        ])
        profile.value = profileData
        providers.value = providerData.providers || []
        roles.value = roleData.roles || []
        return profileData
      } catch (err) {
        error.value = err.response?.data?.detail || err.message
        if ([401, 403].includes(err.response?.status)) {
          clearSession()
        }
        throw err
      } finally {
        loading.value = false
        pendingProfileRequest = null
      }
    })()

    return pendingProfileRequest
  }

  async function initializeAuth() {
    if (authReady.value) {
      return
    }

    if (!token.value) {
      authReady.value = true
      return
    }

    try {
      await fetchProfile()
    } catch {
      clearSession()
    } finally {
      authReady.value = true
    }
  }

  async function login(payload) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.post('/api/auth/login', payload)
      setToken(data.access_token)
      profile.value = data.user
      authReady.value = true
      await fetchProfile(true)
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      saving.value = false
    }
  }

  async function requestRegisterCode(email) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.post('/api/auth/register/request-code', { email })
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      saving.value = false
    }
  }

  async function fetchRegistrationStatus() {
    error.value = null

    try {
      const { data } = await axios.get('/api/auth/registration-status')
      registrationStatus.value = {
        bootstrap_mode: Boolean(data.bootstrap_mode),
        requires_email_verification: Boolean(data.requires_email_verification)
      }
      return registrationStatus.value
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    }
  }

  async function register(payload) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.post('/api/auth/register', payload)
      setToken(data.access_token)
      profile.value = data.user
      authReady.value = true
      await fetchProfile(true)
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      saving.value = false
    }
  }

  async function logout() {
    try {
      await axios.post('/api/auth/logout')
    } catch {
      // Frontend clears the session regardless of backend response.
    }
    clearSession()
    authReady.value = true
  }

  async function updateProfile(payload) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.put('/api/account/me', payload)
      profile.value = data
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      saving.value = false
    }
  }

  async function changePassword(payload) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.post('/api/account/me/password', payload)
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      saving.value = false
    }
  }

  async function fetchUsers() {
    loading.value = true
    error.value = null

    try {
      const { data } = await axios.get('/api/account/admin-users')
      users.value = data
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createUser(payload) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.post('/api/account/admin-users', payload)
      users.value.push(data)
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      saving.value = false
    }
  }

  async function updateUser(userId, payload) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.patch(`/api/account/admin-users/${userId}`, payload)
      const index = users.value.findIndex((item) => item.id === String(userId) || item.id === userId)
      if (index !== -1) {
        users.value[index] = data
      }
      if (profile.value?.id === String(userId)) {
        profile.value = data
      }
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      throw err
    } finally {
      saving.value = false
    }
  }

  function hasAnyRole(allowedRoles = []) {
    return allowedRoles.includes(role.value)
  }

  return {
    token,
    profile,
    providers,
    roles,
    users,
    registrationStatus,
    loading,
    saving,
    authReady,
    error,
    isAuthenticated,
    displayName,
    avatarUrl,
    authProviderLabel,
    role,
    roleLabel,
    permissions,
    canManageUsers,
    canManageSensors,
    canResolveAlerts,
    canAccessSettings,
    initializeAuth,
    fetchProfile,
    login,
    requestRegisterCode,
    fetchRegistrationStatus,
    register,
    logout,
    updateProfile,
    changePassword,
    fetchUsers,
    createUser,
    updateUser,
    hasAnyRole,
    clearSession
  }
})
