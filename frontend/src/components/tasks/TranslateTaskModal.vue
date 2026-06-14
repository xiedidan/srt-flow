<script setup>
/**
 * Translate Task Creation Modal - Enhanced with batch selection
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVideosStore } from '@/stores/videos'
import { useTasksStore } from '@/stores/tasks'
import api from '@/api'

const props = defineProps({
  visible: Boolean,
  video: Object
})

const emit = defineEmits(['close', 'submit'])
const router = useRouter()

const videosStore = useVideosStore()
const tasksStore = useTasksStore()

const selectionMode = ref('single')
const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)
const selectedVideos = ref([])
const selectedTag = ref('')
const tagVideos = ref([])
const loadingTagVideos = ref(false)
const sourceLanguage = ref('auto')
const targetLanguage = ref('zh-CN')
const taskContext = ref('')
const contextOverlapLines = ref(3)
const submitting = ref(false)
const globalConfig = ref(null)
const loadingConfig = ref(true)

const languageOptions = [
  { value: 'auto', label: '自动检测' },
  { value: 'en', label: '英语' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'zh-TW', label: '繁体中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
  { value: 'ru', label: '俄语' }
]

const targetLanguageOptions = languageOptions.filter(l => l.value !== 'auto')
const allTags = computed(() => videosStore.allTags)

const videosToProcess = computed(() => {
  if (selectionMode.value === 'single' && props.video) return [props.video]
  if (selectionMode.value === 'search') return selectedVideos.value
  if (selectionMode.value === 'tag') return tagVideos.value.filter(v => v.selected)
  return []
})

const selectedCount = computed(() => videosToProcess.value.length)
const canSubmit = computed(() => selectedCount.value > 0 && !submitting.value && !loadingConfig.value)

function hasRequiredSubtitle(video) {
  return !!video.files?.subtitle_original
}

function hasTranslatedSubtitle(video) {
  return !!video.files?.subtitle_translated
}

const videosWithTranslation = computed(() => {
  return videosToProcess.value.filter(v => hasTranslatedSubtitle(v)).length
})

async function loadGlobalConfig() {
  loadingConfig.value = true
  try {
    const res = await api.get('/config/global')
    globalConfig.value = res.data
    if (globalConfig.value?.default_source_language) {
      sourceLanguage.value = globalConfig.value.default_source_language
    }
    if (globalConfig.value?.default_target_language) {
      targetLanguage.value = globalConfig.value.default_target_language
    }
    const translateRes = await api.get('/config/translate')
    if (translateRes.data?.context_overlap_lines !== undefined) {
      contextOverlapLines.value = translateRes.data.context_overlap_lines
    }
  } catch (e) {
    console.error('Failed to load config:', e)
  } finally {
    loadingConfig.value = false
  }
}

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

watch(() => props.visible, (visible) => {
  if (visible) {
    loadGlobalConfig()
    taskContext.value = ''
    if (props.video) {
      selectionMode.value = 'single'
    } else {
      selectionMode.value = 'search'
      selectedVideos.value = []
      searchKeyword.value = ''
      searchResults.value = []
    }
  }
})

onMounted(() => {
  if (props.visible) {
    loadGlobalConfig()
    if (!props.video) videosStore.fetchVideos({ page_size: 100 })
  }
})

async function handleSubmit() {
  if (!canSubmit.value) return
  const videos = videosToProcess.value
  const videosWithoutSubtitle = videos.filter(v => !hasRequiredSubtitle(v))
  if (videosWithoutSubtitle.length > 0) {
    alert(`有 ${videosWithoutSubtitle.length} 个视频没有原始字幕，请先进行语音识别`)
    return
  }
  if (videosWithTranslation.value > 0) {
    const confirmed = confirm(`有 ${videosWithTranslation.value} 个视频已有翻译结果，继续将覆盖原有翻译字幕。是否继续？`)
    if (!confirmed) return
  }
  submitting.value = true
  try {
    for (const video of videos) {
      await tasksStore.createTask({
        type: 'translate',
        payload: {
          video_id: video.id,
          source_language: sourceLanguage.value,
          target_language: targetLanguage.value,
          task_context: taskContext.value.trim() || null,
          context_overlap_lines: contextOverlapLines.value
        }
      })
    }
    emit('submit', videos.length)
    if (confirm(`成功创建 ${videos.length} 个翻译任务！是否跳转到字幕翻译任务页面？`)) {
      router.push('/translate')
    }
    emit('close')
  } catch (e) {
    console.error('Failed:', e)
    alert('创建任务失败: ' + (e.message || '未知错误'))
  } finally { submitting.value = false }
}

function handleClose() { emit('close') }
</script>


<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container" :class="{ 'wide': selectionMode !== 'single' }">
        <div class="modal-header">
          <h3>🌐 创建字幕翻译任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="!props.video" class="mode-tabs">
            <button :class="{ active: selectionMode === 'search' }" @click="selectionMode = 'search'">🔍 搜索视频</button>
            <button :class="{ active: selectionMode === 'tag' }" @click="selectionMode = 'tag'">🏷️ 按标签选择</button>
          </div>
          <div class="info-hint">
            <span class="hint-icon">💡</span>
            <span>仅显示已完成语音识别的视频（有原始字幕）</span>
          </div>

          <div v-if="selectionMode === 'single' && props.video" class="video-info-card">
            <img v-if="props.video.thumbnail" :src="props.video.thumbnail" class="video-thumb" alt="" />
            <div class="video-thumb placeholder" v-else>🎬</div>
            <div class="video-details">
              <div class="video-title">{{ props.video.title }}</div>
              <div class="video-meta">
                <span>{{ props.video.source }}</span>
                <span v-if="props.video.duration">{{ Math.floor(props.video.duration / 60) }}:{{ String(Math.floor(props.video.duration % 60)).padStart(2, '0') }}</span>
              </div>
              <div v-if="hasTranslatedSubtitle(props.video)" class="warning-badge">⚠️ 已有翻译，将被覆盖</div>
            </div>
          </div>
          <div v-if="selectionMode === 'search'" class="search-section">
            <input v-model="searchKeyword" type="text" class="search-input" placeholder="输入视频标题搜索..." />
            <div v-if="searchResults.length > 0" class="video-list">
              <div v-for="video in searchResults" :key="video.id" class="video-item" :class="{ selected: video.selected }" @click="toggleVideoSelect(video)">
                <input type="checkbox" :checked="video.selected" @click.stop />
                <img v-if="video.thumbnail" :src="video.thumbnail" class="video-thumb" alt="" />
                <div class="video-thumb placeholder" v-else>🎬</div>
                <div class="video-info">
                  <div class="video-title">{{ video.title }}</div>
                  <div class="video-meta">
                    <span v-if="video.duration">{{ Math.floor(video.duration / 60) }}:{{ String(Math.floor(video.duration % 60)).padStart(2, '0') }}</span>
                    <span class="has-subtitle">✓ 有字幕</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="searchKeyword && !searching" class="empty-hint">未找到已识别的视频</div>
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
              <div class="tag-videos-header">
                <span>共 {{ tagVideos.length }} 个已识别视频</span>
                <button @click="toggleAllTagVideos">{{ tagVideos.every(v => v.selected) ? '取消全选' : '全选' }}</button>
              </div>
              <div class="video-list">
                <div v-for="video in tagVideos" :key="video.id" class="video-item" :class="{ selected: video.selected }" @click="video.selected = !video.selected">
                  <input type="checkbox" :checked="video.selected" @click.stop />
                  <img v-if="video.thumbnail" :src="video.thumbnail" class="video-thumb" alt="" />
                  <div class="video-thumb placeholder" v-else>🎬</div>
                  <div class="video-info">
                    <div class="video-title">{{ video.title }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="videosWithTranslation > 0" class="warning-box">
            <span class="warning-icon">⚠️</span>
            <span>有 {{ videosWithTranslation }} 个视频已有翻译结果，重新翻译将覆盖原有字幕</span>
          </div>
          <div class="form-group">
            <label for="source-language">源语言</label>
            <select id="source-language" v-model="sourceLanguage" class="form-select" :disabled="loadingConfig">
              <option v-for="lang in languageOptions" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label for="target-language">目标语言</label>
            <select id="target-language" v-model="targetLanguage" class="form-select" :disabled="loadingConfig">
              <option v-for="lang in targetLanguageOptions" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
            </select>
          </div>
          <details class="advanced-options">
            <summary>高级选项</summary>
            <div class="advanced-content">
              <div class="form-group">
                <label for="task-context">任务背景（可选）</label>
                <textarea id="task-context" v-model="taskContext" class="form-textarea" rows="3" placeholder="提供视频相关的背景信息，帮助 AI 更准确地翻译"></textarea>
                <p class="form-hint">背景信息会添加到翻译提示词中，帮助 AI 理解上下文</p>
              </div>
              <div class="form-group">
                <label for="context-overlap">批次上下文行数</label>
                <input id="context-overlap" v-model.number="contextOverlapLines" type="number" class="form-input" min="0" max="10" />
                <p class="form-hint">每个翻译批次前后包含的上下文行数（0-10）</p>
              </div>
            </div>
          </details>
        </div>
        <div class="modal-footer">
          <span v-if="selectedCount > 0">将创建 {{ selectedCount }} 个翻译任务</span>
          <div class="footer-actions">
            <button class="btn btn-secondary" @click="handleClose">取消</button>
            <button class="btn btn-primary" :disabled="!canSubmit" @click="handleSubmit">{{ submitting ? '创建中...' : '开始翻译' }}</button>
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
  max-width: 520px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
  
  &.wide { max-width: 640px; }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  
  h3 { margin: 0; font-size: 18px; color: var(--text-primary); }
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  
  &:hover { background-color: var(--bg-hover); color: var(--text-primary); }
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
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
    
    &:hover { border-color: var(--accent-color); }
    &.active { background-color: rgba(59, 130, 246, 0.1); border-color: var(--accent-color); color: var(--accent-color); }
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


.video-info-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  margin-bottom: 16px;
  
  .video-thumb {
    width: 80px;
    height: 60px;
    object-fit: cover;
    border-radius: 6px;
    flex-shrink: 0;
    
    &.placeholder {
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: var(--bg-secondary);
      font-size: 24px;
    }
  }
  
  .video-details { flex: 1; min-width: 0; }
  .video-title { font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px; }
  .video-meta { font-size: 12px; color: var(--text-muted); display: flex; gap: 8px; }
  .warning-badge { margin-top: 6px; font-size: 12px; color: var(--warning); }
}

.search-section, .tag-section { margin-bottom: 16px; }

.search-input, .form-select {
  width: 100%;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  margin-bottom: 12px;
  
  &:focus { outline: none; border-color: var(--accent-color); }
}

.video-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 12px;
}

.video-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-bottom: 1px solid var(--border-color);
  
  &:last-child { border-bottom: none; }
  &:hover { background-color: var(--bg-hover); }
  &.selected { background-color: rgba(59, 130, 246, 0.1); }
  
  input { width: 16px; height: 16px; accent-color: var(--accent-color); }
  
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
  
  .video-info { flex: 1; min-width: 0; }
  .video-title { font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .video-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; display: flex; gap: 8px; }
  .has-subtitle { color: var(--success); }
}


.selected-section { margin-top: 12px; }
.section-title { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-bottom: 8px; }
.selected-list { display: flex; flex-wrap: wrap; gap: 6px; }
.selected-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-primary);
  
  button {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    padding: 0;
    &:hover { color: var(--error); }
  }
}

.tag-videos-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  
  span { font-size: 13px; color: var(--text-secondary); }
  button {
    padding: 4px 10px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    &:hover { border-color: var(--accent-color); color: var(--accent-color); }
  }
}

.empty-hint, .loading-hint {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 14px;
}

.warning-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background-color: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #f59e0b;
}

.form-group {
  margin-bottom: 16px;
  
  label { display: block; font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: 8px; }
}

.form-textarea, .form-input {
  width: 100%;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  
  &:focus { outline: none; border-color: var(--accent-color); }
  &::placeholder { color: var(--text-muted); }
}

.form-textarea { resize: vertical; min-height: 60px; }
.form-hint { margin-top: 6px; font-size: 12px; color: var(--text-muted); line-height: 1.4; }

.advanced-options {
  margin-top: 16px;
  
  summary {
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-secondary);
    padding: 8px 0;
    user-select: none;
    &:hover { color: var(--text-primary); }
  }
  
  .advanced-content { padding-top: 12px; }
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  
  > span { font-size: 13px; color: var(--text-secondary); }
}

.footer-actions { display: flex; gap: 12px; }

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  
  &.btn-primary {
    background-color: var(--accent-color);
    color: white;
    &:hover:not(:disabled) { background-color: var(--accent-hover); }
  }
  
  &.btn-secondary {
    background-color: var(--bg-hover);
    color: var(--text-primary);
    &:hover { background-color: var(--border-color); }
  }
}
</style>
