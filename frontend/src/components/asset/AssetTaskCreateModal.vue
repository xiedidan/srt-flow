<script setup>
/**
 * Asset Generation Task Create Modal
 * Supports video selection, generation items selection, and configuration
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useVideosStore } from '@/stores/videos'
import { useTasksStore } from '@/stores/tasks'
import api from '@/api'

const emit = defineEmits(['close', 'created'])

const videosStore = useVideosStore()
const tasksStore = useTasksStore()

// Selection mode: 'search' | 'tag'
const selectionMode = ref('search')

// Search state
const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)
const selectedVideos = ref([])

// Tag selection state
const selectedTag = ref('')
const tagVideos = ref([])
const loadingTagVideos = ref(false)

// Generation items (checkboxes)
const generateTitle = ref(true)
const generateSummary = ref(true)
const generateThumbnail = ref(true)

// Title generation config
const titleCandidateCount = ref(5)
const targetPlatform = ref('general')
const includeEmoji = ref(false)

// Summary generation config
const summaryStyle = ref('plain')
const summaryMaxLength = ref(500)

// Thumbnail generation config
const thumbnailMode = ref('frame')
const frameTime = ref('auto')
const outputWidth = ref(1920)
const outputHeight = ref(1080)

// AI config status from settings
const thumbnailAiConfigured = ref(false)

// Loading state
const loadingConfig = ref(true)
const submitting = ref(false)

// Platform options
const platformOptions = [
  { value: 'general', label: '通用' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'bilibili', label: 'Bilibili' },
  { value: 'tiktok', label: 'TikTok' }
]

// Summary style options
const summaryStyleOptions = [
  { value: 'plain', label: '纯文本', description: '一段连续的摘要文字' },
  { value: 'structured', label: '结构化', description: '带章节标题的分段摘要' }
]

// Thumbnail mode options
const thumbnailModeOptions = [
  { value: 'frame', label: '视频截帧', description: '从视频中截取关键帧' },
  { value: 'ai', label: 'AI 绘图', description: '使用 AI 生成创意图片' }
]

// All available tags from videos store
const allTags = computed(() => videosStore.allTags)

// Selected count for display
const selectedCount = computed(() => {
  if (selectionMode.value === 'search') {
    return selectedVideos.value.length
  } else {
    return tagVideos.value.filter(v => v.selected).length
  }
})

// At least one generation item must be selected
const hasGenerationItem = computed(() => 
  generateTitle.value || generateSummary.value || generateThumbnail.value
)

// Check if AI thumbnail is selected but not configured
const thumbnailAiNotConfigured = computed(() => 
  generateThumbnail.value && thumbnailMode.value === 'ai' && !thumbnailAiConfigured.value
)

// Can submit
const canSubmit = computed(() => 
  selectedCount.value > 0 && 
  hasGenerationItem.value && 
  !submitting.value &&
  !thumbnailAiNotConfigured.value
)

// Load asset config
async function loadAssetConfig() {
  loadingConfig.value = true
  try {
    const res = await api.get('/config/asset')
    if (res.data) {
      if (res.data.title_count) titleCandidateCount.value = res.data.title_count
      // Check if thumbnail AI is configured
      thumbnailAiConfigured.value = !!res.data.thumbnail_ai_provider_id
    }
  } catch (e) {
    console.error('Failed to load asset config:', e)
  } finally {
    loadingConfig.value = false
  }
}

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
    // Filter videos that have subtitle (original or translated)
    searchResults.value = videosStore.videos
      .filter(v => v.files?.subtitle_original || v.files?.subtitle_translated)
      .map(v => ({
        ...v,
        selected: selectedVideos.value.some(sv => sv.id === v.id)
      }))
  } finally {
    searching.value = false
  }
}

// Toggle video selection in search mode
function toggleVideoSelect(video) {
  const idx = selectedVideos.value.findIndex(v => v.id === video.id)
  if (idx === -1) {
    selectedVideos.value.push(video)
  } else {
    selectedVideos.value.splice(idx, 1)
  }
  const resultVideo = searchResults.value.find(v => v.id === video.id)
  if (resultVideo) {
    resultVideo.selected = idx === -1
  }
}

// Remove selected video
function removeSelected(video) {
  const idx = selectedVideos.value.findIndex(v => v.id === video.id)
  if (idx !== -1) {
    selectedVideos.value.splice(idx, 1)
  }
  const resultVideo = searchResults.value.find(v => v.id === video.id)
  if (resultVideo) {
    resultVideo.selected = false
  }
}

// Load videos by tag
watch(selectedTag, async (tag) => {
  if (!tag) {
    tagVideos.value = []
    return
  }
  loadingTagVideos.value = true
  try {
    await videosStore.fetchVideos({ tag, page_size: 100 })
    tagVideos.value = videosStore.videos
      .filter(v => v.files?.subtitle_original || v.files?.subtitle_translated)
      .map(v => ({ ...v, selected: true }))
  } finally {
    loadingTagVideos.value = false
  }
})

// Toggle all tag videos
function toggleAllTagVideos() {
  const allSelected = tagVideos.value.every(v => v.selected)
  tagVideos.value.forEach(v => v.selected = !allSelected)
}

// Get subtitle status text
function getSubtitleStatus(video) {
  const hasOriginal = !!video.files?.subtitle_original
  const hasTranslated = !!video.files?.subtitle_translated
  if (hasTranslated) return '✓ 已翻译'
  if (hasOriginal) return '✓ 原始字幕'
  return '无字幕'
}

// Submit tasks
async function handleSubmit() {
  if (!canSubmit.value) return
  
  submitting.value = true
  try {
    const videosToProcess = selectionMode.value === 'search' 
      ? selectedVideos.value 
      : tagVideos.value.filter(v => v.selected)
    
    for (const video of videosToProcess) {
      await tasksStore.createTask({
        type: 'asset_gen',
        payload: {
          video_id: video.id,
          generate_title: generateTitle.value,
          generate_summary: generateSummary.value,
          generate_thumbnail: generateThumbnail.value,
          title_config: generateTitle.value ? {
            candidate_count: titleCandidateCount.value,
            target_platform: targetPlatform.value,
            include_emoji: includeEmoji.value
          } : null,
          summary_config: generateSummary.value ? {
            style: summaryStyle.value,
            max_length: summaryMaxLength.value
          } : null,
          thumbnail_config: generateThumbnail.value ? {
            mode: thumbnailMode.value,
            frame_time: frameTime.value,
            output_width: outputWidth.value,
            output_height: outputHeight.value
          } : null
        }
      })
    }
    
    emit('created', videosToProcess.length)
    emit('close')
  } catch (e) {
    console.error('Failed to create asset tasks:', e)
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('close')
}

onMounted(() => {
  loadAssetConfig()
  videosStore.fetchVideos({ page_size: 100 })
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>🎨 新建素材生成任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div class="modal-body">
          <!-- Generation Items Selection -->
          <div class="section">
            <div class="section-title">生成项目</div>
            <div class="gen-items">
              <label class="gen-item" :class="{ selected: generateTitle }">
                <input type="checkbox" v-model="generateTitle" />
                <span class="item-icon">📝</span>
                <span class="item-label">标题候选</span>
              </label>
              <label class="gen-item" :class="{ selected: generateSummary }">
                <input type="checkbox" v-model="generateSummary" />
                <span class="item-icon">📄</span>
                <span class="item-label">视频摘要</span>
              </label>
              <label class="gen-item" :class="{ selected: generateThumbnail }">
                <input type="checkbox" v-model="generateThumbnail" />
                <span class="item-icon">🖼️</span>
                <span class="item-label">缩略图</span>
              </label>
            </div>
          </div>

          <!-- Selection Mode Tabs -->
          <div class="mode-tabs">
            <button 
              :class="{ active: selectionMode === 'search' }"
              @click="selectionMode = 'search'"
            >
              🔍 搜索视频
            </button>
            <button 
              :class="{ active: selectionMode === 'tag' }"
              @click="selectionMode = 'tag'"
            >
              🏷️ 按标签选择
            </button>
          </div>

          <div class="info-hint">
            <span class="hint-icon">💡</span>
            <span>仅显示有字幕的视频（用于生成摘要和标题）</span>
          </div>

          <!-- Search Mode -->
          <div v-if="selectionMode === 'search'" class="search-section">
            <div class="search-input-wrapper">
              <input
                v-model="searchKeyword"
                type="text"
                class="search-input"
                placeholder="输入视频标题搜索..."
              />
              <span v-if="searching" class="search-loading">搜索中...</span>
            </div>
            
            <div v-if="searchResults.length > 0" class="video-list search-results">
              <div 
                v-for="video in searchResults" 
                :key="video.id"
                class="video-item"
                :class="{ selected: video.selected }"
                @click="toggleVideoSelect(video)"
              >
                <div class="video-checkbox">
                  <input type="checkbox" :checked="video.selected" @click.stop />
                </div>
                <img 
                  v-if="video.thumbnail" 
                  :src="video.thumbnail" 
                  class="video-thumb"
                  alt=""
                />
                <div class="video-thumb placeholder" v-else>🎬</div>
                <div class="video-info">
                  <div class="video-title">{{ video.title }}</div>
                  <div class="video-meta">
                    <span v-if="video.duration">{{ Math.floor(video.duration / 60) }}:{{ String(Math.floor(video.duration % 60)).padStart(2, '0') }}</span>
                    <span class="has-subtitle">{{ getSubtitleStatus(video) }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="searchKeyword && !searching" class="empty-hint">
              未找到有字幕的视频
            </div>

            <div v-if="selectedVideos.length > 0" class="selected-section">
              <div class="section-title">已选择 {{ selectedVideos.length }} 个视频</div>
              <div class="selected-list">
                <div 
                  v-for="video in selectedVideos" 
                  :key="video.id"
                  class="selected-chip"
                >
                  <span class="chip-title">{{ video.title }}</span>
                  <button class="chip-remove" @click="removeSelected(video)">✕</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Tag Mode -->
          <div v-if="selectionMode === 'tag'" class="tag-section">
            <div class="form-group">
              <label>选择标签</label>
              <select v-model="selectedTag" class="form-select">
                <option value="">-- 请选择标签 --</option>
                <option v-for="tag in allTags" :key="tag" :value="tag">
                  {{ tag }}
                </option>
              </select>
            </div>

            <div v-if="loadingTagVideos" class="loading-hint">加载中...</div>
            
            <div v-else-if="tagVideos.length > 0" class="tag-videos">
              <div class="tag-videos-header">
                <span>共 {{ tagVideos.length }} 个有字幕的视频</span>
                <button class="select-all-btn" @click="toggleAllTagVideos">
                  {{ tagVideos.every(v => v.selected) ? '取消全选' : '全选' }}
                </button>
              </div>
              <div class="video-list">
                <div 
                  v-for="video in tagVideos" 
                  :key="video.id"
                  class="video-item"
                  :class="{ selected: video.selected }"
                  @click="video.selected = !video.selected"
                >
                  <div class="video-checkbox">
                    <input type="checkbox" :checked="video.selected" @click.stop />
                  </div>
                  <img 
                    v-if="video.thumbnail" 
                    :src="video.thumbnail" 
                    class="video-thumb"
                    alt=""
                  />
                  <div class="video-thumb placeholder" v-else>🎬</div>
                  <div class="video-info">
                    <div class="video-title">{{ video.title }}</div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="selectedTag" class="empty-hint">
              该标签下没有有字幕的视频
            </div>
          </div>

          <!-- Title Generation Config -->
          <div v-if="generateTitle" class="config-section">
            <div class="section-title">📝 标题生成配置</div>
            <div class="config-grid">
              <div class="form-group">
                <label>候选数量</label>
                <input 
                  v-model.number="titleCandidateCount" 
                  type="number" 
                  class="form-input"
                  min="3"
                  max="10"
                  :disabled="loadingConfig"
                />
              </div>
              <div class="form-group">
                <label>目标平台</label>
                <select v-model="targetPlatform" class="form-select" :disabled="loadingConfig">
                  <option v-for="opt in platformOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
            </div>
            <div class="form-group checkbox-group">
              <label>
                <input type="checkbox" v-model="includeEmoji" :disabled="loadingConfig" />
                包含表情符号
              </label>
            </div>
          </div>

          <!-- Summary Generation Config -->
          <div v-if="generateSummary" class="config-section">
            <div class="section-title">📄 摘要生成配置</div>
            <div class="config-grid">
              <div class="form-group">
                <label>摘要风格</label>
                <select v-model="summaryStyle" class="form-select" :disabled="loadingConfig">
                  <option v-for="opt in summaryStyleOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
                <p class="form-hint">{{ summaryStyleOptions.find(s => s.value === summaryStyle)?.description }}</p>
              </div>
              <div class="form-group">
                <label>最大字数</label>
                <input 
                  v-model.number="summaryMaxLength" 
                  type="number" 
                  class="form-input"
                  min="100"
                  max="2000"
                  step="100"
                  :disabled="loadingConfig"
                />
              </div>
            </div>
          </div>

          <!-- Thumbnail Generation Config -->
          <div v-if="generateThumbnail" class="config-section">
            <div class="section-title">🖼️ 缩略图生成配置</div>
            <div class="form-group">
              <label>生成方式</label>
              <div class="mode-options">
                <label 
                  v-for="opt in thumbnailModeOptions" 
                  :key="opt.value"
                  class="mode-option"
                  :class="{ selected: thumbnailMode === opt.value }"
                >
                  <input type="radio" :value="opt.value" v-model="thumbnailMode" :disabled="loadingConfig" />
                  <div class="mode-content">
                    <span class="mode-label">{{ opt.label }}</span>
                    <span class="mode-desc">{{ opt.description }}</span>
                  </div>
                </label>
              </div>
            </div>
            
            <!-- Warning when AI mode selected but not configured -->
            <div v-if="thumbnailMode === 'ai' && !thumbnailAiConfigured" class="config-warning">
              <span class="warning-icon">⚠️</span>
              <span>AI 生成缩略图需要先在「设置 → 素材生成」中配置 AI 服务商</span>
            </div>
            
            <div v-if="thumbnailMode === 'frame'" class="config-grid">
              <div class="form-group">
                <label>截帧时间</label>
                <input 
                  v-model="frameTime" 
                  type="text" 
                  class="form-input"
                  placeholder="auto 或 00:01:30"
                  :disabled="loadingConfig"
                />
                <p class="form-hint">auto 自动选取，或指定时间如 00:01:30</p>
              </div>
              <div class="form-group">
                <label>输出尺寸</label>
                <div class="size-inputs">
                  <input 
                    v-model.number="outputWidth" 
                    type="number" 
                    class="form-input size-input"
                    :disabled="loadingConfig"
                  />
                  <span>×</span>
                  <input 
                    v-model.number="outputHeight" 
                    type="number" 
                    class="form-input size-input"
                    :disabled="loadingConfig"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <div class="footer-info">
            <span v-if="thumbnailAiNotConfigured" class="warning">
              请先配置 AI 缩略图服务商，或选择视频截帧方式
            </span>
            <span v-else-if="selectedCount > 0 && hasGenerationItem">
              将创建 {{ selectedCount }} 个素材生成任务
            </span>
            <span v-else-if="!hasGenerationItem" class="warning">
              请至少选择一个生成项目
            </span>
          </div>
          <div class="footer-actions">
            <button class="btn btn-secondary" @click="handleClose">取消</button>
            <button 
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
  max-width: 680px;
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

.gen-items {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.gen-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  input {
    display: none;
  }
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  &.selected {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.1);
  }
  
  .item-icon {
    font-size: 18px;
  }
  
  .item-label {
    font-size: 14px;
    color: var(--text-primary);
  }
}

.mode-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  
  button {
    flex: 1;
    padding: 10px 16px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
    
    &:hover {
      border-color: var(--accent-color);
    }
    
    &.active {
      background-color: rgba(59, 130, 246, 0.1);
      border-color: var(--accent-color);
      color: var(--accent-color);
    }
  }
}

.info-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background-color: rgba(59, 130, 246, 0.1);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--accent-color);
}

.search-section, .tag-section {
  margin-bottom: 20px;
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
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  
  &.search-results {
    margin-bottom: 16px;
  }
}

.video-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-bottom: 1px solid var(--border-color);
  
  &:last-child {
    border-bottom: none;
  }
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.selected {
    background-color: rgba(59, 130, 246, 0.1);
  }
}

.video-checkbox input {
  width: 16px;
  height: 16px;
  accent-color: var(--accent-color);
}

.video-thumb {
  width: 48px;
  height: 36px;
  object-fit: cover;
  border-radius: 4px;
  
  &.placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-primary);
    font-size: 16px;
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
  display: flex;
  gap: 8px;
  
  .has-subtitle {
    color: var(--success, #22c55e);
  }
}

.selected-section {
  margin-top: 16px;
}

.selected-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.selected-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  font-size: 12px;
  
  .chip-title {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-primary);
  }
  
  .chip-remove {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    padding: 0;
    
    &:hover {
      color: var(--error);
    }
  }
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

.form-select, .form-input {
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
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.form-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.tag-videos-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  
  span {
    font-size: 13px;
    color: var(--text-secondary);
  }
}

.select-all-btn {
  padding: 4px 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  
  &:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }
}

.loading-hint, .empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 14px;
}

.config-section {
  padding: 16px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  margin-bottom: 16px;
}

.config-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background-color: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 6px;
  margin-top: 12px;
  font-size: 13px;
  color: var(--warning, #f59e0b);
  
  .warning-icon {
    font-size: 16px;
  }
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.checkbox-group {
  label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      accent-color: var(--accent-color);
    }
  }
}

.mode-options {
  display: flex;
  gap: 12px;
}

.mode-option {
  flex: 1;
  padding: 12px;
  background-color: var(--bg-secondary);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  input {
    display: none;
  }
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  &.selected {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.1);
  }
}

.mode-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mode-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.mode-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.size-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .size-input {
    width: 80px;
  }
  
  span {
    color: var(--text-muted);
  }
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.footer-info {
  font-size: 13px;
  color: var(--text-secondary);
  
  .warning {
    color: var(--warning, #f59e0b);
  }
}

.footer-actions {
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
