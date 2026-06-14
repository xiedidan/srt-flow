/**
 * Tasks API endpoints
 */
import api from './index'

export const tasksApi = {
  /**
   * Get tasks list
   */
  list(params = {}) {
    return api.get('/tasks', { params })
  },

  /**
   * Get task details
   */
  get(taskId) {
    return api.get(`/tasks/${taskId}`)
  },

  /**
   * Create new task
   */
  create(data) {
    return api.post('/tasks', data)
  },

  /**
   * Perform task action (retry/cancel)
   */
  action(taskId, action, options = {}) {
    return api.post(`/tasks/${taskId}/action`, { action, ...options })
  }
}
