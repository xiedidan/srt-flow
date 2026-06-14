/**
 * WebSocket composable for real-time task updates
 * 
 * Uses singleton pattern to ensure only one WebSocket connection exists.
 */
import { ref, onMounted, onUnmounted, readonly } from 'vue'

// ============================================================================
// Singleton WebSocket Manager
// ============================================================================

const ws = ref(null)
const connected = ref(false)
const reconnectAttempts = ref(0)
const maxReconnectAttempts = 10
const baseReconnectDelay = 1000
const maxReconnectDelay = 30000

// Subscribers for message handling
const subscribers = new Set()

// Reconnect timer reference
let reconnectTimer = null

function getReconnectDelay() {
  // Exponential backoff with jitter
  const delay = Math.min(
    baseReconnectDelay * Math.pow(2, reconnectAttempts.value),
    maxReconnectDelay
  )
  // Add jitter (±20%)
  return delay * (0.8 + Math.random() * 0.4)
}

function connect() {
  // Always cleanup before connecting
  cleanup()
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/status`
  
  try {
    console.log('[WS] Connecting to', wsUrl)
    ws.value = new WebSocket(wsUrl)
    
    ws.value.onopen = () => {
      connected.value = true
      reconnectAttempts.value = 0
      console.log('[WS] Connected')
    }
    
    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        // Notify all subscribers
        subscribers.forEach(callback => {
          try {
            callback(data)
          } catch (e) {
            console.error('[WS] Subscriber error:', e)
          }
        })
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }
    
    ws.value.onclose = (event) => {
      connected.value = false
      console.log('[WS] Disconnected, code:', event.code)
      
      // Only reconnect if we have subscribers
      if (subscribers.size > 0) {
        attemptReconnect()
      }
    }
    
    ws.value.onerror = (error) => {
      console.error('[WS] Error:', error)
    }
  } catch (e) {
    console.error('[WS] Connection failed:', e)
    attemptReconnect()
  }
}

function cleanup() {
  // Clear any pending reconnect timer
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  
  // Close existing connection
  if (ws.value) {
    // Remove handlers to prevent triggering reconnect
    ws.value.onclose = null
    ws.value.onerror = null
    ws.value.onmessage = null
    ws.value.onopen = null
    
    if (ws.value.readyState === WebSocket.OPEN || 
        ws.value.readyState === WebSocket.CONNECTING) {
      ws.value.close()
    }
    ws.value = null
  }
  
  connected.value = false
}

function attemptReconnect() {
  // Clear any existing timer
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  
  if (reconnectAttempts.value < maxReconnectAttempts) {
    reconnectAttempts.value++
    const delay = getReconnectDelay()
    console.log(`[WS] Reconnecting in ${Math.round(delay)}ms (${reconnectAttempts.value}/${maxReconnectAttempts})...`)
    reconnectTimer = setTimeout(connect, delay)
  } else {
    console.warn('[WS] Max reconnect attempts reached')
  }
}

function subscribe(callback) {
  subscribers.add(callback)
  
  // Start connection if this is the first subscriber
  if (subscribers.size === 1 && !ws.value) {
    connect()
  }
  
  return () => {
    subscribers.delete(callback)
    
    // Disconnect if no more subscribers
    if (subscribers.size === 0) {
      cleanup()
      reconnectAttempts.value = 0
    }
  }
}

// ============================================================================
// Composable Export
// ============================================================================

export function useWebSocket(onMessage) {
  let unsubscribe = null
  
  onMounted(() => {
    if (onMessage) {
      unsubscribe = subscribe(onMessage)
    }
  })

  onUnmounted(() => {
    if (unsubscribe) {
      unsubscribe()
    }
  })

  return {
    connected: readonly(connected),
    reconnectAttempts: readonly(reconnectAttempts)
  }
}

// Manual control for non-component usage
export function connectWebSocket(onMessage) {
  return subscribe(onMessage)
}

export function disconnectWebSocket() {
  cleanup()
  subscribers.clear()
  reconnectAttempts.value = 0
}
