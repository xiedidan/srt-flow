/**
 * Global application state store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // State
  const sidebarCollapsed = ref(false)
  const loading = ref(false)
  const notifications = ref([])

  // Getters
  const hasNotifications = computed(() => notifications.value.length > 0)

  // Actions
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setLoading(value) {
    loading.value = value
  }

  function addNotification(notification) {
    const id = Date.now()
    notifications.value.push({ id, ...notification })
    // Auto remove after 5 seconds
    setTimeout(() => removeNotification(id), 5000)
  }

  function removeNotification(id) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  return {
    sidebarCollapsed,
    loading,
    notifications,
    hasNotifications,
    toggleSidebar,
    setLoading,
    addNotification,
    removeNotification
  }
})
