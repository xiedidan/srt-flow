<script setup>
/**
 * Video card component for grid/list display
 */
import { computed, ref } from 'vue'

const props = defineProps({
  video: {
    type: Object,
    required: true
  },
  selected: {
    type: Boolean,
    default: false
  },
  viewMode: {
    type: String,
    default: 'grid' // grid | list
  }
})

const emit = defineEmits(['view', 'select', 'action'])

// Check if this is a downloading video
const isDownloading = computed(() => props.video.is_downloading === true)

// Source icons
const sourceIcons = {
  youtube: '📺',
  bilibili: '📱',
  local: '💾',
  unknown: '🎬'
}

const sourceIcon = computed(() => sourceIcons[props.video.source] || '🎬')

const duration = computed(() => {
  if (isDownloading.value) return '-'
  if (!props.video.duration) return '-'
  // Round to nearest second for cleaner display
  const totalSecs = Math.round(props.video.duration)
  const mins = Math.floor(totalSecs / 60)
  const secs = totalSecs % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

// Thumbnail URL - always try to get thumbnail, backend will auto-generate from first frame if needed
const thumbnailUrl = computed(() => {
  // For downloading videos, use remote thumbnail URL if available
  if (isDownloading.value) {
    return props.video.thumbnail_url || null
  }
  
  const files = props.video.files || {}
  // If video file exists, we can always try to get thumbnail (backend auto-generates)
  if (files.thumbnail || files.video || files.video_output) {
    return `/api/v1/videos/${props.video.id}/thumbnail`
  }
  return null
})

const formattedDate = computed(() => {
  if (!props.video.created_at) return '-'
  return new Date(props.video.created_at).toLocaleDateString('zh-CN')
})

// File status indicators
const fileStatus = computed(() => {
  if (isDownloading.value) {
    return {
      hasVideo: false,
      hasSubtitle: false,
      hasTranslated: false,
      hasTts: false,
      hasOutput: false
    }
  }
  const files = props.video.files || {}
  return {
    hasVideo: !!files.video,
    hasSubtitle: !!files.subtitle_original,
    hasTranslated: !!files.subtitle_translated,
    hasTts: !!files.audio_tts,
    hasOutput: !!files.video_output
  }
})

// Download status text
// Progress stages: 0-90% downloading files, 90-100% merging
const downloadStatusText = computed(() => {
  if (!isDownloading.value) return ''
  const status = props.video.download_status
  // Clamp progress to 0-100 range
  const progress = Math.min(100, Math.max(0, props.video.download_progress || 0))
  if (status === 'pending') return '等待下载...'
  if (status === 'running') {
    if (progress >= 95) {
      return '合并中...'
    } else if (progress >= 90) {
      return '处理中...'
    } else {
      return `下载中 ${progress}%`
    }
  }
  return status
})

// Download progress percentage (clamped to 0-100)
const downloadProgress = computed(() => {
  return Math.min(100, Math.max(0, props.video.download_progress || 0))
})

// Track thumbnail load error
const thumbnailError = ref(false)

function handleSelect(e) {
  e.stopPropagation()
  if (!isDownloading.value) {
    emit('select', props.video.id)
  }
}

function handleThumbnailError() {
  thumbnailError.value = true
}

function handleCardClick() {
  if (!isDownloading.value) {
    emit('view', props.video)
  }
}
</script>

<template>
  <div 
    class="video-card" 
    :class="[viewMode, { selected, downloading: isDownloading }]"
    @click="handleCardClick"
  >
    <!-- Checkbox (not for downloading) -->
    <div v-if="!isDownloading" class="select-box" @click="handleSelect">
      <input type="checkbox" :checked="selected" />
    </div>
    
    <!-- Thumbnail -->
    <div class="thumbnail">
      <img 
        v-if="thumbnailUrl && !thumbnailError" 
        :src="thumbnailUrl" 
        :alt="video.title" 
        class="thumbnail-img"
        @error="handleThumbnailError"
      />
      <div v-else class="thumbnail-placeholder" :class="{ downloading: isDownloading }">
        <span v-if="isDownloading" class="download-icon">⏳</span>
        <span v-else>{{ sourceIcon }}</span>
      </div>
      <span v-if="!isDownloading" class="duration-badge">{{ duration }}</span>
      <!-- Download progress bar -->
      <div v-if="isDownloading && video.download_status === 'running'" class="download-progress">
        <div class="progress-bar" :style="{ width: downloadProgress + '%' }"></div>
      </div>
    </div>
    
    <!-- Info -->
    <div class="video-info">
      <h4 class="video-title">{{ video.title }}</h4>
      
      <div class="video-meta">
        <span class="source">{{ sourceIcon }} {{ video.source || 'unknown' }}</span>
        <span v-if="isDownloading" class="download-status">{{ downloadStatusText }}</span>
        <span v-else class="date">{{ formattedDate }}</span>
      </div>
      
      <!-- Tags -->
      <div v-if="video.tags?.length" class="video-tags">
        <span v-for="tag in video.tags.slice(0, 3)" :key="tag" class="tag">
          {{ tag }}
        </span>
        <span v-if="video.tags.length > 3" class="tag more">
          +{{ video.tags.length - 3 }}
        </span>
      </div>
      
      <!-- File status (not for downloading) -->
      <div v-if="!isDownloading" class="file-status">
        <span class="status-dot" :class="{ active: fileStatus.hasVideo }" title="原视频">📹</span>
        <span class="status-dot" :class="{ active: fileStatus.hasSubtitle }" title="原字幕">📝</span>
        <span class="status-dot" :class="{ active: fileStatus.hasTranslated }" title="翻译字幕">🌐</span>
        <span class="status-dot" :class="{ active: fileStatus.hasTts }" title="合成语音">🔊</span>
        <span class="status-dot" :class="{ active: fileStatus.hasOutput }" title="输出视频">🎬</span>
      </div>
    </div>
    
    <!-- Actions (not for downloading) -->
    <div v-if="!isDownloading" class="video-actions" @click.stop>
      <button class="action-btn" @click="emit('action', { type: 'asr', video })" title="语音识别">
        🎤
      </button>
      <button class="action-btn" @click="emit('action', { type: 'translate', video })" title="翻译">
        🌐
      </button>
      <button class="action-btn" @click="emit('action', { type: 'tts', video })" title="语音合成">
        🔊
      </button>
      <button class="action-btn" @click="emit('action', { type: 'synthesize', video })" title="视频合成">
        🎬
      </button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.video-card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  
  &:hover {
    border-color: var(--accent-color);
    
    .select-box {
      opacity: 1;
    }
    
    .video-actions {
      opacity: 1;
    }
  }
  
  &.selected {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.05);
    
    .select-box {
      opacity: 1;
    }
  }
  
  &.downloading {
    cursor: default;
    border-color: var(--warning, #f59e0b);
    background-color: rgba(245, 158, 11, 0.05);
    
    &:hover {
      border-color: var(--warning, #f59e0b);
    }
  }
  
  // Grid mode
  &.grid {
    display: flex;
    flex-direction: column;
    
    .thumbnail {
      aspect-ratio: 16 / 9;
      width: 100%;
    }
    
    .video-info {
      padding: 12px;
    }
    
    .video-actions {
      position: absolute;
      bottom: 12px;
      right: 12px;
    }
  }
  
  // List mode
  &.list {
    display: flex;
    align-items: center;
    padding: 12px;
    gap: 16px;
    
    .thumbnail {
      width: 160px;
      height: 90px;
      flex-shrink: 0;
    }
    
    .video-info {
      flex: 1;
      min-width: 0;
    }
    
    .video-actions {
      flex-shrink: 0;
    }
  }
}

.select-box {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s;
  
  input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: var(--accent-color);
    cursor: pointer;
  }
}

.thumbnail {
  position: relative;
  background-color: var(--bg-primary);
  border-radius: 4px;
  overflow: hidden;
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-hover) 100%);
  
  &.downloading {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.2) 100%);
    
    .download-icon {
      animation: pulse 1.5s ease-in-out infinite;
    }
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.95); }
}

.download-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 4px;
  background-color: rgba(0, 0, 0, 0.3);
  
  .progress-bar {
    height: 100%;
    background-color: var(--warning, #f59e0b);
    transition: width 0.3s ease;
  }
}

.duration-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  padding: 2px 6px;
  background-color: rgba(0, 0, 0, 0.8);
  border-radius: 4px;
  font-size: 12px;
  color: white;
}

.video-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.video-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.video-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
  
  .download-status {
    color: var(--warning, #f59e0b);
    font-weight: 500;
  }
}

.video-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag {
  padding: 2px 8px;
  background-color: var(--bg-hover);
  border-radius: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  
  &.more {
    background-color: transparent;
    color: var(--text-muted);
  }
}

.file-status {
  display: flex;
  gap: 8px;
}

.status-dot {
  font-size: 14px;
  opacity: 0.3;
  
  &.active {
    opacity: 1;
  }
}

.video-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.action-btn {
  padding: 6px 8px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: var(--border-color);
  }
}
</style>
