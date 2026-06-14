<script setup>
/**
 * Video detail modal component
 */
import { computed, watch, ref } from 'vue'
import { useVideosStore } from '@/stores/videos'
import { PreviewModal } from '@/components/preview'

const props = defineProps({
  visible: Boolean,
  videoId: String
})

const emit = defineEmits(['close', 'action'])

const videosStore = useVideosStore()
const activeTab = ref('info')
const editingTags = ref(false)
const newTag = ref('')
const showPreview = ref(false)
const previewInitialTab = ref('preview')

const video = computed(() => videosStore.currentVideo)

// Source labels
const sourceLabels = {
  youtube: 'YouTube',
  bilibili: 'Bilibili',
  local: '本地'
}

// File type labels
const fileTypeLabels = {
  video: '原始视频',
  audio_original: '原始音频',
  subtitle_original: '原始字幕',
  subtitle_translated: '翻译字幕',
  audio_tts: '合成语音',
  video_output: '输出视频',
  thumbnail: '缩略图',
  summary: '摘要',
  log: '处理日志'
}

// Fetch video when videoId changes
watch(() => props.videoId, async (newId) => {
  if (newId && props.visible) {
    await videosStore.fetchVideo(newId)
  }
}, { immediate: true })

watch(() => props.visible, (visible) => {
  if (!visible) {
    videosStore.clearCurrentVideo()
    activeTab.value = 'info'
    editingTags.value = false
    thumbnailError.value = false
  }
})

// Format duration same as VideoCard (e.g., "5:30")
const duration = computed(() => {
  if (!video.value?.duration) return '-'
  const totalSecs = Math.round(video.value.duration)
  const mins = Math.floor(totalSecs / 60)
  const secs = totalSecs % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

// Thumbnail URL
const thumbnailUrl = computed(() => {
  if (!video.value?.id) return null
  const files = video.value.files || {}
  if (files.thumbnail || files.video || files.video_output) {
    return `/api/v1/videos/${video.value.id}/thumbnail`
  }
  return null
})

// Track thumbnail load error
const thumbnailError = ref(false)

function handleThumbnailError() {
  thumbnailError.value = true
}

const availableFiles = computed(() => {
  if (!video.value?.files) return []
  return Object.entries(video.value.files)
    .filter(([_, path]) => path)
    .map(([type, path]) => ({
      type,
      label: fileTypeLabels[type] || type,
      path
    }))
})

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function handleClose() {
  emit('close')
}

async function addTag() {
  if (!newTag.value.trim() || !video.value) return
  const tags = [...(video.value.tags || []), newTag.value.trim()]
  await videosStore.updateVideo(video.value.id, { tags })
  newTag.value = ''
}

async function removeTag(tag) {
  if (!video.value) return
  const tags = (video.value.tags || []).filter(t => t !== tag)
  await videosStore.updateVideo(video.value.id, { tags })
}

function handleAction(type) {
  if (!video.value || !video.value.id) {
    console.error('Cannot perform action: video not loaded')
    return
  }
  emit('action', { type, video: video.value })
}

// Open preview modal
function openPreview(tab = 'preview') {
  previewInitialTab.value = tab
  showPreview.value = true
}

// Close preview modal
function closePreview() {
  showPreview.value = false
}

// Handle preview saved
function onPreviewSaved(data) {
  // Refresh video data after subtitle save
  if (props.videoId) {
    videosStore.fetchVideo(props.videoId)
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>{{ video?.title || '视频详情' }}</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div v-if="videosStore.loading" class="modal-loading">
          加载中...
        </div>
        
        <template v-else-if="video">
          <div class="modal-tabs">
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'info' }"
              @click="activeTab = 'info'"
            >
              基本信息
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'files' }"
              @click="activeTab = 'files'"
            >
              文件列表
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'tasks' }"
              @click="activeTab = 'tasks'"
            >
              任务历史
            </button>
          </div>
          
          <div class="modal-body">
            <!-- Info Tab -->
            <div v-show="activeTab === 'info'" class="tab-content">
              <!-- Thumbnail -->
              <div class="video-thumbnail-section">
                <div class="thumbnail-container">
                  <img 
                    v-if="thumbnailUrl && !thumbnailError" 
                    :src="thumbnailUrl" 
                    :alt="video.title"
                    class="thumbnail-img"
                    @error="handleThumbnailError"
                  />
                  <div v-else class="thumbnail-placeholder">
                    <span>🎬</span>
                  </div>
                  <span class="duration-badge">{{ duration }}</span>
                </div>
              </div>
              
              <div class="info-grid">
                <div class="info-item">
                  <label>视频 ID</label>
                  <span class="mono">{{ video.id }}</span>
                </div>
                <div class="info-item">
                  <label>来源</label>
                  <span>{{ sourceLabels[video.source] || video.source }}</span>
                </div>
                <div class="info-item">
                  <label>时长</label>
                  <span>{{ duration }}</span>
                </div>
                <div class="info-item">
                  <label>创建时间</label>
                  <span>{{ formatDateTime(video.created_at) }}</span>
                </div>
                <div class="info-item full-width">
                  <label>标题</label>
                  <span>{{ video.title }}</span>
                </div>
                <div class="info-item full-width">
                  <label>
                    标签
                    <button class="edit-btn" @click="editingTags = !editingTags">
                      {{ editingTags ? '完成' : '编辑' }}
                    </button>
                  </label>
                  <div class="tags-container">
                    <span v-for="tag in video.tags" :key="tag" class="tag">
                      {{ tag }}
                      <button v-if="editingTags" class="remove-tag" @click="removeTag(tag)">×</button>
                    </span>
                    <div v-if="editingTags" class="add-tag">
                      <input 
                        v-model="newTag" 
                        placeholder="新标签" 
                        @keyup.enter="addTag"
                      />
                      <button @click="addTag">+</button>
                    </div>
                    <span v-if="!video.tags?.length && !editingTags" class="no-tags">无标签</span>
                  </div>
                </div>
                <div v-if="video.source_url" class="info-item full-width">
                  <label>源地址</label>
                  <a :href="video.source_url" target="_blank" class="source-link">
                    {{ video.source_url }}
                  </a>
                </div>
              </div>
            </div>
            
            <!-- Files Tab -->
            <div v-show="activeTab === 'files'" class="tab-content">
              <div v-if="availableFiles.length === 0" class="empty-files">
                暂无文件
              </div>
              <div v-else class="files-list">
                <div v-for="file in availableFiles" :key="file.type" class="file-item">
                  <span class="file-icon">📄</span>
                  <div class="file-info">
                    <span class="file-label">{{ file.label }}</span>
                    <span class="file-path">{{ file.path }}</span>
                  </div>
                  <div class="file-actions">
                    <button 
                      v-if="['subtitle_original', 'subtitle_translated'].includes(file.type)"
                      class="file-btn"
                      @click="openPreview('edit')"
                    >
                      编辑
                    </button>
                    <button 
                      v-if="file.type === 'video' || file.type === 'video_output'"
                      class="file-btn"
                      @click="openPreview('preview')"
                    >
                      预览
                    </button>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Tasks Tab -->
            <div v-show="activeTab === 'tasks'" class="tab-content">
              <div v-if="!video.task_history?.length" class="empty-tasks">
                暂无任务历史
              </div>
              <div v-else class="tasks-list">
                <div v-for="task in video.task_history" :key="task.id" class="task-item">
                  <span class="task-type">{{ task.type }}</span>
                  <span class="task-status" :class="task.status">{{ task.status }}</span>
                  <span class="task-time">{{ formatDateTime(task.created_at) }}</span>
                </div>
              </div>
            </div>
          </div>
          
          <div class="modal-footer">
            <div class="action-buttons">
              <button class="btn btn-preview" @click="openPreview('preview')">▶️ 预览</button>
              <button class="btn btn-action" @click="handleAction('asr')">🎤 识别</button>
              <button class="btn btn-action" @click="handleAction('translate')">🌐 翻译</button>
              <button class="btn btn-action" @click="handleAction('tts')">🔊 合成</button>
              <button class="btn btn-action" @click="handleAction('synthesize')">🎬 视频</button>
            </div>
            <button class="btn btn-secondary" @click="handleClose">关闭</button>
          </div>
        </template>
      </div>
      
      <!-- Preview Modal -->
      <PreviewModal
        :visible="showPreview"
        :video-id="videoId"
        :initial-tab="previewInitialTab"
        @close="closePreview"
        @saved="onPreviewSaved"
      />
    </div>
  </Teleport>
</template>

<style lang="scss" scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background-color: var(--bg-secondary);
  border-radius: 12px;
  width: 90%;
  max-width: 720px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  
  h3 {
    margin: 0;
    font-size: 18px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 90%;
  }
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
}

.modal-loading {
  padding: 60px;
  text-align: center;
  color: var(--text-secondary);
}

.modal-tabs {
  display: flex;
  gap: 4px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
}

.tab-btn {
  padding: 8px 16px;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
  
  &.active {
    background-color: var(--accent-color);
    color: var(--text-primary);
  }
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.tab-content {
  min-height: 200px;
}

.video-thumbnail-section {
  margin-bottom: 20px;
}

.thumbnail-container {
  position: relative;
  width: 100%;
  max-width: 400px;
  aspect-ratio: 16 / 9;
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--bg-primary);
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
  font-size: 48px;
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-hover) 100%);
}

.duration-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 4px 8px;
  background-color: rgba(0, 0, 0, 0.8);
  border-radius: 4px;
  font-size: 12px;
  color: white;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  
  &.full-width {
    grid-column: 1 / -1;
  }
  
  label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  
  span {
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .mono {
    font-family: monospace;
    font-size: 12px;
    word-break: break-all;
  }
}

.edit-btn {
  padding: 2px 8px;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  cursor: pointer;
  
  &:hover {
    background-color: var(--bg-hover);
  }
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background-color: var(--bg-hover);
  border-radius: 4px;
  font-size: 13px;
  color: var(--text-primary);
}

.remove-tag {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0 2px;
  font-size: 14px;
  
  &:hover {
    color: var(--error);
  }
}

.add-tag {
  display: flex;
  gap: 4px;
  
  input {
    width: 80px;
    padding: 4px 8px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 13px;
    
    &:focus {
      outline: none;
      border-color: var(--accent-color);
    }
  }
  
  button {
    padding: 4px 8px;
    background-color: var(--accent-color);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
  }
}

.no-tags {
  color: var(--text-muted);
  font-style: italic;
}

.source-link {
  color: var(--accent-color);
  word-break: break-all;
  
  &:hover {
    text-decoration: underline;
  }
}

.empty-files,
.empty-tasks {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
}

.file-icon {
  font-size: 20px;
}

.file-info {
  flex: 1;
  min-width: 0;
  
  .file-label {
    display: block;
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .file-path {
    display: block;
    font-size: 11px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.file-btn {
  padding: 4px 12px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
  
  &:hover {
    background-color: var(--border-color);
  }
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
}

.task-type {
  font-size: 13px;
  color: var(--text-primary);
  min-width: 80px;
}

.task-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  
  &.pending { background-color: rgba(245, 158, 11, 0.2); color: var(--warning); }
  &.running { background-color: rgba(59, 130, 246, 0.2); color: var(--info); }
  &.completed { background-color: rgba(34, 197, 94, 0.2); color: var(--success); }
  &.failed { background-color: rgba(239, 68, 68, 0.2); color: var(--error); }
}

.task-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-muted);
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &.btn-action {
    background-color: var(--bg-hover);
    color: var(--text-primary);
    
    &:hover {
      background-color: var(--border-color);
    }
  }
  
  &.btn-preview {
    background-color: var(--accent-color);
    color: white;
    
    &:hover {
      background-color: var(--accent-hover);
    }
  }
  
  &.btn-secondary {
    background-color: var(--bg-hover);
    color: var(--text-primary);
    
    &:hover {
      background-color: var(--border-color);
    }
  }
}
</style>
