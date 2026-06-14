/**
 * Reference Audio API module
 * 
 * Provides functions for managing TTS reference audio files.
 */
import api from './index'

/**
 * Get all reference audio files
 * @returns {Promise<Array>} List of reference audio metadata
 */
export async function listReferenceAudios() {
  const { data } = await api.get('/reference-audio')
  return data
}

/**
 * Upload a new reference audio file
 * @param {File} file - Audio file to upload
 * @param {string} name - Required name
 * @param {Object} [options] - Optional fields
 * @param {string} [options.description] - Optional description
 * @param {string} [options.emotion] - Optional emotion tag
 * @param {string} [options.content] - Optional transcript content
 * @returns {Promise<Object>} Uploaded audio metadata
 */
export async function uploadReferenceAudio(file, name, options = {}) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('name', name)
  if (options.description) {
    formData.append('description', options.description)
  }
  if (options.emotion) {
    formData.append('emotion', options.emotion)
  }
  if (options.content) {
    formData.append('content', options.content)
  }
  
  const { data } = await api.post('/reference-audio', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return data
}

/**
 * Get reference audio by ID
 * @param {string} audioId - Audio ID
 * @returns {Promise<Object>} Audio metadata
 */
export async function getReferenceAudio(audioId) {
  const { data } = await api.get(`/reference-audio/${audioId}`)
  return data
}

/**
 * Update reference audio metadata
 * @param {string} audioId - Audio ID
 * @param {Object} updates - Fields to update
 * @param {string} [updates.name] - Name
 * @param {string} [updates.description] - Description
 * @param {string} [updates.emotion] - Emotion tag
 * @param {string} [updates.content] - Transcript content
 * @returns {Promise<Object>} Updated audio metadata
 */
export async function updateReferenceAudio(audioId, updates) {
  const { data } = await api.put(`/reference-audio/${audioId}`, updates)
  return data
}

/**
 * Delete reference audio
 * @param {string} audioId - Audio ID
 * @returns {Promise<void>}
 */
export async function deleteReferenceAudio(audioId) {
  await api.delete(`/reference-audio/${audioId}`)
}

/**
 * Get audio stream URL for playback
 * @param {string} audioId - Audio ID
 * @returns {string} Stream URL
 */
export function getAudioStreamUrl(audioId) {
  return `${api.defaults.baseURL}/reference-audio/${audioId}/stream`
}

export default {
  listReferenceAudios,
  uploadReferenceAudio,
  getReferenceAudio,
  updateReferenceAudio,
  deleteReferenceAudio,
  getAudioStreamUrl
}
