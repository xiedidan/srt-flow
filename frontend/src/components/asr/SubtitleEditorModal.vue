<script setup>
/**
 * Subtitle Editor Modal for ASR/Translation tasks
 * - ASR tasks: Single subtitle editor
 * - Translation tasks: Bilingual editor with original + translated
 */
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import SubtitleEditor from '@/components/preview/SubtitleEditor.vue'
import BilingualSubtitleEditor from '@/components/preview/BilingualSubtitleEditor.vue'
import VideoPlayer from '@/components/preview/VideoPlayer.vue'

const props = defineProps({
  task: {
    type: Object,
    required: true
  },
  subtitleType: {
    type: String,
    default: 'original' // 'original' | 'translated'
  }
})

const emit = defineEmits(['close', 'saved'])

const loading = ref(true)
const saving = ref(false)
const error = ref(null)
const subtitles = ref([])
const originalSubtitles = ref([])
const video = ref(null)
const videoUrl = ref('')
const currentTime = ref(0)
const videoPlayerRef = ref(null)
const subtitleEditorRef = ref(null)
const bilingualEditorRef = ref(null)

// Subtitle display mode
const subtitleMode = ref('original')

// Video codec compatibility
const browserCompatible = computed(() => video.value?.browser_compatible !== false)
const videoCodec = computed(() => video.value?.video_codec)

// Whether this is a translation task (for bilingual support)
const isTranslationTask = computed(() => props.subtitleType === 'translated')

// Available subtitle modes based on task type
const availableSubtitleModes = computed(() => {
  if (isTranslationTask.value) {
    return [
      { value: 'dual', label: '双语' },
      { value: 'translated', label: '译文' },
      { value: 'original', label: '原文' },
      { value: 'none', label: '隐藏' }
    ]
  }
  return [
    { value: 'original', label: '显示' },
    { value: 'none', label: '隐藏' }
  ]
})

// Subtitles formatted for VideoPlayer component
const playerSubtitles = computed(() => {
  if (isTranslationTask.value && originalSubtitles.value.length > 0) {
    return subtitles.value.map(sub => {
      const translated = sub.original || sub.text
      const original = findMatchingOriginal(sub.start, sub.end)
      return {
        ...sub,
        original: original,
        translated: translated
      }
    })
  }
  return subtitles.value.map(sub => ({
    ...sub,
    original: sub.original || sub.text,
    translated: ''
  }))
})

// Find matching original subtitle by time range
function findMatchingOriginal(start, end) {
  if (!originalSubtitles.value.length) return ''
  const overlapping = originalSubtitles.value.filter(orig => {
    return orig.start < end && orig.end > start
  })
  if (overlapping.length === 0) return ''
  return overlapping.map(o => o.original || o.text).join(' ')
}

// Get video info
const videoTitle = computed(() => video.value?.title || '未知视频')

const modalTitle = computed(() =>
  props.subtitleType === 'translated' ? '📝 翻译字幕编辑' : '📝 字幕编辑'
)

// Load subtitle data
async function loadSubtitles() {
  loading.value = true
  error.value = null

  try {
    const videoId = props.task.video_id || props.task.payload?.video_id
    
    if (!videoId) {
      throw new Error('任务没有关联视频')
    }

    // Get video info
    const videoRes = await api.get(`/videos/${videoId}`)
    video.value = videoRes.data

    // Get video stream URL
    videoUrl.value = `/api/v1/videos/${videoId}/stream`

    const files = video.value?.files || {}

    // Load original subtitles
    const originalPath = files['subtitle_original']
    if (originalPath) {
      try {
        const originalRes = await api.get(`/videos/${videoId}/files/subtitle_original/content`)
        const originalContent = originalRes.data?.content
        originalSubtitles.value = parseSrt(originalContent)
      } catch (e) {
        console.warn('Failed to load original subtitles:', e)
        originalSubtitles.value = []
      }
    }

    // For translation tasks, also load translated subtitles
    if (isTranslationTask.value) {
      const translatedPath = files['subtitle_translated']
      if (translatedPath) {
        const translatedRes = await api.get(`/videos/${videoId}/files/subtitle_translated/content`)
        const translatedContent = translatedRes.data?.content
        subtitles.value = parseSrt(translatedContent)
      } else if (props.task.result?.subtitles) {
        subtitles.value = props.task.result.subtitles
      } else {
        subtitles.value = []
      }
      subtitleMode.value = 'dual'
    } else {
      // For ASR tasks, use original subtitles
      subtitles.value = [...originalSubtitles.value]
      subtitleMode.value = 'original'
    }
  } catch (e) {
    console.error('Failed to load subtitles:', e)
    error.value = e.message || '加载字幕失败'
  } finally {
    loading.value = false
  }
}

// Parse SRT format to subtitle array
function parseSrt(srtContent) {
  if (!srtContent || typeof srtContent !== 'string') return []

  const blocks = srtContent.trim().split(/\n\n+/)
  const result = []

  for (const block of blocks) {
    const lines = block.split('\n')
    if (lines.length < 3) continue

    const index = parseInt(lines[0])
    const timeMatch = lines[1].match(/(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})/)
    if (!timeMatch) continue

    const text = lines.slice(2).join('\n')

    result.push({
      index,
      start: parseSrtTime(timeMatch[1]),
      end: parseSrtTime(timeMatch[2]),
      original: text,
      text
    })
  }

  return result
}

function parseSrtTime(timeStr) {
  const match = timeStr.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})/)
  if (!match) return 0
  const [, h, m, s, ms] = match.map(Number)
  return h * 3600 + m * 60 + s + ms / 1000
}

// Handle video time update
function handleTimeUpdate(time) {
  currentTime.value = time
}

// Seek video to time
function handleSeek(time) {
  if (videoPlayerRef.value) {
    videoPlayerRef.value.seek(time)
  }
}

// Handle subtitle update (for single editor)
function handleSubtitleUpdate(newSubtitles) {
  subtitles.value = newSubtitles
}

// Handle bilingual update
function handleOriginalUpdate(newOriginal) {
  originalSubtitles.value = newOriginal
}

function handleTranslatedUpdate(newTranslated) {
  subtitles.value = newTranslated
}

// Save subtitles (single editor)
async function handleSave(newSubtitles) {
  saving.value = true

  try {
    const videoId = props.task.video_id || props.task.payload?.video_id
    if (!videoId) throw new Error('No video ID')

    const srtContent = subtitlesToSrt(newSubtitles)
    const fileType = isTranslationTask.value ? 'subtitle_translated' : 'subtitle_original'

    await api.put(`/videos/${videoId}/files/${fileType}/content`, {
      content: srtContent
    })

    emit('saved')
  } catch (e) {
    console.error('Failed to save subtitles:', e)
    alert('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

// Save bilingual subtitles
async function handleBilingualSave({ original, translated }) {
  saving.value = true

  try {
    const videoId = props.task.video_id || props.task.payload?.video_id
    if (!videoId) throw new Error('No video ID')

    // Save original subtitles
    const originalSrt = subtitlesToSrt(original)
    await api.put(`/videos/${videoId}/files/subtitle_original/content`, {
      content: originalSrt
    })

    // Save translated subtitles
    const translatedSrt = subtitlesToSrt(translated)
    await api.put(`/videos/${videoId}/files/subtitle_translated/content`, {
      content: translatedSrt
    })

    emit('saved')
  } catch (e) {
    console.error('Failed to save subtitles:', e)
    alert('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function subtitlesToSrt(subs) {
  return subs.map((sub, i) => {
    const start = formatSrtTime(sub.start)
    const end = formatSrtTime(sub.end)
    return `${i + 1}\n${start} --> ${end}\n${sub.original || sub.text || ''}`
  }).join('\n\n')
}

function formatSrtTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`
}

function handleClose() {
  const editor = isTranslationTask.value ? bilingualEditorRef.value : subtitleEditorRef.value
  if (editor?.hasChanges) {
    if (!confirm('有未保存的更改，确定要关闭吗？')) return
  }
  emit('close')
}

onMounted(() => {
  loadSubtitles()
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>{{ modalTitle }} - {{ videoTitle }}</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>

        <div v-if="loading" class="modal-loading">
          <span class="spinner">⏳</span> 加载中...
        </div>

        <div v-else-if="error" class="modal-error">
          <span class="error-icon">❌</span>
          <p>{{ error }}</p>
          <button class="btn-retry" @click="loadSubtitles">重试</button>
        </div>

        <template v-else>
          <div class="modal-body">
            <div class="editor-layout">
              <!-- Video Player -->
              <div class="video-section">
                <VideoPlayer
                  ref="videoPlayerRef"
                  :src="videoUrl"
                  :subtitles="playerSubtitles"
                  :subtitle-mode="subtitleMode"
                  :browser-compatible="browserCompatible"
                  :video-codec="videoCodec"
                  @timeupdate="handleTimeUpdate"
                />
                <div class="video-info">
                  <span class="subtitle-count">
                    {{ isTranslationTask ? `原文 ${originalSubtitles.length} 条 / 译文 ${subtitles.length} 条` : `${subtitles.length} 条字幕` }}
                  </span>
                  <div class="subtitle-toggle">
                    <span class="toggle-label">字幕显示:</span>
                    <button 
                      v-for="mode in availableSubtitleModes"
                      :key="mode.value"
                      class="toggle-btn" 
                      :class="{ active: subtitleMode === mode.value }"
                      @click="subtitleMode = mode.value"
                    >
                      {{ mode.label }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- Subtitle Editor -->
              <div class="subtitle-section">
                <!-- Bilingual editor for translation tasks -->
                <BilingualSubtitleEditor
                  v-if="isTranslationTask"
                  ref="bilingualEditorRef"
                  :original-subtitles="originalSubtitles"
                  :translated-subtitles="subtitles"
                  :current-time="currentTime"
                  @update:original="handleOriginalUpdate"
                  @update:translated="handleTranslatedUpdate"
                  @seek="handleSeek"
                  @save="handleBilingualSave"
                />
                <!-- Single editor for ASR tasks -->
                <SubtitleEditor
                  v-else
                  ref="subtitleEditorRef"
                  :subtitles="subtitles"
                  :current-time="currentTime"
                  @update="handleSubtitleUpdate"
                  @seek="handleSeek"
                  @save="handleSave"
                />
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style lang="scss" scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background-color: var(--bg-secondary);
  border-radius: 12px;
  width: 95%;
  max-width: 1400px;
  height: 90vh;
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

.modal-loading,
.modal-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-secondary);
}

.spinner {
  font-size: 24px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: 48px;
}

.btn-retry {
  padding: 8px 20px;
  background-color: var(--accent-color);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;

  &:hover {
    background-color: var(--accent-hover);
  }
}

.modal-body {
  flex: 1;
  overflow: hidden;
  padding: 16px;
}

.editor-layout {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 16px;
  height: 100%;
}

.video-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.video-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
  flex-wrap: wrap;
  gap: 8px;
}

.subtitle-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.subtitle-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toggle-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.toggle-btn {
  padding: 4px 10px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--border-color);
  }
  
  &.active {
    background-color: var(--accent-color);
    color: white;
  }
}

.subtitle-section {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

@media (max-width: 1000px) {
  .editor-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
}
</style>
