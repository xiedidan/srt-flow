<script setup>
/**
 * Synthesis Task Create Modal - Simplified
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useVideosStore } from '@/stores/videos'
import { useTasksStore } from '@/stores/tasks'
import api from '@/api'

const emit = defineEmits(['close', 'created'])

const videosStore = useVideosStore()
const tasksStore = useTasksStore()

const selectionMode = ref('search')
const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)
const selectedVideos = ref([])
const selectedTag = ref('')
const tagVideos = ref([])
const loadingTagVideos = ref(false)
const subtitleMode = ref('dual')
const videoEncoder = ref('libx264')  // Will be updated from system config
const submitting = ref(false)

// GPU info
const gpuInfo = ref(null)
const loadingGpu = ref(true)

const subtitleModeOptions = [
  { value: 'original_only', label: '仅原始字幕' },
  { value: 'translated_only', label: '仅翻译字幕' },
  { value: 'dual', label: '双字幕叠加' }
]

// Encoder options based on GPU availability
const encoderOptions = computed(() => {
  const nvencAvailable = gpuInfo.value?.nvenc_available || false
  return [
    { value: 'libx264', label: 'H.264 (CPU)', available: true },
    { value: 'h264_nvenc', label: 'H.264 NVENC (GPU)', available: nvencAvailable },
    { value: 'libx265', label: 'H.265 (CPU)', available: true },
    { value: 'hevc_nvenc', label: 'H.265 NVENC (GPU)', available: nvencAvailable }
  ]
})

const allTags = computed(() => videosStore.allTags)

const selectedCount = computed(() => {
  if (selectionMode.value === 'search') return selectedVideos.value.length
  return tagVideos.value.filter(v => v.selected).length
})

function hasRequiredSubtitle(video) {
  if (subtitleMode.value === 'original_only') return !!video.files?.subtitle_original
  if (subtitleMode.value === 'translated_only') return !!video.files?.subtitle_translated
  return !!video.files?.subtitle_original && !!video.files?.subtitle_translated
}

const canSubmit = computed(() => selectedCount.value > 0 && !submitting.value)

let searchTimeout = null
watch(searchKeyword, (keyword) => {
  clearTimeout(searchTimeout)
  if (!keyword.trim()) { searchResults.value = []; return }
  searchTimeout = setTimeout(() => doSearch(keyword), 300)
})

async function doSearch(keyword) {
  if (!keyword.trim()) return
  searching.value = true
  try {
    await videosStore.fetchVideos({ keyword, page_size: 20 })
    searchResults.value = videosStore.videos
      .filter(v => hasRequiredSubtitle(v))
      .map(v => ({ ...v, selected: selectedVideos.value.some(sv => sv.id === v.id) }))
  } finally { searching.value = false }
}

function toggleVideoSelect(video) {
  const idx = selectedVideos.value.findIndex(v => v.id === video.id)
  if (idx === -1) selectedVideos.value.push(video)
  else selectedVideos.value.splice(idx, 1)
  const r = searchResults.value.find(v => v.id === video.id)
  if (r) r.selected = idx === -1
}

function removeSelected(video) {
  const idx = selectedVideos.value.findIndex(v => v.id === video.id)
  if (idx !== -1) selectedVideos.value.splice(idx, 1)
  const r = searchResults.value.find(v => v.id === video.id)
  if (r) r.selected = false
}

watch(selectedTag, async (tag) => {
  if (!tag) { tagVideos.value = []; return }
  loadingTagVideos.value = true
  try {
    await videosStore.fetchVideos({ tag, page_size: 100 })
    tagVideos.value = videosStore.videos.filter(v => hasRequiredSubtitle(v)).map(v => ({ ...v, selected: true }))
  } finally { loadingTagVideos.value = false }
})

function toggleAllTagVideos() {
  const all = tagVideos.value.every(v => v.selected)
  tagVideos.value.forEach(v => v.selected = !all)
}

async function handleSubmit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const videos = selectionMode.value === 'search' ? selectedVideos.value : tagVideos.value.filter(v => v.selected)
    for (const video of videos) {
      await tasksStore.createTask({
        type: 'synthesize',
        payload: { video_id: video.id, subtitle_mode: subtitleMode.value, video_encoder: videoEncoder.value }
      })
    }
    emit('created', videos.length)
    emit('close')
  } catch (e) { console.error('Failed:', e) }
  finally { submitting.value = false }
}

async function loadGpuInfo() {
  loadingGpu.value = true
  try {
    // Load GPU info and system config in parallel
    const [gpuResponse, configResponse] = await Promise.all([
      api.get('/system/gpu'),
      api.get('/config/synthesis')
    ])
    gpuInfo.value = gpuResponse.data
    
    // Set default encoder from system config
    const defaultEncoder = configResponse.data?.video_encoder
    if (defaultEncoder) {
      // Check if the configured encoder is available
      const nvencAvailable = gpuResponse.data?.nvenc_available || false
      const isNvenc = defaultEncoder.includes('nvenc')
      
      if (isNvenc && !nvencAvailable) {
        // Fallback to CPU encoder if GPU not available
        videoEncoder.value = defaultEncoder.includes('h265') || defaultEncoder.includes('hevc') 
          ? 'libx265' 
          : 'libx264'
      } else {
        videoEncoder.value = defaultEncoder
      }
    }
  } catch (e) {
    console.error('Failed to load GPU info:', e)
    gpuInfo.value = { gpu_available: false, nvenc_available: false }
  } finally {
    loadingGpu.value = false
  }
}

function handleClose() { emit('close') }

onMounted(() => { 
  videosStore.fetchVideos({ page_size: 100 })
  loadGpuInfo()
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>🎞️ 新建视频合成任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        <div class="modal-body">
          <div class="section">
            <div class="section-title">字幕模式</div>
            <div class="mode-options">
              <label v-for="opt in subtitleModeOptions" :key="opt.value" class="mode-option" :class="{ selected: subtitleMode === opt.value }">
                <input type="radio" :value="opt.value" v-model="subtitleMode" />
                <span>{{ opt.label }}</span>
              </label>
            </div>
          </div>
          <div class="mode-tabs">
            <button :class="{ active: selectionMode === 'search' }" @click="selectionMode = 'search'">🔍 搜索视频</button>
            <button :class="{ active: selectionMode === 'tag' }" @click="selectionMode = 'tag'">🏷️ 按标签选择</button>
          </div>
          <div v-if="selectionMode === 'search'" class="search-section">
            <input v-model="searchKeyword" type="text" class="search-input" placeholder="输入视频标题搜索..." />
            <div v-if="searchResults.length > 0" class="video-list">
              <div v-for="video in searchResults" :key="video.id" class="video-item" :class="{ selected: video.selected }" @click="toggleVideoSelect(video)">
                <input type="checkbox" :checked="video.selected" @click.stop />
                <span class="video-title">{{ video.title }}</span>
              </div>
            </div>
            <div v-else-if="searchKeyword && !searching" class="empty-hint">未找到符合条件的视频</div>
            <div v-if="selectedVideos.length > 0" class="selected-section">
              <div class="section-title">已选择 {{ selectedVideos.length }} 个视频</div>
              <div class="selected-list">
                <span v-for="video in selectedVideos" :key="video.id" class="selected-chip">{{ video.title }}<button @click="removeSelected(video)">✕</button></span>
              </div>
            </div>
          </div>
          <div v-if="selectionMode === 'tag'" class="tag-section">
            <select v-model="selectedTag" class="form-select">
              <option value="">-- 请选择标签 --</option>
              <option v-for="tag in allTags" :key="tag" :value="tag">{{ tag }}</option>
            </select>
            <div v-if="loadingTagVideos" class="loading-hint">加载中...</div>
            <div v-else-if="tagVideos.length > 0" class="tag-videos">
              <div class="tag-videos-header"><span>共 {{ tagVideos.length }} 个视频</span><button @click="toggleAllTagVideos">{{ tagVideos.every(v => v.selected) ? '取消全选' : '全选' }}</button></div>
              <div class="video-list">
                <div v-for="video in tagVideos" :key="video.id" class="video-item" :class="{ selected: video.selected }" @click="video.selected = !video.selected">
                  <input type="checkbox" :checked="video.selected" @click.stop />
                  <span class="video-title">{{ video.title }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="section">
            <div class="section-title">视频编码</div>
            <div v-if="loadingGpu" class="loading-hint">检测 GPU...</div>
            <template v-else>
              <div v-if="gpuInfo?.gpu_available" class="gpu-status available">
                🎮 检测到 GPU: {{ gpuInfo.gpu_name }}
              </div>
              <div v-else class="gpu-status">
                💻 未检测到 NVIDIA GPU，仅支持 CPU 编码
              </div>
              <div class="encoder-options">
                <label 
                  v-for="opt in encoderOptions" 
                  :key="opt.value" 
                  class="encoder-option"
                  :class="{ selected: videoEncoder === opt.value, disabled: !opt.available }"
                >
                  <input 
                    type="radio" 
                    :value="opt.value" 
                    v-model="videoEncoder" 
                    :disabled="!opt.available"
                  />
                  <span>{{ opt.label }}</span>
                  <span v-if="opt.value.includes('nvenc')" class="gpu-badge">GPU</span>
                </label>
              </div>
            </template>
          </div>
        </div>
        <div class="modal-footer">
          <span v-if="selectedCount > 0">将创建 {{ selectedCount }} 个任务</span>
          <div class="footer-actions">
            <button class="btn btn-secondary" @click="handleClose">取消</button>
            <button class="btn btn-primary" :disabled="!canSubmit" @click="handleSubmit">{{ submitting ? '创建中...' : '创建任务' }}</button>
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
  z-index: 2000;
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

.mode-options {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.mode-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-primary);
  
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

.mode-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  
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

.search-section, .tag-section {
  margin-bottom: 20px;
}

.search-input, .form-select {
  width: 100%;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  margin-bottom: 12px;
  box-sizing: border-box;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
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
  color: var(--text-primary);
  
  &:last-child {
    border-bottom: none;
  }
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.selected {
    background-color: rgba(59, 130, 246, 0.1);
  }
  
  input {
    width: 16px;
    height: 16px;
    accent-color: var(--accent-color);
  }
}

.video-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  font-size: 12px;
  color: var(--text-primary);
  
  button {
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

.tag-videos {
  margin-top: 12px;
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
  
  button {
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
}

.empty-hint, .loading-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 14px;
}

.gpu-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  
  &.available {
    background-color: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.3);
    color: var(--success);
  }
}

.encoder-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.encoder-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background-color: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-primary);
  font-size: 13px;
  
  input[type="radio"] {
    display: none;
  }
  
  &:hover:not(.disabled) {
    border-color: var(--accent-color);
  }
  
  &.selected {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.1);
  }
  
  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .gpu-badge {
    padding: 2px 6px;
    background-color: rgba(34, 197, 94, 0.15);
    color: var(--success);
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
  }
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  
  > span {
    font-size: 13px;
    color: var(--text-secondary);
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
