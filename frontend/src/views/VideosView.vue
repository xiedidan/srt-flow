<script setup>
/**
 * Videos management view
 * Displays video list with filtering, search, and batch operations
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useVideosStore } from '@/stores/videos'
import { useTasksStore } from '@/stores/tasks'
import { useWebSocket } from '@/composables/useWebSocket'
import { useViewMode } from '@/composables/useViewMode'
import VideoCard from '@/components/videos/VideoCard.vue'
import VideoDetailModal from '@/components/videos/VideoDetailModal.vue'
import DownloadModal from '@/components/videos/DownloadModal.vue'
import AsrTaskModal from '@/components/tasks/AsrTaskModal.vue'
import TranslateTaskModal from '@/components/tasks/TranslateTaskModal.vue'
import SynthesisTaskModal from '@/components/tasks/SynthesisTaskModal.vue'
import TtsTaskModal from '@/components/tasks/TtsTaskModal.vue'
import Pagination from '@/components/common/Pagination.vue'

const videosStore = useVideosStore()
const tasksStore = useTasksStore()

// WebSocket for real-time download progress
const { connected } = useWebSocket((data) => {
  if (data.type === 'task_progress') {
    // Update download progress
    videosStore.updateDownloadProgress(data.data.task_id, data.data.progress)
  } else if (data.type === 'task_update') {
    // Handle task status changes
    videosStore.updateFromTaskUpdate(data.data)
  } else if (data.type === 'task_metadata') {
    // Handle metadata updates (title, thumbnail, etc.)
    videosStore.updateDownloadMetadata(data.data.task_id, data.data.metadata)
  }
})

// View mode with persistence
const { viewMode } = useViewMode('videos', 'grid')

// Search
const searchKeyword = ref('')
const selectedTag = ref('')

// Modal state
const showDetailModal = ref(false)
const showDownloadModal = ref(false)
const showAsrModal = ref(false)
const showTranslateModal = ref(false)
const showSynthesisModal = ref(false)
const showTtsModal = ref(false)
const selectedVideoId = ref(null)
const selectedVideoForAsr = ref(null)
const selectedVideoForTranslate = ref(null)
const selectedVideoForSynthesis = ref(null)
const selectedVideoForTts = ref(null)

// Computed
const filteredVideos = computed(() => videosStore.videos)

// Methods
function handleSearch() {
  videosStore.setFilters({ keyword: searchKeyword.value })
}

function handleTagFilter(tag) {
  selectedTag.value = tag
  videosStore.setFilters({ tag: tag || null })
}

function handlePageChange(page) {
  videosStore.setPage(page)
}

function handleViewVideo(video) {
  selectedVideoId.value = video.id
  showDetailModal.value = true
}

function handleSelectVideo(videoId) {
  videosStore.toggleSelect(videoId)
}

async function handleVideoAction({ type, video }) {
  // Check if video is valid
  if (!video || !video.id) {
    console.error('Invalid video object:', video)
    return
  }
  
  // ASR task needs confirmation modal for language selection
  if (type === 'asr') {
    selectedVideoForAsr.value = video
    showAsrModal.value = true
    showDetailModal.value = false
    return
  }
  
  // Translate task needs confirmation modal for language selection
  if (type === 'translate') {
    selectedVideoForTranslate.value = video
    showTranslateModal.value = true
    showDetailModal.value = false
    return
  }
  
  // Synthesis task needs confirmation modal for subtitle mode selection
  if (type === 'synthesize') {
    selectedVideoForSynthesis.value = video
    showSynthesisModal.value = true
    showDetailModal.value = false
    return
  }
  
  // TTS task needs confirmation modal for engine and options selection
  if (type === 'tts') {
    selectedVideoForTts.value = video
    showTtsModal.value = true
    showDetailModal.value = false
    return
  }
  
  if (['asset_gen'].includes(type)) {
    // Task type labels for user feedback
    const typeLabels = {
      asset_gen: '素材生成'
    }
    
    try {
      await tasksStore.createTask({
        type,
        payload: { video_id: video.id }
      })
      showDetailModal.value = false
      // Show success feedback
      alert(`${typeLabels[type]}任务已创建，请在任务列表中查看进度`)
    } catch (e) {
      console.error('Failed to create task:', e)
      alert(`创建${typeLabels[type]}任务失败: ${e.message || e}`)
    }
  }
}

function handleAsrTaskCreated() {
  showAsrModal.value = false
  selectedVideoForAsr.value = null
}

function handleTranslateTaskCreated() {
  showTranslateModal.value = false
  selectedVideoForTranslate.value = null
}

function handleSynthesisTaskCreated() {
  showSynthesisModal.value = false
  selectedVideoForSynthesis.value = null
}

function handleTtsTaskCreated() {
  showTtsModal.value = false
  selectedVideoForTts.value = null
}

async function handleDownload(data) {
  try {
    await tasksStore.createTask(data)
    showDownloadModal.value = false
    setTimeout(() => videosStore.fetchVideos(), 2000)
  } catch (e) {
    console.error('Failed to submit download:', e)
  }
}

async function handleBatchAction(action) {
  const ids = videosStore.selectedIds
  if (ids.length === 0) return
  
  if (action === 'delete') {
    if (!confirm(`确定要删除选中的 ${ids.length} 个视频吗？`)) return
  } else {
    for (const id of ids) {
      try {
        await tasksStore.createTask({
          type: action,
          payload: { video_id: id }
        })
      } catch (e) {
        console.error(`Failed to create ${action} task for ${id}:`, e)
      }
    }
    videosStore.clearSelection()
  }
}

function refreshVideos() {
  videosStore.fetchVideos()
}

onMounted(() => {
  videosStore.fetchVideos()
})

// Auto refresh every 30s as fallback when WS disconnected
let refreshInterval
onMounted(() => {
  refreshInterval = setInterval(() => {
    if (!connected.value) {
      videosStore.fetchVideos()
    }
  }, 30000)
})
onUnmounted(() => {
  clearInterval(refreshInterval)
})
</script>

<template>
  <div class="videos-view">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">视频管理</h2>
        <span class="video-count">{{ videosStore.pagination.total }} 个视频</span>
        <span class="ws-status" :class="{ connected }">
          {{ connected ? '● 实时' : '○ 离线' }}
        </span>
      </div>
      <div class="header-actions">
        <button class="btn-refresh" @click="refreshVideos" title="刷新">🔄</button>
        <button class="btn-primary" @click="showDownloadModal = true">
          <span>📥</span> 下载视频
        </button>
      </div>
    </div>
    
    <div class="toolbar">
      <div class="toolbar-left">
        <div class="search-box">
          <input v-model="searchKeyword" type="text" placeholder="搜索视频..." @keyup.enter="handleSearch" />
          <button @click="handleSearch">🔍</button>
        </div>
        <select v-model="selectedTag" class="tag-filter" @change="handleTagFilter(selectedTag)">
          <option value="">全部标签</option>
          <option v-for="tag in videosStore.allTags" :key="tag" :value="tag">{{ tag }}</option>
        </select>
      </div>
      
      <div class="toolbar-right">
        <div v-if="videosStore.selectedIds.length > 0" class="batch-actions">
          <span class="selected-count">已选 {{ videosStore.selectedIds.length }} 项</span>
          <button class="batch-btn" @click="handleBatchAction('asr')">🎤 批量识别</button>
          <button class="batch-btn" @click="handleBatchAction('translate')">🌐 批量翻译</button>
          <button class="batch-btn danger" @click="handleBatchAction('delete')">🗑️ 删除</button>
          <button class="batch-btn" @click="videosStore.clearSelection">取消</button>
        </div>
        <div class="view-toggle">
          <button :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" title="网格视图">▦</button>
          <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图">☰</button>
        </div>
        <label class="select-all">
          <input type="checkbox" :checked="videosStore.isAllSelected" @change="videosStore.toggleSelectAll" />
          全选
        </label>
      </div>
    </div>
    
    <div class="videos-content">
      <div v-if="videosStore.loading" class="loading"><span class="loading-spinner">⏳</span>加载中...</div>
      <div v-else-if="filteredVideos.length === 0" class="empty-state">
        <span class="icon">🎬</span>
        <p>暂无视频</p>
        <p class="hint">点击上方按钮下载第一个视频</p>
        <button class="btn-primary" @click="showDownloadModal = true">📥 下载视频</button>
      </div>
      <template v-else>
        <div class="videos-grid" :class="viewMode">
          <VideoCard v-for="video in filteredVideos" :key="video.id" :video="video"
            :selected="videosStore.selectedIds.includes(video.id)" :view-mode="viewMode"
            @view="handleViewVideo" @select="handleSelectVideo" @action="handleVideoAction" />
        </div>
        <div class="pagination-wrapper">
          <Pagination :page="videosStore.pagination.page" :total-pages="videosStore.totalPages"
            :total="videosStore.pagination.total" @change="handlePageChange" />
        </div>
      </template>
    </div>
    
    <VideoDetailModal :visible="showDetailModal" :video-id="selectedVideoId"
      @close="showDetailModal = false" @action="handleVideoAction" />
    <DownloadModal :visible="showDownloadModal" @close="showDownloadModal = false" @submit="handleDownload" />
    <AsrTaskModal 
      :visible="showAsrModal" 
      :video="selectedVideoForAsr"
      @close="showAsrModal = false" 
      @submit="handleAsrTaskCreated" 
    />
    <TranslateTaskModal
      :visible="showTranslateModal"
      :video="selectedVideoForTranslate"
      @close="showTranslateModal = false"
      @submit="handleTranslateTaskCreated"
    />
    <SynthesisTaskModal
      :visible="showSynthesisModal"
      :video="selectedVideoForSynthesis"
      @close="showSynthesisModal = false"
      @submit="handleSynthesisTaskCreated"
    />
    <TtsTaskModal
      :visible="showTtsModal"
      :video="selectedVideoForTts"
      @close="showTtsModal = false"
      @submit="handleTtsTaskCreated"
    />
  </div>
</template>


<style lang="scss" scoped>
.videos-view {
  max-width: 1400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.video-count {
  font-size: 14px;
  color: var(--text-muted);
}

.ws-status {
  font-size: 12px;
  color: var(--text-muted);
  
  &.connected {
    color: var(--success);
  }
}

.header-actions {
  display: flex;
  gap: 12px;
}

.btn-refresh {
  padding: 8px 12px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
  }
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background-color: var(--accent-color);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--accent-hover);
  }
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 12px 16px;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-box {
  display: flex;
  
  input {
    width: 200px;
    padding: 8px 12px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-right: none;
    border-radius: 6px 0 0 6px;
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
  
  button {
    padding: 8px 12px;
    background-color: var(--bg-hover);
    border: 1px solid var(--border-color);
    border-radius: 0 6px 6px 0;
    cursor: pointer;
    
    &:hover {
      background-color: var(--border-color);
    }
  }
}

.tag-filter {
  padding: 8px 12px;
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

.batch-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-count {
  font-size: 13px;
  color: var(--text-secondary);
  margin-right: 8px;
}

.batch-btn {
  padding: 6px 12px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 4px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  
  &:hover {
    background-color: var(--border-color);
  }
  
  &.danger:hover {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error);
  }
}

.view-toggle {
  display: flex;
  background-color: var(--bg-primary);
  border-radius: 6px;
  overflow: hidden;
  
  button {
    padding: 8px 12px;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 16px;
    
    &:hover {
      background-color: var(--bg-hover);
    }
    
    &.active {
      background-color: var(--accent-color);
      color: white;
    }
  }
}

.select-all {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  
  input {
    accent-color: var(--accent-color);
  }
}

.videos-content {
  min-height: 400px;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 80px 20px;
  color: var(--text-secondary);
}

.loading-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
  
  .icon {
    font-size: 64px;
    margin-bottom: 16px;
  }
  
  p {
    color: var(--text-secondary);
    margin: 4px 0;
  }
  
  .hint {
    font-size: 14px;
    margin-bottom: 24px;
  }
}

.videos-grid {
  &.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
  }
  
  &.list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}
</style>
