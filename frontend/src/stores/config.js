/**
 * Configuration state store
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { configApi } from '@/api/config'

export const useConfigStore = defineStore('config', () => {
  // State
  const categories = ref([])
  const configs = ref({})
  const loading = ref(false)
  const saving = ref(false)

  // Actions
  async function fetchCategories() {
    loading.value = true
    try {
      const response = await configApi.listCategories()
      categories.value = response.data?.categories || []
    } finally {
      loading.value = false
    }
  }

  async function fetchConfig(category) {
    loading.value = true
    try {
      const response = await configApi.get(category)
      configs.value[category] = response.data
      return response.data
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(category, updates) {
    saving.value = true
    try {
      const response = await configApi.update(category, updates)
      configs.value[category] = response.data
      return response.data
    } finally {
      saving.value = false
    }
  }

  async function setSecret(category, keyName, value) {
    saving.value = true
    try {
      const response = await configApi.setSecret(category, keyName, value)
      // Update masked value in config
      if (configs.value[category]) {
        configs.value[category][`${keyName}_masked`] = response.data.masked
        configs.value[category][`${keyName}_configured`] = response.data.configured
      }
      return response.data
    } finally {
      saving.value = false
    }
  }

  async function deleteSecret(category, keyName) {
    saving.value = true
    try {
      await configApi.deleteSecret(category, keyName)
      if (configs.value[category]) {
        configs.value[category][`${keyName}_masked`] = ''
        configs.value[category][`${keyName}_configured`] = false
      }
    } finally {
      saving.value = false
    }
  }

  async function resetConfig(category) {
    saving.value = true
    try {
      const response = await configApi.reset(category)
      configs.value[category] = response.data
      return response.data
    } finally {
      saving.value = false
    }
  }

  function getConfig(category) {
    return configs.value[category] || null
  }

  return {
    categories,
    configs,
    loading,
    saving,
    fetchCategories,
    fetchConfig,
    updateConfig,
    setSecret,
    deleteSecret,
    resetConfig,
    getConfig
  }
})
