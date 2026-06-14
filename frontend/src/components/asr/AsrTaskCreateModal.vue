<script setup>
/**
 * ASR Task Create Modal
 * Supports single video search and batch selection by tag
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useVideosStore } from '@/stores/videos'
import { useTasksStore } from '@/stores/tasks'

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

// ASR options
const language = ref('auto')
const model = ref('large-v3')

const languageOptions = [
  { value: 'auto', label: '自动检测' },
  { value: 'zh', label: '中文' },
  { value: 'en', label: '英语' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
  { value: 'ru', label: '俄语' }
]

const modelOptions = [
  { value: 'large-v3', label: 'Whisper Large V3 (推荐)' },
  { value: 'medium', label: 'Whisper Medium' },
  { value: 'small', label: 'Whisper Small (快速)' }
]

const submitting = ref(false)

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

// Can submit
const canSubmit = computed(() => selectedCount.value > 0 && !submitting.value)

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
    const response = await videosStore.fetchVideos({ keyword, page_size: 20 })
    searchResults.value = videosStore.videos.map(v => ({
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
  // Update search results selection state
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
    tagVideos.value = videosStore.videos.map(v => ({ ...v, selected: true }))
  } finally {
    loadingTagVideos.value = false
  }
})

// Toggle all tag videos
function toggleAllTagVideos() {
  const allSelected = tagVideos.value.every(v => v.selected)
  tagVideos.value.forEach(v => v.selected = !allSelected)
}

// Submit tasks
async function handleSubmit() {
  if (!canSubmit.value) return
  
  submitting.value = true
  try {
    const videosToProcess = selectionMode.value === 'search' 
      ? selectedVideos.value 
      : tagVideos.value.filter(v => v.selected)
    
    // Create tasks for each video
    for (const video of videosToProcess) {
      await tasksStore.createTask({
        type: 'asr',
        payload: {
          video_id: video.id,
          language: language.value,
          model: model.value
        }
      })
    }
    
    emit('created', videosToProcess.length)
    emit('close')
  } catch (e) {
    console.error('Failed to create ASR tasks:', e)
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('close')
}

// Load initial data
onMounted(() => {
  videosStore.fetchVideos({ page_size: 100 })
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>🎤 新建语音识别任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div class="modal-body">
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
            
            <!-- Search Results -->
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
                    <span v-if="video.duration">{{ video.duration }}</span>
                    <span v-if="video.tags?.length" class="video-tags">
                      {{ video.tags.slice(0, 3).join(', ') }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="searchKeyword && !searching" class="empty-hint">
              未找到匹配的视频
            </div>

            <!-- Selected Videos -->
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
                <span>共 {{ tagVideos.length }} 个视频</span>
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
              该标签下没有视频
            </div>
          </div>

          <!-- ASR Options -->
          <div class="options-section">
            <div class="section-title">识别选项</div>
            <div class="options-grid">
              <div class="form-group">
                <label>源语言</label>
                <select v-model="language" class="form-select">
                  <option v-for="opt in languageOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label>模型</label>
                <select v-model="model" class="form-select">
                  <option v-for="opt in modelOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <div class="footer-info">
            <span v-if="selectedCount > 0">将创建 {{ selectedCount }} 个识别任务</span>
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
  max-width: 640px;
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
  
  &::placeholder {
    color: var(--text-muted);
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

.video-checkbox {
  input {
    width: 16px;
    height: 16px;
    accent-color: var(--accent-color);
  }
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
  
  span + span::before {
    content: ' · ';
  }
}

.selected-section {
  margin-top: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
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
    line-height: 1;
    
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

.form-select {
  width: 100%;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
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

.options-section {
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.options-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
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
