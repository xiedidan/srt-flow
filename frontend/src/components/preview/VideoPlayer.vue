<script setup>
/**
 * Video player component with subtitle support
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  src: String,
  subtitles: {
    type: Array,
    default: () => []
  },
  subtitleMode: {
    type: String,
    default: 'original' // original, translated, dual
  },
  currentTime: {
    type: Number,
    default: 0
  },
  browserCompatible: {
    type: Boolean,
    default: true
  },
  videoCodec: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['timeupdate', 'play', 'pause', 'seeked', 'loaded', 'error'])

const videoRef = ref(null)
const isPlaying = ref(false)
const duration = ref(0)
const currentTimeInternal = ref(0)
const volume = ref(1)
const isMuted = ref(false)
const isFullscreen = ref(false)
const showControls = ref(true)
const videoError = ref(null)
let controlsTimer = null

// Current subtitle based on time
const currentSubtitle = computed(() => {
  if (!props.subtitles?.length) return null
  const time = currentTimeInternal.value
  return props.subtitles.find(s => time >= s.start && time <= s.end)
})

// Format time display
function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// Progress percentage
const progress = computed(() => {
  if (!duration.value) return 0
  return (currentTimeInternal.value / duration.value) * 100
})

// Video event handlers
function onLoadedMetadata() {
  if (videoRef.value) {
    duration.value = videoRef.value.duration
    videoError.value = null
    isHevcError.value = false
    emit('loaded', { duration: duration.value })
  }
}

// Handle video error
function onVideoError(e) {
  const video = videoRef.value
  const error = video?.error
  
  // MediaError codes: 1=ABORTED, 2=NETWORK, 3=DECODE, 4=SRC_NOT_SUPPORTED
  if (error) {
    if (error.code === 3 || error.code === 4) {
      // Codec issue - use prop info if available
      if (!props.browserCompatible) {
        videoError.value = `视频编码 ${props.videoCodec?.toUpperCase() || 'HEVC'} 不支持浏览器预览`
      } else {
        videoError.value = '视频编码不支持预览'
      }
    } else if (error.code === 2) {
      videoError.value = '网络错误，无法加载视频'
    } else {
      videoError.value = '视频加载失败'
    }
  } else {
    videoError.value = '视频加载失败'
  }
  
  emit('error', { error: videoError.value })
}

function onTimeUpdate() {
  if (videoRef.value) {
    currentTimeInternal.value = videoRef.value.currentTime
    emit('timeupdate', currentTimeInternal.value)
  }
}

function onPlay() {
  isPlaying.value = true
  emit('play')
}

function onPause() {
  isPlaying.value = false
  emit('pause')
}

function onSeeked() {
  emit('seeked', currentTimeInternal.value)
}

// Control methods
function togglePlay() {
  if (!videoRef.value) return
  if (isPlaying.value) {
    videoRef.value.pause()
  } else {
    videoRef.value.play()
  }
}

function seek(time) {
  if (videoRef.value) {
    videoRef.value.currentTime = Math.max(0, Math.min(time, duration.value))
  }
}

function seekRelative(delta) {
  seek(currentTimeInternal.value + delta)
}

function onProgressClick(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const percent = (e.clientX - rect.left) / rect.width
  seek(percent * duration.value)
}

function toggleMute() {
  if (videoRef.value) {
    isMuted.value = !isMuted.value
    videoRef.value.muted = isMuted.value
  }
}

function setVolume(val) {
  if (videoRef.value) {
    volume.value = val
    videoRef.value.volume = val
    isMuted.value = val === 0
  }
}

function toggleFullscreen() {
  const container = videoRef.value?.parentElement?.parentElement
  if (!container) return
  
  if (!document.fullscreenElement) {
    container.requestFullscreen?.()
    isFullscreen.value = true
  } else {
    document.exitFullscreen?.()
    isFullscreen.value = false
  }
}

// Auto-hide controls
function showControlsTemporarily() {
  showControls.value = true
  clearTimeout(controlsTimer)
  if (isPlaying.value) {
    controlsTimer = setTimeout(() => {
      showControls.value = false
    }, 3000)
  }
}

// Watch for external time changes
watch(() => props.currentTime, (newTime) => {
  if (Math.abs(newTime - currentTimeInternal.value) > 0.5) {
    seek(newTime)
  }
})

// Keyboard shortcuts
function onKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  
  switch (e.key) {
    case ' ':
      e.preventDefault()
      togglePlay()
      break
    case 'ArrowLeft':
      e.preventDefault()
      seekRelative(-5)
      break
    case 'ArrowRight':
      e.preventDefault()
      seekRelative(5)
      break
    case 'ArrowUp':
      e.preventDefault()
      setVolume(Math.min(1, volume.value + 0.1))
      break
    case 'ArrowDown':
      e.preventDefault()
      setVolume(Math.max(0, volume.value - 0.1))
      break
    case 'm':
      toggleMute()
      break
    case 'f':
      toggleFullscreen()
      break
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('fullscreenchange', () => {
    isFullscreen.value = !!document.fullscreenElement
  })
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  clearTimeout(controlsTimer)
})

// Expose methods for parent
defineExpose({
  seek,
  seekRelative,
  togglePlay,
  getCurrentTime: () => currentTimeInternal.value
})
</script>

<template>
  <div 
    class="video-player" 
    :class="{ fullscreen: isFullscreen }"
    @mousemove="showControlsTemporarily"
    @mouseleave="isPlaying && (showControls = false)"
  >
    <div class="video-container">
      <video
        ref="videoRef"
        :src="src"
        @loadedmetadata="onLoadedMetadata"
        @timeupdate="onTimeUpdate"
        @play="onPlay"
        @pause="onPause"
        @seeked="onSeeked"
        @error="onVideoError"
        @click="togglePlay"
      />
      
      <!-- Codec warning banner (shown before video loads if known incompatible) -->
      <div v-if="!browserCompatible && !videoError" class="codec-warning">
        <span class="warning-icon">⚠️</span>
        <span class="warning-text">
          视频编码为 {{ videoCodec?.toUpperCase() || 'HEVC' }}，浏览器可能无法播放。建议重新下载时勾选"强制 H264 编码"。
        </span>
      </div>
      
      <!-- Video error overlay -->
      <div v-if="videoError" class="error-overlay">
        <div class="error-content">
          <span class="error-icon">🎬</span>
          <p class="error-message">{{ videoError }}</p>
          <p class="error-hint">
            建议重新下载时勾选"强制 H264 编码"选项，确保浏览器兼容。
          </p>
        </div>
      </div>
      
      <!-- Subtitle overlay -->
      <div v-if="currentSubtitle && subtitleMode !== 'none'" class="subtitle-overlay" :class="subtitleMode">
        <div v-if="subtitleMode === 'original' || subtitleMode === 'dual'" class="subtitle-line original">
          {{ currentSubtitle.original }}
        </div>
        <div v-if="subtitleMode === 'translated' || subtitleMode === 'dual'" class="subtitle-line translated">
          {{ currentSubtitle.translated }}
        </div>
      </div>
    </div>
    
    <!-- Controls -->
    <div class="controls" :class="{ visible: showControls || !isPlaying }">
      <!-- Progress bar -->
      <div class="progress-bar" @click="onProgressClick">
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
      </div>
      
      <div class="controls-row">
        <div class="controls-left">
          <button class="control-btn" @click="togglePlay" :title="isPlaying ? '暂停' : '播放'">
            {{ isPlaying ? '⏸' : '▶' }}
          </button>
          <button class="control-btn" @click="seekRelative(-10)" title="后退10秒">⏪</button>
          <button class="control-btn" @click="seekRelative(10)" title="前进10秒">⏩</button>
          <span class="time-display">
            {{ formatTime(currentTimeInternal) }} / {{ formatTime(duration) }}
          </span>
        </div>
        
        <div class="controls-right">
          <div class="volume-control">
            <button class="control-btn" @click="toggleMute" :title="isMuted ? '取消静音' : '静音'">
              {{ isMuted || volume === 0 ? '🔇' : volume < 0.5 ? '🔉' : '🔊' }}
            </button>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              :value="isMuted ? 0 : volume"
              @input="setVolume(parseFloat($event.target.value))"
              class="volume-slider"
            />
          </div>
          <button class="control-btn" @click="toggleFullscreen" title="全屏">
            {{ isFullscreen ? '⛶' : '⛶' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.video-player {
  position: relative;
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
  
  &.fullscreen {
    border-radius: 0;
  }
}

.video-container {
  position: relative;
  width: 100%;
  padding-top: 56.25%; // 16:9 aspect ratio
  
  video {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
    cursor: pointer;
  }
}

.codec-warning {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background-color: rgba(234, 179, 8, 0.9);
  color: #000;
  font-size: 13px;
  z-index: 5;
  
  .warning-icon {
    font-size: 16px;
  }
  
  .warning-text {
    flex: 1;
  }
}

.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.85);
  z-index: 10;
}

.error-content {
  text-align: center;
  padding: 24px;
  max-width: 400px;
  
  .error-icon {
    font-size: 48px;
    display: block;
    margin-bottom: 16px;
  }
  
  .error-message {
    color: #fff;
    font-size: 16px;
    margin: 0 0 12px;
  }
  
  .error-hint {
    color: rgba(255, 255, 255, 0.7);
    font-size: 13px;
    line-height: 1.6;
    margin: 0;
    padding: 12px;
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 6px;
  }
}

.subtitle-overlay {
  position: absolute;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  max-width: 90%;
  pointer-events: none;
  
  .subtitle-line {
    padding: 6px 12px;
    margin: 4px 0;
    background-color: rgba(0, 0, 0, 0.75);
    border-radius: 4px;
    font-size: 18px;
    line-height: 1.4;
    color: #fff;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
    
    &.original {
      color: #fff;
    }
    
    &.translated {
      color: #ffd700;
      font-size: 16px;
    }
  }
  
  &.dual .subtitle-line {
    font-size: 16px;
    
    &.translated {
      font-size: 14px;
    }
  }
}

.controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
  padding: 20px 12px 12px;
  opacity: 0;
  transition: opacity 0.3s;
  
  &.visible {
    opacity: 1;
  }
}

.progress-bar {
  cursor: pointer;
  padding: 8px 0;
}

.progress-track {
  height: 4px;
  background-color: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: var(--accent-color);
  transition: width 0.1s linear;
}

.controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.controls-left,
.controls-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 16px;
  padding: 6px 10px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: rgba(255, 255, 255, 0.1);
  }
}

.time-display {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  font-variant-numeric: tabular-nums;
  margin-left: 8px;
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 4px;
}

.volume-slider {
  width: 60px;
  height: 4px;
  -webkit-appearance: none;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  cursor: pointer;
  
  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px;
    height: 12px;
    background: #fff;
    border-radius: 50%;
  }
}
</style>
