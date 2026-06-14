/**
 * Videos API endpoints
 */
import api from './index'

export const videosApi = {
  /**
   * Get videos list
   */
  list(params = {}) {
    return api.get('/videos', { params })
  },

  /**
   * Get video details
   */
  get(videoId) {
    return api.get(`/videos/${videoId}`)
  },

  /**
   * Update video info
   */
  update(videoId, data) {
    return api.patch(`/videos/${videoId}`, data)
  },

  /**
   * Get file content (subtitle, summary, etc.)
   */
  getFileContent(videoId, fileType) {
    return api.get(`/videos/${videoId}/files/${fileType}/content`)
  },

  /**
   * Save file content
   */
  saveFileContent(videoId, fileType, content) {
    return api.put(`/videos/${videoId}/files/${fileType}/content`, { content })
  }
}
