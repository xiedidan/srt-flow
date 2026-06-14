<script setup>
/**
 * Asset Result View Component
 * Displays generated assets: titles, summary, and thumbnail
 * Supports copy, edit, and download operations
 */
import { ref, computed, watch } from 'vue'
import api from '@/api'

const props = defineProps({
  task: {
    type: Object,
    required: true
  },
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'update'])

// Result data
const titles = ref([])
const summary = ref('')
const thumbnailUrl = ref('')
const editingSummary = ref(false)
const editedSummary = ref('')
const savingSummary = ref(false)
const copySuccess = ref('')

// Loading states
const loadingTitles = ref(false)
const loadingSummary = ref(false)
const loadingThumbnail = ref(false)

// Computed properties
const videoId = computed(() => props.task?.payload?.video_id || props.task?.video_id)
const result = computed(() => props.task?.result || {})

const generatedItems = computed(() => result.value.generated_items || [])
const hasTitles = computed(() => generatedItems.value.includes('title') || result.value.title_candidates_path)
const hasSummary = computed(() => generatedItems.value.includes('summary') || result.value.summary_path)
const hasThumbnail = computed(() => generatedItems.value.includes('thumbnail') || result.value.thumbnail_path)

// Load content when visible
watch(() => props.visible, async (visible) => {
  if (visible && props.task?.status === 'completed') {
    await loadResults()
  }
}, { immediate: true })

async function loadResults() {
  if (hasTitles.value) await loadTitles()
  if (hasSummary.value) await loadSummary()
  if (hasThumbnail.value) loadThumbnail()
}

async function loadTitles() {
  if (!videoId.value) return
  loadingTitles.value = true
  try {
    const res = await api.get(`/videos/${videoId.value}/files/title_candidates/content`)
    if (res.data) {
      // Parse titles from text file (one per line)
      const content = res.data.content || res.data
      titles.value = (typeof content === 'string' ? content : '')
        .split('\n')
        .map(line => line.trim())
        .filter(line => line && !line.startsWith('#'))
        .map(line => line.replace(/^\d+[\.\:\)\-]\s*/, '')) // Remove number prefix
    }
  } catch (e) {
    console.error('Failed to load titles:', e)
    titles.value = []
  } finally {
    loadingTitles.value = false
  }
}

async function loadSummary() {
  if (!videoId.value) return
  loadingSummary.value = true
  try {
    const res = await api.get(`/videos/${videoId.value}/files/summary/content`)
    if (res.data) {
      summary.value = res.data.content || res.data || ''
    }
  } catch (e) {
    console.error('Failed to load summary:', e)
    summary.value = ''
  } finally {
    loadingSummary.value = false
  }
}

function loadThumbnail() {
  if (!videoId.value) return
  loadingThumbnail.value = true
  // Use thumbnail API endpoint
  thumbnailUrl.value = `/api/v1/videos/${videoId.value}/thumbnail?t=${Date.now()}`
  loadingThumbnail.value = false
}

// Copy to clipboard
async function copyToClipboard(text, label) {
  try {
    await navigator.clipboard.writeText(text)
    copySuccess.value = label
    setTimeout(() => copySuccess.value = '', 2000)
  } catch (e) {
    console.error('Failed to copy:', e)
  }
}

function copyTitle(title, index) {
  copyToClipboard(title, `title-${index}`)
}

function copySummary() {
  copyToClipboard(summary.value, 'summary')
}

function copyAllTitles() {
  copyToClipboard(titles.value.join('\n'), 'all-titles')
}

// Edit summary
function startEditSummary() {
  editedSummary.value = summary.value
  editingSummary.value = true
}

function cancelEditSummary() {
  editingSummary.value = false
  editedSummary.value = ''
}

async function saveSummary() {
  if (!videoId.value) return
  savingSummary.value = true
  try {
    await api.put(`/videos/${videoId.value}/files/summary/content`, {
      content: editedSummary.value
    })
    summary.value = editedSummary.value
    editingSummary.value = false
    emit('update')
  } catch (e) {
    console.error('Failed to save summary:', e)
  } finally {
    savingSummary.value = false
  }
}

// Download thumbnail
function downloadThumbnail() {
  if (!thumbnailUrl.value) return
  const link = document.createElement('a')
  link.href = thumbnailUrl.value
  link.download = `thumbnail_${videoId.value}.jpg`
  link.click()
}

// Preview thumbnail in new tab
function previewThumbnail() {
  if (!thumbnailUrl.value) return
  window.open(thumbnailUrl.value, '_blank')
}

function handleClose() {
  emit('close')
}

function handleThumbnailError() {
  thumbnailUrl.value = ''
}
</script>

<template>
  <div v-if="visible" class="asset-result-view">
    <div class="result-header">
      <h4>🎨 生成结果</h4>
      <button class="close-btn" @click="handleClose">✕</button>
    </div>
    
    <div class="result-body">
      <!-- Titles Section -->
      <div v-if="hasTitles" class="result-section">
        <div class="section-header">
          <h5>📝 标题候选</h5>
          <button 
            v-if="titles.length > 0" 
            class="copy-all-btn"
            @click="copyAllTitles"
          >
            {{ copySuccess === 'all-titles' ? '✓ 已复制' : '复制全部' }}
          </button>
        </div>
        
        <div v-if="loadingTitles" class="loading">加载中...</div>
        <div v-else-if="titles.length > 0" class="titles-list">
          <div 
            v-for="(title, index) in titles" 
            :key="index"
            class="title-item"
          >
            <span class="title-index">{{ index + 1 }}</span>
            <span class="title-text">{{ title }}</span>
            <button 
              class="copy-btn"
              @click="copyTitle(title, index)"
              :title="copySuccess === `title-${index}` ? '已复制' : '复制'"
            >
              {{ copySuccess === `title-${index}` ? '✓' : '📋' }}
            </button>
          </div>
        </div>
        <div v-else class="empty-hint">暂无标题数据</div>
      </div>

      <!-- Summary Section -->
      <div v-if="hasSummary" class="result-section">
        <div class="section-header">
          <h5>📄 视频摘要</h5>
          <div class="section-actions">
            <button 
              v-if="!editingSummary && summary"
              class="action-btn"
              @click="copySummary"
            >
              {{ copySuccess === 'summary' ? '✓ 已复制' : '📋 复制' }}
            </button>
            <button 
              v-if="!editingSummary && summary"
              class="action-btn"
              @click="startEditSummary"
            >
              ✏️ 编辑
            </button>
          </div>
        </div>
        
        <div v-if="loadingSummary" class="loading">加载中...</div>
        <div v-else-if="editingSummary" class="summary-edit">
          <textarea 
            v-model="editedSummary"
            class="summary-textarea"
            rows="8"
          ></textarea>
          <div class="edit-actions">
            <button class="btn btn-secondary" @click="cancelEditSummary">取消</button>
            <button 
              class="btn btn-primary" 
              @click="saveSummary"
              :disabled="savingSummary"
            >
              {{ savingSummary ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
        <div v-else-if="summary" class="summary-content">
          <p>{{ summary }}</p>
        </div>
        <div v-else class="empty-hint">暂无摘要数据</div>
      </div>

      <!-- Thumbnail Section -->
      <div v-if="hasThumbnail" class="result-section">
        <div class="section-header">
          <h5>🖼️ 缩略图</h5>
          <div v-if="thumbnailUrl" class="section-actions">
            <button class="action-btn" @click="previewThumbnail">
              🔍 预览
            </button>
            <button class="action-btn" @click="downloadThumbnail">
              ⬇️ 下载
            </button>
          </div>
        </div>
        
        <div v-if="loadingThumbnail" class="loading">加载中...</div>
        <div v-else-if="thumbnailUrl" class="thumbnail-preview">
          <img 
            :src="thumbnailUrl" 
            alt="Thumbnail"
            @error="handleThumbnailError"
          />
        </div>
        <div v-else class="empty-hint">暂无缩略图</div>
      </div>

      <!-- No Results -->
      <div v-if="!hasTitles && !hasSummary && !hasThumbnail" class="no-results">
        <p>暂无生成结果</p>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.asset-result-view {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  
  h4 {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
  }
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
}

.result-body {
  padding: 20px;
  max-height: 500px;
  overflow-y: auto;
}

.result-section {
  margin-bottom: 24px;
  
  &:last-child {
    margin-bottom: 0;
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  
  h5 {
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
  }
}

.section-actions {
  display: flex;
  gap: 8px;
}

.action-btn, .copy-all-btn {
  padding: 4px 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }
}

.loading {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 14px;
}

.empty-hint {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
}

/* Titles */
.titles-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
  
  &:hover {
    background-color: var(--bg-hover);
  }
}

.title-index {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--accent-color);
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
}

.title-text {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.4;
}

.copy-btn {
  padding: 4px 8px;
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s;
  
  &:hover {
    opacity: 1;
  }
}

/* Summary */
.summary-content {
  padding: 16px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  
  p {
    margin: 0;
    font-size: 14px;
    color: var(--text-primary);
    line-height: 1.6;
    white-space: pre-wrap;
  }
}

.summary-edit {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-textarea {
  width: 100%;
  padding: 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
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

/* Thumbnail */
.thumbnail-preview {
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--bg-primary);
  
  img {
    width: 100%;
    max-height: 300px;
    object-fit: contain;
    display: block;
  }
}

.no-results {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
}
</style>
