import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

export const useAccountStore = defineStore('account', () => {
  const profile = ref(null)
  const providers = ref([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref(null)

  const displayName = computed(() => profile.value?.display_name || profile.value?.username || '管理员')
  const avatarUrl = computed(() => profile.value?.avatar_url || '')
  const authProviderLabel = computed(() => profile.value?.auth_provider_label || '本地账户')

  async function fetchProfile() {
    loading.value = true
    error.value = null

    try {
      const [{ data: profileData }, { data: providerData }] = await Promise.all([
        axios.get('/api/account/me'),
        axios.get('/api/account/providers')
      ])
      profile.value = profileData
      providers.value = providerData.providers || []
      return profileData
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch account profile:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateProfile(payload) {
    saving.value = true
    error.value = null

    try {
      const { data } = await axios.put('/api/account/me', payload)
      profile.value = data
      return data
    } catch (err) {
      error.value = err.message
      console.error('Failed to update account profile:', err)
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
      error.value = err.message
      console.error('Failed to change password:', err)
      throw err
    } finally {
      saving.value = false
    }
  }

  return {
    profile,
    providers,
    loading,
    saving,
    error,
    displayName,
    avatarUrl,
    authProviderLabel,
    fetchProfile,
    updateProfile,
    changePassword
  }
})
