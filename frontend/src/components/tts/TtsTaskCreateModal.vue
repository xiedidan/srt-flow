<script setup>
/**
 * TTS Task Create Modal
 * Multi-step workflow:
 * 1. Select videos
 * 2. Sentence merge preview (if enabled)
 * 3. Confirm and submit
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useVideosStore } from '@/stores/videos'
import { useTasksStore } from '@/stores/tasks'
import api from '@/api'
import { listReferenceAudios, getAudioStreamUrl } from '@/api/referenceAudio'
import { previewSentenceMerge } from '@/api/tts'
import SentenceMergeEditor from './SentenceMergeEditor.vue'

const emit = defineEmits(['close', 'created'])

const videosStore = useVideosStore()
const tasksStore = useTasksStore()

// Current step: 1 = select videos, 2 = sentence merge, 3 = confirm (skipped if no merge)
const currentStep = ref(1)

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

// TTS options
const engine = ref('chattts')
const speaker = ref('')
const outputFormat = ref('m4a')
const useGpu = ref(true)
const minSpeed = ref(0.5)
const maxSpeed = ref(2.0)
const enableTimeStretch = ref(true)

// Sentence merge state
const enableSentenceMerge = ref(false)
const sentenceMergeConfigured = ref(false)
const loadingMergePreview = ref(false)
const mergePreviewError = ref('')
const originalEntries = ref([])
const mergedEntries = ref([])

// Reference audio state
const referenceAudios = ref([])
const selectedReferenceAudioId = ref('')
const loadingReferenceAudios = ref(false)
const playingAudioId = ref(null)
const audioElement = ref(null)

// Loading state
const loadingConfig = ref(true)
const submitting = ref(false)

// TTS engine options
const engineOptions = [
  { value: 'chattts', label: 'ChatTTS (推荐)', description: '自然度高，支持情感', supportsCloning: false },
  { value: 'coqui', label: 'Coqui TTS', description: '开源，多语言支持', supportsCloning: true },
  { value: 'sparktts', label: 'SparkTTS', description: '讯飞开源，中文优秀', supportsCloning: true },
  { value: 'indextts', label: 'IndexTTS', description: '零样本克隆', supportsCloning: true },
  { value: 'cozyvoice', label: 'CozyVoice', description: '阿里开源，多风格', supportsCloning: true },
  { value: 'vits', label: 'VITS', description: '轻量快速', supportsCloning: false }
]

// Output format options
const formatOptions = [
  { value: 'm4a', label: 'M4A (AAC)', description: '推荐，体积小' },
  { value: 'mp3', label: 'MP3', description: '兼容性好' },
  { value: 'wav', label: 'WAV', description: '无损，体积大' }
]

// All available tags from videos store
const allTags = computed(() => videosStore.allTags)

// Check if current engine supports voice cloning
const currentEngineSupportsCloning = computed(() => {
  const engineOpt = engineOptions.find(e => e.value === engine.value)
  return engineOpt?.supportsCloning ?? false
})

// Get selected reference audio object
const selectedReferenceAudio = computed(() => {
  if (!selectedReferenceAudioId.value) return null
  return referenceAudios.value.find(a => a.id === selectedReferenceAudioId.value)
})

// Selected count for display
const selectedCount = computed(() => {
  if (selectionMode.value === 'search') {
    return selectedVideos.value.length
  } else {
    return tagVideos.value.filter(v => v.selected).length
  }
})

// Get videos to process
const videosToProcess = computed(() => {
  if (selectionMode.value === 'search') {
    return selectedVideos.value
  } else {
    return tagVideos.value.filter(v => v.selected)
  }
})

// Can proceed to next step
const canProceed = computed(() => {
  if (currentStep.value === 1) {
    return selectedCount.value > 0
  }
  if (currentStep.value === 2) {
    return mergedEntries.value.length > 0
  }
  return true
})

// Can submit
const canSubmit = computed(() => selectedCount.value > 0 && !submitting.value)

// Show sentence merge step (only for single video and merge enabled)
const showMergeStep = computed(() => {
  return enableSentenceMerge.value && sentenceMergeConfigured.value && selectedCount.value === 1
})

// Load TTS config
async function loadTtsConfig() {
  loadingConfig.value = true
  try {
    const res = await api.get('/config/tts')
    if (res.data) {
      if (res.data.engine) engine.value = res.data.engine
      if (res.data.speaker) speaker.value = res.data.speaker
      if (res.data.output_format) outputFormat.value = res.data.output_format
      if (res.data.use_gpu !== undefined) useGpu.value = res.data.use_gpu
      if (res.data.min_speed !== undefined) minSpeed.value = res.data.min_speed
      if (res.data.max_speed !== undefined) maxSpeed.value = res.data.max_speed
      if (res.data.enable_time_stretch !== undefined) enableTimeStretch.value = res.data.enable_time_stretch
      // Sentence merge settings
      if (res.data.enable_sentence_merge !== undefined) enableSentenceMerge.value = res.data.enable_sentence_merge
      if (res.data.sentence_merge_provider_id) sentenceMergeConfigured.value = true
    }
  } catch (e) {
    console.error('Failed to load TTS config:', e)
  } finally {
    loadingConfig.value = false
  }
}

// Load reference audios
async function loadReferenceAudios() {
  loadingReferenceAudios.value = true
  try {
    referenceAudios.value = await listReferenceAudios()
  } catch (e) {
    console.error('Failed to load reference audios:', e)
  } finally {
    loadingReferenceAudios.value = false
  }
}

// Format duration for display
function formatDuration(seconds) {
  if (!seconds) return '--:--'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// Toggle audio playback
function toggleAudioPlay(audio) {
  if (playingAudioId.value === audio.id) {
    if (audioElement.value) {
      audioElement.value.pause()
      audioElement.value = null
    }
    playingAudioId.value = null
  } else {
    if (audioElement.value) {
      audioElement.value.pause()
    }
    const url = getAudioStreamUrl(audio.id)
    audioElement.value = new Audio(url)
    audioElement.value.play()
    playingAudioId.value = audio.id
    audioElement.value.onended = () => {
      playingAudioId.value = null
      audioElement.value = null
    }
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
    searchResults.value = videosStore.videos
      .filter(v => v.files?.subtitle_translated)
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
      .filter(v => v.files?.subtitle_translated)
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

// Load sentence merge preview
async function loadMergePreview() {
  if (videosToProcess.value.length !== 1) return
  
  const video = videosToProcess.value[0]
  loadingMergePreview.value = true
  mergePreviewError.value = ''
  
  try {
    const result = await previewSentenceMerge(video.id)
    originalEntries.value = result.original_entries
    mergedEntries.value = result.merged_entries
  } catch (e) {
    console.error('Failed to load merge preview:', e)
    mergePreviewError.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loadingMergePreview.value = false
  }
}

// Handle merged entries update from editor
function handleMergedEntriesUpdate(entries) {
  mergedEntries.value = entries
}

// Regenerate merge preview
async function regenerateMergePreview() {
  await loadMergePreview()
}

// Go to next step
async function nextStep() {
  if (currentStep.value === 1) {
    if (showMergeStep.value) {
      currentStep.value = 2
      await loadMergePreview()
    } else {
      // Skip merge step, submit directly
      await handleSubmit()
    }
  } else if (currentStep.value === 2) {
    await handleSubmit()
  }
}

// Go to previous step
function prevStep() {
  if (currentStep.value > 1) {
    currentStep.value--
    // Reset merge state when going back
    if (currentStep.value === 1) {
      originalEntries.value = []
      mergedEntries.value = []
      mergePreviewError.value = ''
    }
  }
}

// Submit tasks
async function handleSubmit() {
  if (!canSubmit.value) return
  
  submitting.value = true
  try {
    let speakerValue = speaker.value || null
    if (selectedReferenceAudio.value && currentEngineSupportsCloning.value) {
      speakerValue = `ref:${selectedReferenceAudio.value.id}`
    }
    
    // Create tasks for each video
    for (const video of videosToProcess.value) {
      const payload = {
        video_id: video.id,
        subtitle_path: video.files?.subtitle_translated,
        engine: engine.value,
        speaker: speakerValue,
        reference_audio_id: selectedReferenceAudio.value?.id || null,
        output_format: outputFormat.value,
        use_gpu: useGpu.value,
        min_speed: minSpeed.value,
        max_speed: maxSpeed.value,
        enable_time_stretch: enableTimeStretch.value
      }
      
      // Include merged entries if available (single video with merge)
      if (showMergeStep.value && mergedEntries.value.length > 0) {
        payload.merged_entries = mergedEntries.value
        payload.skip_ai_merge = true // Tell backend to use provided entries
      }
      
      await tasksStore.createTask({ type: 'tts', payload })
    }
    
    emit('created', videosToProcess.value.length)
    emit('close')
  } catch (e) {
    console.error('Failed to create TTS tasks:', e)
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('close')
}

// Load initial data
onMounted(() => {
  loadTtsConfig()
  loadReferenceAudios()
  videosStore.fetchVideos({ page_size: 100 })
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="handleClose">
      <div class="modal-container" :class="{ 'wide': currentStep === 2 }">
        <div class="modal-header">
          <h3>🔊 新建语音合成任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <!-- Step Indicator -->
        <div v-if="showMergeStep" class="step-indicator">
          <div class="step" :class="{ active: currentStep === 1, done: currentStep > 1 }">
            <span class="step-num">1</span>
            <span class="step-label">选择视频</span>
          </div>
          <div class="step-line" :class="{ done: currentStep > 1 }"></div>
          <div class="step" :class="{ active: currentStep === 2 }">
            <span class="step-num">2</span>
            <span class="step-label">句子合并</span>
          </div>
        </div>
        
        <div class="modal-body">
          <!-- Step 1: Video Selection -->
          <div v-show="currentStep === 1">
            <!-- Selection Mode Tabs -->
            <div class="mode-tabs">
              <button :class="{ active: selectionMode === 'search' }" @click="selectionMode = 'search'">
                🔍 搜索视频
              </button>
              <button :class="{ active: selectionMode === 'tag' }" @click="selectionMode = 'tag'">
                🏷️ 按标签选择
              </button>
            </div>

            <div class="info-hint">
              <span class="hint-icon">💡</span>
              <span>仅显示已完成翻译的视频（有翻译字幕）</span>
            </div>

            <!-- Search Mode -->
            <div v-if="selectionMode === 'search'" class="search-section">
              <div class="search-input-wrapper">
                <input v-model="searchKeyword" type="text" class="search-input" placeholder="输入视频标题搜索..." />
                <span v-if="searching" class="search-loading">搜索中...</span>
              </div>
              
              <div v-if="searchResults.length > 0" class="video-list search-results">
                <div v-for="video in searchResults" :key="video.id" class="video-item"
                  :class="{ selected: video.selected }" @click="toggleVideoSelect(video)">
                  <div class="video-checkbox">
                    <input type="checkbox" :checked="video.selected" @click.stop />
                  </div>
                  <img v-if="video.thumbnail" :src="video.thumbnail" class="video-thumb" alt="" />
                  <div class="video-thumb placeholder" v-else>🎬</div>
                  <div class="video-info">
                    <div class="video-title">{{ video.title }}</div>
                    <div class="video-meta">
                      <span v-if="video.duration">{{ Math.floor(video.duration / 60) }}:{{ String(Math.floor(video.duration % 60)).padStart(2, '0') }}</span>
                      <span class="has-subtitle">✓ 已翻译</span>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else-if="searchKeyword && !searching" class="empty-hint">未找到已翻译的视频</div>

              <div v-if="selectedVideos.length > 0" class="selected-section">
                <div class="section-title">已选择 {{ selectedVideos.length }} 个视频</div>
                <div class="selected-list">
                  <div v-for="video in selectedVideos" :key="video.id" class="selected-chip">
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
                  <option v-for="tag in allTags" :key="tag" :value="tag">{{ tag }}</option>
                </select>
              </div>

              <div v-if="loadingTagVideos" class="loading-hint">加载中...</div>
              
              <div v-else-if="tagVideos.length > 0" class="tag-videos">
                <div class="tag-videos-header">
                  <span>共 {{ tagVideos.length }} 个已翻译视频</span>
                  <button class="select-all-btn" @click="toggleAllTagVideos">
                    {{ tagVideos.every(v => v.selected) ? '取消全选' : '全选' }}
                  </button>
                </div>
                <div class="video-list">
                  <div v-for="video in tagVideos" :key="video.id" class="video-item"
                    :class="{ selected: video.selected }" @click="video.selected = !video.selected">
                    <div class="video-checkbox">
                      <input type="checkbox" :checked="video.selected" @click.stop />
                    </div>
                    <img v-if="video.thumbnail" :src="video.thumbnail" class="video-thumb" alt="" />
                    <div class="video-thumb placeholder" v-else>🎬</div>
                    <div class="video-info">
                      <div class="video-title">{{ video.title }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else-if="selectedTag" class="empty-hint">该标签下没有已翻译的视频</div>
            </div>

            <!-- TTS Options -->
            <div class="options-section">
              <div class="section-title">合成选项</div>
              <div class="options-grid">
                <div class="form-group">
                  <label>TTS 引擎</label>
                  <select v-model="engine" class="form-select" :disabled="loadingConfig">
                    <option v-for="opt in engineOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                  <p class="form-hint">{{ engineOptions.find(e => e.value === engine)?.description }}</p>
                </div>
                <div class="form-group">
                  <label>输出格式</label>
                  <select v-model="outputFormat" class="form-select" :disabled="loadingConfig">
                    <option v-for="opt in formatOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label>说话人/音色（可选）</label>
                <input v-model="speaker" type="text" class="form-input" placeholder="留空使用默认音色"
                  :disabled="loadingConfig || (selectedReferenceAudioId && currentEngineSupportsCloning)" />
                <p v-if="selectedReferenceAudioId && currentEngineSupportsCloning" class="form-hint">
                  已选择参考音频，将使用音色克隆
                </p>
              </div>

              <!-- Reference Audio Selection -->
              <div v-if="currentEngineSupportsCloning" class="form-group reference-audio-section">
                <label>🎵 参考音频（音色克隆）<span class="optional-badge">可选</span></label>
                <p class="form-hint">选择参考音频后，TTS 将模仿该音色进行语音合成</p>
                
                <div v-if="loadingReferenceAudios" class="loading-hint">加载参考音频...</div>
                
                <div v-else-if="referenceAudios.length === 0" class="empty-audio-hint">
                  <span>暂无参考音频</span>
                  <router-link to="/settings/reference-audio" class="link-btn" @click="$emit('close')">去上传 →</router-link>
                </div>
                
                <div v-else class="reference-audio-list">
                  <div class="audio-option" :class="{ selected: !selectedReferenceAudioId }" @click="selectedReferenceAudioId = ''">
                    <div class="audio-radio"><input type="radio" :checked="!selectedReferenceAudioId" name="refAudio" /></div>
                    <div class="audio-info">
                      <div class="audio-name">不使用参考音频</div>
                      <div class="audio-desc">使用引擎默认音色</div>
                    </div>
                  </div>
                  
                  <div v-for="audio in referenceAudios" :key="audio.id" class="audio-option"
                    :class="{ selected: selectedReferenceAudioId === audio.id }" @click="selectedReferenceAudioId = audio.id">
                    <div class="audio-radio"><input type="radio" :checked="selectedReferenceAudioId === audio.id" name="refAudio" /></div>
                    <div class="audio-info">
                      <div class="audio-name">{{ audio.original_filename }}</div>
                      <div class="audio-meta">
                        <span>⏱️ {{ formatDuration(audio.duration) }}</span>
                        <span v-if="audio.description" class="audio-desc-text">{{ audio.description }}</span>
                      </div>
                    </div>
                    <button class="play-btn" :class="{ playing: playingAudioId === audio.id }"
                      @click.stop="toggleAudioPlay(audio)" :title="playingAudioId === audio.id ? '停止' : '试听'">
                      {{ playingAudioId === audio.id ? '⏹️' : '▶️' }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- Advanced Options -->
              <details class="advanced-options">
                <summary>高级选项</summary>
                <div class="advanced-content">
                  <div class="form-group checkbox-group">
                    <label><input type="checkbox" v-model="useGpu" :disabled="loadingConfig" /> 使用 GPU 加速</label>
                  </div>
                  <div class="form-group checkbox-group">
                    <label><input type="checkbox" v-model="enableTimeStretch" :disabled="loadingConfig" /> 启用时间拉伸调整</label>
                    <p class="form-hint">当语速调整无法匹配时长时，使用音频拉伸微调</p>
                  </div>
                  <div class="speed-range">
                    <div class="form-group">
                      <label>语速下限（慢速）</label>
                      <input v-model.number="minSpeed" type="number" class="form-input" min="0.1" max="1.0" step="0.1" :disabled="loadingConfig" />
                      <p class="form-hint">0.5 = 正常语速的一半（更慢）</p>
                    </div>
                    <div class="form-group">
                      <label>语速上限（快速）</label>
                      <input v-model.number="maxSpeed" type="number" class="form-input" min="1.0" max="3.0" step="0.1" :disabled="loadingConfig" />
                      <p class="form-hint">2.0 = 正常语速的两倍（更快）</p>
                    </div>
                  </div>
                </div>
              </details>

              <!-- Sentence Merge Info -->
              <div v-if="enableSentenceMerge && sentenceMergeConfigured && selectedCount === 1" class="merge-info">
                <span class="merge-icon">✨</span>
                <span>已启用 AI 句子合并，下一步将预览合并结果</span>
              </div>
              <div v-else-if="enableSentenceMerge && selectedCount > 1" class="merge-info warning">
                <span class="merge-icon">⚠️</span>
                <span>批量任务不支持句子合并预览，将自动执行合并</span>
              </div>
            </div>
          </div>

          <!-- Step 2: Sentence Merge Preview -->
          <div v-show="currentStep === 2" class="merge-step">
            <div class="merge-header">
              <h4>📝 句子合并预览</h4>
              <p class="merge-desc">AI 已将分散的字幕片段合并为完整句子，您可以手动调整合并结果</p>
            </div>
            
            <div v-if="mergePreviewError" class="merge-error">
              <span class="error-icon">❌</span>
              <span>{{ mergePreviewError }}</span>
              <button class="retry-btn" @click="loadMergePreview">重试</button>
            </div>
            
            <SentenceMergeEditor
              v-else
              :original-entries="originalEntries"
              :merged-entries="mergedEntries"
              :loading="loadingMergePreview"
              @update:merged-entries="handleMergedEntriesUpdate"
              @regenerate="regenerateMergePreview"
            />
          </div>
        </div>
        
        <div class="modal-footer">
          <div class="footer-info">
            <span v-if="currentStep === 1 && selectedCount > 0">将创建 {{ selectedCount }} 个语音合成任务</span>
            <span v-if="currentStep === 2">合并后共 {{ mergedEntries.length }} 条字幕</span>
          </div>
          <div class="footer-actions">
            <button v-if="currentStep > 1" class="btn btn-secondary" @click="prevStep">上一步</button>
            <button v-else class="btn btn-secondary" @click="handleClose">取消</button>
            <button class="btn btn-primary" :disabled="!canProceed || submitting" @click="nextStep">
              {{ submitting ? '创建中...' : (currentStep === 1 && showMergeStep ? '下一步' : '创建任务') }}
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
  
  &.wide {
    max-width: 800px;
  }
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

.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  
  .step {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .step-num {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background-color: var(--bg-primary);
      border: 2px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
    }
    
    .step-label {
      font-size: 13px;
      color: var(--text-muted);
    }
    
    &.active {
      .step-num { border-color: var(--accent-color); background-color: var(--accent-color); color: white; }
      .step-label { color: var(--text-primary); font-weight: 500; }
    }
    
    &.done {
      .step-num { border-color: var(--success, #22c55e); background-color: var(--success, #22c55e); color: white; }
      .step-label { color: var(--success, #22c55e); }
    }
  }
  
  .step-line {
    width: 60px;
    height: 2px;
    background-color: var(--border-color);
    margin: 0 12px;
    
    &.done { background-color: var(--success, #22c55e); }
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

.search-section, .tag-section { margin-bottom: 20px; }

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
  
  &:focus { outline: none; border-color: var(--accent-color); }
  &::placeholder { color: var(--text-muted); }
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
  
  &.search-results { margin-bottom: 16px; }
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

.video-checkbox input { width: 16px; height: 16px; accent-color: var(--accent-color); }

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
.video-meta .has-subtitle { color: var(--success, #22c55e); }

.selected-section { margin-top: 16px; }
.section-title { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-bottom: 8px; }
.selected-list { display: flex; flex-wrap: wrap; gap: 8px; }

.selected-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  font-size: 12px;
  
  .chip-title { max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-primary); }
  .chip-remove { background: none; border: none; color: var(--text-muted); font-size: 12px; cursor: pointer; padding: 0; line-height: 1; &:hover { color: var(--error); } }
}

.form-group {
  margin-bottom: 16px;
  label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 6px; }
}

.form-select, .form-input {
  width: 100%;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  
  &:focus { outline: none; border-color: var(--accent-color); }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.form-hint { margin-top: 4px; font-size: 11px; color: var(--text-muted); }

.tag-videos-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  span { font-size: 13px; color: var(--text-secondary); }
}

.select-all-btn {
  padding: 4px 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  &:hover { border-color: var(--accent-color); color: var(--accent-color); }
}

.loading-hint, .empty-hint { text-align: center; padding: 24px; color: var(--text-muted); font-size: 14px; }

.options-section { padding-top: 16px; border-top: 1px solid var(--border-color); }
.options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.advanced-options {
  margin-top: 16px;
  summary { cursor: pointer; font-size: 13px; color: var(--text-secondary); padding: 8px 0; &:hover { color: var(--accent-color); } }
}

.advanced-content { padding: 16px; background-color: var(--bg-primary); border-radius: 8px; margin-top: 8px; }
.checkbox-group label { display: flex; align-items: center; gap: 8px; cursor: pointer; input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--accent-color); } }
.speed-range { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }

.reference-audio-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  label { display: flex; align-items: center; gap: 8px; }
  .optional-badge { font-size: 11px; padding: 2px 6px; background-color: var(--bg-hover); border-radius: 4px; color: var(--text-muted); font-weight: normal; }
}

.empty-audio-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  .link-btn { color: var(--accent-color); text-decoration: none; &:hover { text-decoration: underline; } }
}

.reference-audio-list { display: flex; flex-direction: column; gap: 8px; max-height: 200px; overflow-y: auto; margin-top: 8px; }

.audio-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover { border-color: var(--accent-color); }
  &.selected { border-color: var(--accent-color); background-color: rgba(59, 130, 246, 0.1); }
  
  .audio-radio input { width: 16px; height: 16px; accent-color: var(--accent-color); }
  .audio-info { flex: 1; min-width: 0; }
  .audio-name { font-size: 13px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .audio-desc { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .audio-meta { display: flex; gap: 12px; font-size: 11px; color: var(--text-muted); margin-top: 4px; }
  
  .play-btn {
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 6px;
    background-color: var(--bg-secondary);
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
    &:hover { background-color: var(--accent-color); }
    &.playing { background-color: var(--accent-color); animation: pulse 1s infinite; }
  }
}

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }

.merge-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 12px 16px;
  background-color: rgba(34, 197, 94, 0.1);
  border-radius: 8px;
  font-size: 13px;
  color: var(--success, #22c55e);
  
  &.warning { background-color: rgba(234, 179, 8, 0.1); color: var(--warning, #eab308); }
  .merge-icon { font-size: 16px; }
}

.merge-step {
  .merge-header {
    margin-bottom: 16px;
    h4 { margin: 0 0 8px 0; font-size: 16px; color: var(--text-primary); }
    .merge-desc { font-size: 13px; color: var(--text-muted); margin: 0; }
  }
  
  .merge-error {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background-color: rgba(239, 68, 68, 0.1);
    border-radius: 8px;
    color: var(--error, #ef4444);
    font-size: 13px;
    
    .error-icon { font-size: 18px; }
    .retry-btn {
      margin-left: auto;
      padding: 6px 12px;
      background-color: transparent;
      border: 1px solid currentColor;
      border-radius: 4px;
      color: inherit;
      font-size: 12px;
      cursor: pointer;
      &:hover { background-color: rgba(239, 68, 68, 0.1); }
    }
  }
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.footer-info { font-size: 13px; color: var(--text-secondary); }
.footer-actions { display: flex; gap: 12px; }

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  &.btn-primary { background-color: var(--accent-color); color: white; &:hover:not(:disabled) { background-color: var(--accent-hover); } }
  &.btn-secondary { background-color: var(--bg-hover); color: var(--text-primary); &:hover { background-color: var(--border-color); } }
}
</style>
