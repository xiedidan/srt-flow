/**
 * Configuration API endpoints
 */
import api from './index'

export const configApi = {
  /**
   * Get all config categories
   */
  listCategories() {
    return api.get('/config')
  },

  /**
   * Get config for a category
   */
  get(category) {
    return api.get(`/config/${category}`)
  },

  /**
   * Update config for a category
   */
  update(category, updates) {
    return api.put(`/config/${category}`, { updates })
  },

  /**
   * Set a secret value (API key)
   */
  setSecret(category, keyName, value) {
    return api.put(`/config/${category}/secrets/${keyName}`, { value })
  },

  /**
   * Delete a secret value
   */
  deleteSecret(category, keyName) {
    return api.delete(`/config/${category}/secrets/${keyName}`)
  },

  /**
   * Validate config without saving
   */
  validate(category, updates) {
    return api.post(`/config/${category}/validate`, { updates })
  },

  /**
   * Reset config to defaults
   */
  reset(category) {
    return api.post(`/config/${category}/reset`)
  },

  /**
   * Export all configs
   */
  exportAll(includeSecrets = false) {
    return api.get('/config/export/all', { params: { include_secrets: includeSecrets } })
  },

  /**
   * Test cookie extraction from browser
   */
  testCookies(browser) {
    return api.post('/config/download/test-cookies', { browser })
  }
}
