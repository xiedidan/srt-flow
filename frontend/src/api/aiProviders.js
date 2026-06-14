/**
 * AI Provider API module
 */
import api from './index'

// RSA public key cache
let publicKeyCache = null

/**
 * Get RSA public key for encrypting API keys
 */
async function getPublicKey() {
  if (publicKeyCache) {
    return publicKeyCache
  }
  const res = await api.get('/ai-providers/public-key')
  // res is { data: { public_key: "..." }, message: "..." } from interceptor
  publicKeyCache = res.data.public_key
  return publicKeyCache
}

/**
 * Encrypt API key using RSA public key
 */
async function encryptApiKey(apiKey) {
  const publicKeyPem = await getPublicKey()
  
  // Import public key
  const pemHeader = '-----BEGIN PUBLIC KEY-----'
  const pemFooter = '-----END PUBLIC KEY-----'
  const pemContents = publicKeyPem
    .replace(pemHeader, '')
    .replace(pemFooter, '')
    .replace(/\s/g, '')
  
  const binaryDer = Uint8Array.from(atob(pemContents), c => c.charCodeAt(0))
  
  const publicKey = await crypto.subtle.importKey(
    'spki',
    binaryDer,
    {
      name: 'RSA-OAEP',
      hash: 'SHA-256'
    },
    false,
    ['encrypt']
  )
  
  // Encrypt the API key
  const encoder = new TextEncoder()
  const data = encoder.encode(apiKey)
  const encrypted = await crypto.subtle.encrypt(
    { name: 'RSA-OAEP' },
    publicKey,
    data
  )
  
  // Convert to base64
  return btoa(String.fromCharCode(...new Uint8Array(encrypted)))
}

export const aiProvidersApi = {
  /**
   * Get all AI providers
   */
  async list() {
    const res = await api.get('/ai-providers')
    return res.data
  },

  /**
   * Get provider types with default URLs
   */
  async getTypes() {
    const res = await api.get('/ai-providers/types/options')
    return res.data
  },

  /**
   * Create a new AI provider
   */
  async create(data) {
    // Encrypt API key before sending
    const encryptedKey = await encryptApiKey(data.api_key)
    const payload = {
      name: data.name,
      api_type: data.api_type,
      base_url: data.base_url,
      api_key_encrypted: encryptedKey
    }
    const res = await api.post('/ai-providers', payload)
    return res.data
  },

  /**
   * Get a single AI provider
   */
  async get(id) {
    const res = await api.get(`/ai-providers/${id}`)
    return res.data
  },

  /**
   * Update an AI provider
   */
  async update(id, data) {
    const payload = { ...data }
    // Encrypt API key if provided
    if (data.api_key) {
      payload.api_key_encrypted = await encryptApiKey(data.api_key)
      delete payload.api_key
    }
    const res = await api.put(`/ai-providers/${id}`, payload)
    return res.data
  },

  /**
   * Delete an AI provider
   */
  async delete(id) {
    const res = await api.delete(`/ai-providers/${id}`)
    return res.data
  },

  /**
   * Test AI provider connection
   */
  async test(id) {
    const res = await api.post(`/ai-providers/${id}/test`)
    return res.data
  }
}

export default aiProvidersApi
