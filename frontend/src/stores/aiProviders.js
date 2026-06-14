/**
 * AI Providers Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { aiProvidersApi } from '@/api/aiProviders'

export const useAIProvidersStore = defineStore('aiProviders', () => {
  // State
  const providers = ref([])
  const providerTypes = ref([])
  const loading = ref(false)
  const error = ref(null)

  // Getters
  const enabledProviders = computed(() => 
    providers.value.filter(p => p.is_enabled)
  )

  const providerOptions = computed(() => 
    enabledProviders.value.map(p => ({
      value: p.id,
      label: `${p.name} (${p.api_type})`
    }))
  )

  // Get provider by ID
  const getProviderById = (id) => {
    return providers.value.find(p => p.id === id)
  }

  // Actions
  async function fetchProviders() {
    loading.value = true
    error.value = null
    try {
      const data = await aiProvidersApi.list()
      providers.value = data || []
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchProviderTypes() {
    try {
      const data = await aiProvidersApi.getTypes()
      providerTypes.value = data || []
    } catch (err) {
      console.error('Failed to fetch provider types:', err)
    }
  }

  async function createProvider(data) {
    loading.value = true
    try {
      const newProvider = await aiProvidersApi.create(data)
      providers.value.push(newProvider)
      return newProvider
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateProvider(id, data) {
    loading.value = true
    try {
      const updated = await aiProvidersApi.update(id, data)
      const index = providers.value.findIndex(p => p.id === id)
      if (index !== -1) {
        providers.value[index] = updated
      }
      return updated
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteProvider(id) {
    loading.value = true
    try {
      await aiProvidersApi.delete(id)
      providers.value = providers.value.filter(p => p.id !== id)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function testProvider(id) {
    try {
      const result = await aiProvidersApi.test(id)
      return result
    } catch (err) {
      return { success: false, message: err.message }
    }
  }

  return {
    // State
    providers,
    providerTypes,
    loading,
    error,
    // Getters
    enabledProviders,
    providerOptions,
    getProviderById,
    // Actions
    fetchProviders,
    fetchProviderTypes,
    createProvider,
    updateProvider,
    deleteProvider,
    testProvider
  }
})
