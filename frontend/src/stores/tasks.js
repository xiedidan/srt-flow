/**
 * Tasks state store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { tasksApi } from '@/api/tasks'

export const useTasksStore = defineStore('tasks', () => {
  // State
  const tasks = ref([])
  const currentTask = ref(null)
  const loading = ref(false)
  const pagination = ref({
    page: 1,
    pageSize: 20,
    total: 0
  })
  const filters = ref({
    status: null,
    type: null
  })

  // Getters
  const runningTasks = computed(() => 
    tasks.value.filter(t => t.status === 'running')
  )
  
  const pendingTasks = computed(() => 
    tasks.value.filter(t => t.status === 'pending')
  )

  const completedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'completed')
  )

  const failedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'failed')
  )

  const totalPages = computed(() =>
    Math.ceil(pagination.value.total / pagination.value.pageSize)
  )

  // Actions
  async function fetchTasks(params = {}) {
    loading.value = true
    try {
      const queryParams = {
        page: pagination.value.page,
        page_size: pagination.value.pageSize,
        ...filters.value,
        ...params
      }
      // Remove null/undefined values
      Object.keys(queryParams).forEach(key => {
        if (queryParams[key] === null || queryParams[key] === undefined || queryParams[key] === '') {
          delete queryParams[key]
        }
      })
      
      const response = await tasksApi.list(queryParams)
      const newTasks = response.data?.items || []
      
      // Preserve progress from existing tasks to avoid flicker during refresh
      // This prevents progress from briefly showing 0 before WebSocket updates
      if (tasks.value.length > 0) {
        const existingTaskMap = new Map(tasks.value.map(t => [t.id, t]))
        newTasks.forEach(newTask => {
          const existing = existingTaskMap.get(newTask.id)
          if (existing && existing.status === 'running' && newTask.status === 'running') {
            // Keep the higher progress value to avoid regression
            if (existing.progress > (newTask.progress || 0)) {
              newTask.progress = existing.progress
            }
          }
        })
      }
      
      tasks.value = newTasks
      pagination.value.total = response.data?.total || 0
    } finally {
      loading.value = false
    }
  }

  async function fetchTask(taskId) {
    loading.value = true
    try {
      const response = await tasksApi.get(taskId)
      currentTask.value = response.data
      return response.data
    } finally {
      loading.value = false
    }
  }

  async function createTask(data) {
    const response = await tasksApi.create(data)
    await fetchTasks()
    return response.data
  }

  async function retryTask(taskId, priority = 'normal') {
    await tasksApi.action(taskId, 'retry', { priority })
    await fetchTasks()
  }

  async function cancelTask(taskId) {
    await tasksApi.action(taskId, 'cancel')
    await fetchTasks()
  }

  function updateTaskProgress(taskId, progress, status) {
    const task = tasks.value.find(t => t.id === taskId)
    if (task) {
      task.progress = progress
      if (status) task.status = status
    }
    if (currentTask.value?.id === taskId) {
      currentTask.value.progress = progress
      if (status) currentTask.value.status = status
    }
  }

  function updateTaskFromWs(data) {
    // Handle both 'id' and 'task_id' field names
    const taskId = data.id || data.task_id
    if (!taskId) return
    
    const task = tasks.value.find(t => t.id === taskId)
    if (task) {
      // Map WebSocket data fields to task fields
      if (data.status) task.status = data.status
      if (data.progress !== undefined) task.progress = data.progress
      if (data.error) task.error = data.error
      if (data.result) task.result = data.result
    }
    if (currentTask.value?.id === taskId) {
      if (data.status) currentTask.value.status = data.status
      if (data.progress !== undefined) currentTask.value.progress = data.progress
      if (data.error) currentTask.value.error = data.error
      if (data.result) currentTask.value.result = data.result
    }
  }

  function setPage(page) {
    pagination.value.page = page
    fetchTasks()
  }

  function setFilters(newFilters) {
    filters.value = { ...filters.value, ...newFilters }
    pagination.value.page = 1
    fetchTasks()
  }

  function clearCurrentTask() {
    currentTask.value = null
  }

  return {
    tasks,
    currentTask,
    loading,
    pagination,
    filters,
    runningTasks,
    pendingTasks,
    completedTasks,
    failedTasks,
    totalPages,
    fetchTasks,
    fetchTask,
    createTask,
    retryTask,
    cancelTask,
    updateTaskProgress,
    updateTaskFromWs,
    setPage,
    setFilters,
    clearCurrentTask
  }
})
