/**
 * ASR API client
 * 
 * - Models are cross-platform, shared by all Whisper engines
 * - Engine executables are platform-specific
 */
import api from './index'

// ============================================================================
// Whisper Models (cross-platform, shared by all engines)
// ============================================================================

/**
 * Get all models status
 */
export async function getModels() {
  return api.get('/asr/models')
}

/**
 * Get status for a specific model
 * @param {string} modelSize - Model size
 */
export async function getModelStatus(modelSize) {
  return api.get(`/asr/models/${modelSize}`)
}

/**
 * Start downloading a model
 * @param {string} modelSize - Model size to download
 */
export async function downloadModel(modelSize) {
  return api.post('/asr/models/download', { model_size: modelSize })
}

/**
 * Delete a downloaded model
 * @param {string} modelSize - Model size to delete
 */
export async function deleteModel(modelSize) {
  return api.delete(`/asr/models/${modelSize}`)
}

// ============================================================================
// Engine Executables (platform-specific)
// ============================================================================

/**
 * Get list of supported engines and platforms
 */
export async function getEngines() {
  return api.get('/asr/engines')
}

/**
 * Get engine status for all platforms
 * @param {string} engine - Engine type: faster_whisper_xxl
 */
export async function getEngineList(engine) {
  return api.get(`/asr/engines/${engine}`)
}

/**
 * Get engine status for a specific platform
 * @param {string} engine - Engine type
 * @param {string} platform - Platform: windows, linux, macos
 */
export async function getEngineStatus(engine, platform) {
  return api.get(`/asr/engines/${engine}/${platform}`)
}

/**
 * Start downloading an engine executable
 * @param {string} engine - Engine type
 * @param {string} platform - Platform: windows, linux, macos
 */
export async function downloadEngine(engine, platform) {
  return api.post('/asr/engines/download', { engine, platform })
}

/**
 * Delete engine for a specific platform
 * @param {string} engine - Engine type
 * @param {string} platform - Platform: windows, linux, macos
 */
export async function deleteEngine(engine, platform) {
  return api.delete(`/asr/engines/${engine}/${platform}`)
}
