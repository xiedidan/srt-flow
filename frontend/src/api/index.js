/**
 * API client configuration with unified response handling
 */
import axios from 'axios'

// Create axios instance
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    // const token = localStorage.getItem('token')
    // if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle unified response format
api.interceptors.response.use(
  (response) => {
    // Handle blob responses (e.g., file downloads, image previews)
    if (response.config.responseType === 'blob') {
      return response.data
    }
    
    const { code, message, data } = response.data
    
    // Check business logic success (code === 0)
    if (code === 0) {
      return { data, message }
    }
    
    // Business logic error
    return Promise.reject(new Error(message || 'Request failed'))
  },
  (error) => {
    // Network or HTTP error
    const message = error.response?.data?.message || error.message || 'Network error'
    return Promise.reject(new Error(message))
  }
)

export default api
