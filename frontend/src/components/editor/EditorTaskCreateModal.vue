<script setup>
/**
 * Editor Task Create Modal
 * Supports video clipping and multi-segment splitting
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useVideosStore } from '@/stores/videos'
import { useTasksStore } from '@/stores/tasks'
import api from '@/api'
import TimelineSelector from './TimelineSelector.vue'

const emit = defineEmits(['close', 'created'])

const videosStore = useVideosStore()
const tasksStore = useTasksStore()

// Steps: 'select' -> 'configure'
const step = ref('select')

// Video selection
const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)
const selectedVideo = ref(null)
const videoDetail = ref(null)
const loadingDetail = ref(false)

// Operation type
const operationType = ref('clip') // 'clip' or 'split'

// Clip configuration
const clipMode = ref('fast') // 'fast' or 'precise'
const startTime = ref(0)
const endTime = ref(0)
const outputName = ref('')

// Split configuration
const splitMode = ref('manual') // 'manual', 'equal_count', 'equal_duration'
const splitPoints = ref([])
const equalSegments = ref(2)
const segmentDuration = ref(60)

// Preview state
const currentTime = ref(0)
const videoPlayerRef = ref(null)

// Submitting
const submitting = ref(false)

// Clip mode options
const clipModeOptions = [
  { value: 'fast', label: '快速模式', description: '不重新编码，速度快但可能不精确' },
  { value: 'precise', label: '精确模式', description: '重新编码，精确到帧但速度较慢' }
]

// Split mode options
const splitModeOptions = [
  { value: 'manual', label: '手动切分', description: '在时间轴上点击添加切分点' },
  { value: 'equal_count', label: '等分（按段数）', description: '将视频等分为指定段数' },
  { value: 'equal_duration', label: '等分（按时长）', description: '按固定时长切分' }
]

// Can proceed to next step
const canProceed = computed(() => selectedVideo.value && videoDetail.value)

// Can submit
const canSubmit = computed(() => {
  if (!selectedVideo.value || submitting.value) return false
  
  if (operationType.value === 'clip') {
    return endTime.value > startTime.value
  } else {
    if (splitMode.value === 'manual') {
      return splitPoints.value.length > 0
    }
    return true
  }
})

// Video duration
const videoDuration = computed(() => videoDetail.value?.duration || 0)

// Video stream URL
const videoStreamUrl = computed(() => {
  if (!selectedVideo.value) return ''
  return `/api/v1/videos/${selectedVideo.value.id}/stream`
})

// Search videos
let searchTimeout = null
watch(searchKeyword, (keyword) => {
  clearTimeout(searchTimeout)
  if (!keyword.trim()) {
    searchResults.value = []
    return
  }
  searchTimeout = setTimeout(() => doSearch(keyword), 300)
})

async function doSearch(keyword) {
  if (!keyword.trim()) return
  searching.value = true
  try {
    await videosStore.fetchVideos({ keyword, page_size: 20 })
    // Filter videos that have video file
    searchResults.value = videosStore.videos.filter(v => v.files?.video)
  } finally {
    searching.value = false
  }
}

// Select video
async function selectVideo(video) {
  selectedVideo.value = video
  loadingDetail.value = true
  
  try {
    const res = await api.get(`/videos/${video.id}`)
    videoDetail.value = res.data
    endTime.value = res.data.duration || 0
  } catch (e) {
    console.error('Failed to load video detail:', e)
  } finally {
    loadingDetail.value = false
  }
}

// Go to configure step
function goToConfigure() {
  if (!canProceed.value) return
  step.value = 'configure'
}

// Go back to select step
function goBack() {
  step.value = 'select'
}

// Handle time update from video player
function onTimeUpdate(time) {
  currentTime.value = time
}

// Seek video
function seekVideo(time) {
  currentTime.value = time
  // If we had a video player ref, we'd call seek on it
}

// Generate equal split points
function generateEqualSplitPoints() {
  if (!videoDuration.value) return
  
  const points = []
  if (splitMode.value === 'equal_count' && equalSegments.value > 1) {
    const segDuration = videoDuration.value / equalSegments.value
    for (let i = 1; i < equalSegments.value; i++) {
      points.push(segDuration * i)
    }
  } else if (splitMode.value === 'equal_duration' && segmentDuration.value > 0) {
    let t = segmentDuration.value
    while (t < videoDuration.value) {
      points.push(t)
      t += segmentDuration.value
    }
  }
  splitPoints.value = points
}

// Watch split mode changes
watch([splitMode, equalSegments, segmentDuration], () => {
  if (splitMode.value !== 'manual') {
    generateEqualSplitPoints()
  }
})

// Format time for display
function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// Submit task
async function handleSubmit() {
  if (!canSubmit.value) return
  
  submitting.value = true
  try {
    const payload = {
      video_id: selectedVideo.value.id,
      video_path: videoDetail.value.files?.video,
      operation: operationType.value,
      clip_mode: clipMode.value
    }
    
    // Add subtitle paths if available
    if (videoDetail.value.files?.subtitle_original) {
      payload.original_subtitle_path = videoDetail.value.files.subtitle_original
    }
    if (videoDetail.value.files?.subtitle_translated) {
      payload.translated_subtitle_path = videoDetail.value.files.subtitle_translated
    }
    
    if (operationType.value === 'clip') {
      payload.start_time = startTime.value
      payload.end_time = endTime.value
      if (outputName.value.trim()) {
        payload.output_name = outputName.value.trim()
      }
    } else {
      if (splitMode.value === 'equal_count') {
        payload.equal_segments = equalSegments.value
      } else if (splitMode.value === 'equal_duration') {
        payload.segment_duration = segmentDuration.value
      } else {
        payload.split_points = splitPoints.value.map(t => ({ time: t }))
      }
    }
    
    await tasksStore.createTask({
      type: 'editor',
      payload
    })
    
    emit('created')
    emit('close')
  } catch (e) {
    console.error('Failed to create editor task:', e)
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('close')
}

onMounted(() => {
  videosStore.fetchVideos({ page_size: 100 })
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="handleClose">
      <div class="modal-container" :class="{ 'wide': step === 'configure' }">
        <div class="modal-header">
          <h3>✂️ 新建剪辑任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div class="modal-body">
          <!-- Step 1: Select Video -->
          <template v-if="step === 'select'">
            <!-- Operation Type -->
            <div class="section">
              <div class="section-title">操作类型</div>
              <div class="type-options">
                <label 
                  class="type-option"
                  :class="{ selected: operationType === 'clip' }"
                >
                  <input type="radio" value="clip" v-model="operationType" />
                  <div class="type-icon">✂️</div>
                  <div class="type-content">
                    <span class="type-label">片段裁剪</span>
                    <span class="type-desc">提取视频中的一段</span>
                  </div>
                </label>
                <label 
                  class="type-option"
                  :class="{ selected: operationType === 'split' }"
                >
                  <input type="radio" value="split" v-model="operationType" />
                  <div class="type-icon">📐</div>
                  <div class="type-content">
                    <span class="type-label">多段切分</span>
                    <span class="type-desc">将视频切分为多个片段</span>
                  </div>
                </label>
              </div>
            </div>

            <!-- Video Search -->
            <div class="section">
              <div class="section-title">选择视频</div>
              <div class="search-input-wrapper">
                <input
                  v-model="searchKeyword"
                  type="text"
                  class="search-input"
                  placeholder="输入视频标题搜索..."
                />
                <span v-if="searching" class="search-loading">搜索中...</span>
              </div>
              
              <div v-if="searchResults.length > 0" class="video-list">
                <div 
                  v-for="video in searchResults" 
                  :key="video.id"
                  class="video-item"
                  :class="{ selected: selectedVideo?.id === video.id }"
                  @click="selectVideo(video)"
                >
                  <img 
                    v-if="video.thumbnail" 
                    :src="`/api/v1/videos/${video.id}/thumbnail`" 
                    class="video-thumb"
                    alt=""
                  />
                  <div class="video-thumb placeholder" v-else>🎬</div>
                  <div class="video-info">
                    <div class="video-title">{{ video.title }}</div>
                    <div class="video-meta">
                      <span v-if="video.duration">{{ formatTime(video.duration) }}</span>
                    </div>
                  </div>
                  <div v-if="selectedVideo?.id === video.id" class="check-mark">✓</div>
                </div>
              </div>
              <div v-else-if="searchKeyword && !searching" class="empty-hint">
                未找到视频
              </div>
            </div>

            <!-- Selected Video Info -->
            <div v-if="selectedVideo" class="selected-video-info">
              <div class="info-header">
                <span class="info-icon">🎬</span>
                <span class="info-title">{{ selectedVideo.title }}</span>
              </div>
              <div v-if="loadingDetail" class="loading-hint">加载中...</div>
              <div v-else-if="videoDetail" class="info-details">
                <span>时长: {{ formatTime(videoDetail.duration) }}</span>
                <span v-if="videoDetail.files?.subtitle_original">✓ 原始字幕</span>
                <span v-if="videoDetail.files?.subtitle_translated">✓ 翻译字幕</span>
              </div>
            </div>
          </template>

          <!-- Step 2: Configure -->
          <template v-if="step === 'configure'">
            <div class="configure-layout">
              <!-- Left: Video Preview -->
              <div class="preview-section">
                <div class="video-preview">
                  <video 
                    :src="videoStreamUrl"
                    controls
                    @timeupdate="onTimeUpdate($event.target.currentTime)"
                  />
                </div>
                
                <!-- Timeline -->
                <TimelineSelector
                  v-if="videoDuration > 0"
                  :duration="videoDuration"
                  :current-time="currentTime"
                  :start-time="startTime"
                  :end-time="endTime"
                  :split-points="splitPoints"
                  :mode="operationType"
                  @update:start-time="startTime = $event"
                  @update:end-time="endTime = $event"
                  @update:split-points="splitPoints = $event"
                  @seek="seekVideo"
                />
              </div>
              
              <!-- Right: Options -->
              <div class="options-section">
                <div class="section">
                  <div class="section-title">
                    {{ operationType === 'clip' ? '裁剪设置' : '切分设置' }}
                  </div>
                  
                  <!-- Clip Options -->
                  <template v-if="operationType === 'clip'">
                    <div class="form-group">
                      <label>剪辑模式</label>
                      <div class="radio-options">
                        <label 
                          v-for="opt in clipModeOptions" 
                          :key="opt.value"
                          class="radio-option"
                        >
                          <input type="radio" :value="opt.value" v-model="clipMode" />
                          <div class="radio-content">
                            <span class="radio-label">{{ opt.label }}</span>
                            <span class="radio-desc">{{ opt.description }}</span>
                          </div>
                        </label>
                      </div>
                    </div>
                    
                    <div class="form-row">
                      <div class="form-group">
                        <label>开始时间</label>
                        <input 
                          type="number" 
                          v-model.number="startTime"
                          min="0"
                          :max="endTime - 1"
                          step="0.1"
                          class="form-input"
                        />
                      </div>
                      <div class="form-group">
                        <label>结束时间</label>
                        <input 
                          type="number" 
                          v-model.number="endTime"
                          :min="startTime + 1"
                          :max="videoDuration"
                          step="0.1"
                          class="form-input"
                        />
                      </div>
                    </div>
                    
                    <div class="form-group">
                      <label>输出文件名（可选）</label>
                      <input 
                        type="text" 
                        v-model="outputName"
                        placeholder="留空使用默认名称"
                        class="form-input"
                      />
                    </div>
                  </template>
                  
                  <!-- Split Options -->
                  <template v-else>
                    <div class="form-group">
                      <label>切分方式</label>
                      <div class="radio-options">
                        <label 
                          v-for="opt in splitModeOptions" 
                          :key="opt.value"
                          class="radio-option"
                        >
                          <input type="radio" :value="opt.value" v-model="splitMode" />
                          <div class="radio-content">
                            <span class="radio-label">{{ opt.label }}</span>
                            <span class="radio-desc">{{ opt.description }}</span>
                          </div>
                        </label>
                      </div>
                    </div>
                    
                    <div v-if="splitMode === 'equal_count'" class="form-group">
                      <label>切分段数</label>
                      <input 
                        type="number" 
                        v-model.number="equalSegments"
                        min="2"
                        max="20"
                        class="form-input"
                      />
                      <p class="form-hint">每段约 {{ formatTime(videoDuration / equalSegments) }}</p>
                    </div>
                    
                    <div v-if="splitMode === 'equal_duration'" class="form-group">
                      <label>每段时长（秒）</label>
                      <input 
                        type="number" 
                        v-model.number="segmentDuration"
                        min="10"
                        :max="videoDuration"
                        class="form-input"
                      />
                      <p class="form-hint">将生成约 {{ Math.ceil(videoDuration / segmentDuration) }} 个片段</p>
                    </div>
                    
                    <div v-if="splitMode === 'manual'" class="form-group">
                      <label>切分点</label>
                      <p class="form-hint">在时间轴上点击添加切分点，拖动调整位置</p>
                      <div v-if="splitPoints.length > 0" class="split-points-list">
                        <div 
                          v-for="(point, idx) in splitPoints" 
                          :key="idx"
                          class="split-point-item"
                        >
                          <span>切分点 {{ idx + 1 }}: {{ formatTime(point) }}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div class="form-group">
                      <label>剪辑模式</label>
                      <select v-model="clipMode" class="form-select">
                        <option value="fast">快速模式</option>
                        <option value="precise">精确模式</option>
                      </select>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </template>
        </div>
        
        <div class="modal-footer">
          <div class="footer-left">
            <button v-if="step === 'configure'" class="btn btn-secondary" @click="goBack">
              ← 返回
            </button>
          </div>
          <div class="footer-right">
            <button class="btn btn-secondary" @click="handleClose">取消</button>
            <button 
              v-if="step === 'select'"
              class="btn btn-primary" 
              :disabled="!canProceed"
              @click="goToConfigure"
            >
              下一步 →
            </button>
            <button 
              v-else
              class="btn btn-primary" 
              :disabled="!canSubmit"
              @click="handleSubmit"
            >
              {{ submitting ? '创建中...' : '创建任务' }}
            </button>
          </div>
        </div>
      </div>
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
  max-width: 600px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
  
  &.wide {
    max-width: 1000px;
  }
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

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.type-options {
  display: flex;
  gap: 12px;
}

.type-option {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background-color: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  input { display: none; }
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  &.selected {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.1);
  }
}

.type-icon {
  font-size: 24px;
}

.type-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.type-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.type-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.search-input-wrapper {
  position: relative;
  margin-bottom: 12px;
}

.search-input {
  width: 100%;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.search-loading {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: var(--text-muted);
}

.video-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.video-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-bottom: 1px solid var(--border-color);
  
  &:last-child { border-bottom: none; }
  &:hover { background-color: var(--bg-hover); }
  &.selected { background-color: rgba(59, 130, 246, 0.1); }
}

.video-thumb {
  width: 64px;
  height: 36px;
  object-fit: cover;
  border-radius: 4px;
  
  &.placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-primary);
    font-size: 20px;
  }
}

.video-info {
  flex: 1;
  min-width: 0;
}

.video-title {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.check-mark {
  color: var(--accent-color);
  font-weight: bold;
}

.selected-video-info {
  padding: 12px;
  background-color: rgba(59, 130, 246, 0.1);
  border-radius: 8px;
  margin-top: 16px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.info-icon { font-size: 16px; }

.info-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.info-details {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.loading-hint, .empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 14px;
}

/* Configure step layout */
.configure-layout {
  display: flex;
  gap: 20px;
}

.preview-section {
  flex: 1;
  min-width: 0;
}

.video-preview {
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
  
  video {
    width: 100%;
    display: block;
  }
}

.options-section {
  width: 280px;
  flex-shrink: 0;
}

.form-group {
  margin-bottom: 16px;
  
  label {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 6px;
  }
}

.form-row {
  display: flex;
  gap: 12px;
  
  .form-group { flex: 1; }
}

.form-input, .form-select {
  width: 100%;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.form-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.radio-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.radio-option {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
  background-color: var(--bg-primary);
  border-radius: 6px;
  cursor: pointer;
  
  input {
    margin-top: 2px;
    accent-color: var(--accent-color);
  }
}

.radio-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.radio-label {
  font-size: 13px;
  color: var(--text-primary);
}

.radio-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.split-points-list {
  margin-top: 8px;
  padding: 8px;
  background-color: var(--bg-primary);
  border-radius: 6px;
}

.split-point-item {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 0;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.footer-left, .footer-right {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  &.btn-primary {
    background-color: var(--accent-color);
    color: white;
    
    &:hover:not(:disabled) {
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
