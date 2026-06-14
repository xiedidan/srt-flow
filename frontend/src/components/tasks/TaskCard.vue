<script setup>
/**
 * Task card component for displaying task in list
 * Shows video thumbnail and title for better task identification
 */
import { computed, ref } from 'vue'

const props = defineProps({
  task: {
    type: Object,
    required: true
  },
  viewMode: {
    type: String,
    default: 'card'
  }
})

const emit = defineEmits(['view', 'retry', 'cancel'])

// Task type labels
const typeLabels = {
  download: '下载',
  asr: '语音识别',
  translate: '翻译',
  tts: '语音合成',
  synthesize: '视频合成',
  asset_gen: '素材生成',
  edit: '编辑'
}

// Status config
const statusConfig = {
  pending: { label: '等待中', class: 'status-pending', icon: '⏳' },
  running: { label: '运行中', class: 'status-running', icon: '🔄' },
  completed: { label: '已完成', class: 'status-completed', icon: '✅' },
  failed: { label: '失败', class: 'status-failed', icon: '❌' },
  cancelled: { label: '已取消', class: 'status-cancelled', icon: '🚫' }
}

const typeLabel = computed(() => typeLabels[props.task.type] || props.task.type)
const status = computed(() => statusConfig[props.task.status] || statusConfig.pending)

const formattedTime = computed(() => {
  if (!props.task.created_at) return '-'
  const date = new Date(props.task.created_at)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
})

const canRetry = computed(() => props.task.status === 'failed')
const canCancel = computed(() => ['pending', 'running'].includes(props.task.status))

// Video thumbnail URL
const thumbnailUrl = computed(() => {
  if (!props.task.video_id) return null
  return `/api/v1/videos/${props.task.video_id}/thumbnail`
})

// Video title display
const videoTitle = computed(() => {
  return props.task.video_title || null
})

// Track thumbnail load error
const thumbnailError = ref(false)

function handleThumbnailError() {
  thumbnailError.value = true
}
</script>

<template>
  <div class="task-card" :class="[status.class, viewMode]" @click="emit('view', task)">
    <!-- Card View -->
    <template v-if="viewMode === 'card'">
      <div class="task-header">
        <span class="task-type">{{ typeLabel }}</span>
        <span class="task-status">
          <span class="status-icon">{{ status.icon }}</span>
          {{ status.label }}
        </span>
      </div>
      
      <!-- Video info with thumbnail -->
      <div class="video-info" v-if="videoTitle || thumbnailUrl">
        <div class="thumbnail-wrapper">
          <img 
            v-if="thumbnailUrl && !thumbnailError" 
            :src="thumbnailUrl" 
            :alt="videoTitle || '视频缩略图'"
            class="thumbnail"
            @error="handleThumbnailError"
          />
          <div v-else class="thumbnail-placeholder">
            <span>🎬</span>
          </div>
        </div>
        <div class="video-details">
          <div class="video-title" :title="videoTitle">{{ videoTitle || '未知视频' }}</div>
          <div class="task-id">{{ task.id.slice(0, 8) }}...</div>
        </div>
      </div>
      <div v-else class="task-id">{{ task.id.slice(0, 8) }}...</div>
      
      <div v-if="task.status === 'running'" class="task-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
        </div>
        <span class="progress-text">{{ task.progress }}%</span>
      </div>
      
      <div v-if="task.error" class="task-error">{{ task.error }}</div>
      
      <div class="task-footer">
        <span class="task-time">{{ formattedTime }}</span>
        <div class="task-actions" @click.stop>
          <button v-if="canRetry" class="action-btn retry" @click="emit('retry', task)" title="重试">
            🔁
          </button>
          <button v-if="canCancel" class="action-btn cancel" @click="emit('cancel', task)" title="取消">
            ⏹️
          </button>
        </div>
      </div>
    </template>
    
    <!-- List View -->
    <template v-else>
      <div class="list-content">
        <!-- Thumbnail in list view -->
        <div class="list-thumbnail">
          <img 
            v-if="thumbnailUrl && !thumbnailError" 
            :src="thumbnailUrl" 
            :alt="videoTitle || '视频缩略图'"
            class="thumbnail-small"
            @error="handleThumbnailError"
          />
          <div v-else class="thumbnail-placeholder-small">
            <span>🎬</span>
          </div>
        </div>
        <span class="list-type">{{ typeLabel }}</span>
        <span class="list-video-title" :title="videoTitle">{{ videoTitle || '-' }}</span>
        <span class="list-status">
          <span class="status-icon">{{ status.icon }}</span>
          {{ status.label }}
        </span>
        <div v-if="task.status === 'running'" class="list-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
          </div>
          <span class="progress-text">{{ task.progress }}%</span>
        </div>
        <span v-else class="list-placeholder"></span>
        <span class="list-time">{{ formattedTime }}</span>
        <div class="task-actions" @click.stop>
          <button v-if="canRetry" class="action-btn retry" @click="emit('retry', task)" title="重试">
            🔁
          </button>
          <button v-if="canCancel" class="action-btn cancel" @click="emit('cancel', task)" title="取消">
            ⏹️
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.task-card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
    border-color: var(--accent-color);
  }
  
  &.status-running {
    border-left: 3px solid var(--info);
  }
  
  &.status-completed {
    border-left: 3px solid var(--success);
  }
  
  &.status-failed {
    border-left: 3px solid var(--error);
  }
  
  &.status-pending {
    border-left: 3px solid var(--warning);
  }
  
  // List view styles
  &.list {
    padding: 12px 16px;
    
    .list-content {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    
    .list-thumbnail {
      flex-shrink: 0;
    }
    
    .list-type {
      font-weight: 600;
      color: var(--text-primary);
      min-width: 80px;
    }
    
    .list-video-title {
      flex: 1;
      min-width: 120px;
      max-width: 200px;
      font-size: 13px;
      color: var(--text-primary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    
    .list-id {
      font-family: monospace;
      font-size: 12px;
      color: var(--text-muted);
      min-width: 90px;
    }
    
    .list-status {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
      color: var(--text-secondary);
      min-width: 80px;
    }
    
    .list-progress {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;
      min-width: 120px;
      
      .progress-bar {
        flex: 1;
        height: 4px;
      }
      
      .progress-text {
        font-size: 12px;
        min-width: 36px;
      }
    }
    
    .list-placeholder {
      flex: 1;
      min-width: 120px;
    }
    
    .list-time {
      font-size: 12px;
      color: var(--text-muted);
      min-width: 100px;
      text-align: right;
    }
  }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-type {
  font-weight: 600;
  color: var(--text-primary);
}

.task-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.status-icon {
  font-size: 14px;
}

/* Video info with thumbnail */
.video-info {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.thumbnail-wrapper {
  flex-shrink: 0;
  width: 80px;
  height: 45px;
  border-radius: 4px;
  overflow: hidden;
  background-color: var(--bg-primary);
}

.thumbnail {
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
  font-size: 20px;
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-hover) 100%);
}

.video-details {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.video-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

/* List view thumbnail */
.thumbnail-small {
  width: 48px;
  height: 27px;
  object-fit: cover;
  border-radius: 3px;
}

.thumbnail-placeholder-small {
  width: 48px;
  height: 27px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-hover) 100%);
  border-radius: 3px;
}

.task-id {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.video-details .task-id {
  margin-bottom: 0;
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background-color: var(--bg-primary);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: var(--accent-color);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 36px;
}

.task-error {
  font-size: 12px;
  color: var(--error);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-time {
  font-size: 12px;
  color: var(--text-muted);
}

.task-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  background: none;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: var(--bg-primary);
  }
  
  &.retry:hover {
    background-color: rgba(59, 130, 246, 0.2);
  }
  
  &.cancel:hover {
    background-color: rgba(239, 68, 68, 0.2);
  }
}
</style>
