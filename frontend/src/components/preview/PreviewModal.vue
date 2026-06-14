<script setup>
/**
 * Preview and edit modal - combines video player and subtitle editor
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useVideosStore } from '@/stores/videos'
import VideoPlayer from './VideoPlayer.vue'
import SubtitleEditor from './SubtitleEditor.vue'
import BilingualSubtitleEditor from './BilingualSubtitleEditor.vue'

const props = defineProps({
  visible: Boolean,
  videoId: String,
  initialTab: {
    type: String,
    default: 'preview' // preview, edit
  }
})

const emit = defineEmits(['close', 'saved'])

const videosStore = useVideosStore()
const activeTab = ref('preview')
const subtitleMode = ref('original') // original, translated, dual
const currentTime = ref(0)
const loading = ref(false)
const saving = ref(false)
const error = ref(null)

// Subtitle data
const originalSubtitles = ref([])
const translatedSubtitles = ref([])
const editingType = ref('original') // which subtitle is being edited

// Component refs
const playerRef = ref(null)
const editorRef = ref(null)

const video = computed(() => videosStore.currentVideo)

// Combined subtitles for player display
const playerSubtitles = computed(() => {
  return originalSubtitles.value.map((sub, i) => ({
    ...sub,
    original: sub.original || sub.text,
    translated: translatedSubtitles.value[i]?.original || translatedSubtitles.value[i]?.text || ''
  }))
})

// Current editing subtitles
const editingSubtitles = computed(() => {
  return editingType.value === 'original' ? originalSubtitles.value : translatedSubtitles.value
})

// Video source URL
const videoSrc = computed(() => {
  if (!video.value?.id) return ''
  return `/api/v1/videos/${video.value.id}/stream`
})

// Has subtitle files
const hasOriginalSubtitle = computed(() => !!video.value?.files?.subtitle_original)
const hasTranslatedSubtitle = computed(() => !!video.value?.files?.subtitle_translated)

// Video codec compatibility
const browserCompatible = computed(() => video.value?.browser_compatible !== false)
const videoCodec = computed(() => video.value?.video_codec)

// Load video and subtitles
async function loadData() {
  if (!props.videoId) return
  
  loading.value = true
  error.value = null
  
  try {
    await videosStore.fetchVideo(props.videoId)
    
    // Load subtitles
    if (hasOriginalSubtitle.value) {
      const content = await videosStore.getFileContent(props.videoId, 'subtitle_original')
      originalSubtitles.value = parseSrt(content.content || content)
    }
    
    if (hasTranslatedSubtitle.value) {
      const content = await videosStore.getFileContent(props.videoId, 'subtitle_translated')
      translatedSubtitles.value = parseSrt(content.content || content)
    }
  } catch (e) {
    error.value = e.message || '加载失败'
    console.error('Failed to load preview data:', e)
  } finally {
    loading.value = false
  }
}

// Parse SRT content to array
function parseSrt(content) {
  if (!content) return []
  
  const subtitles = []
  const blocks = content.trim().split(/\n\n+/)
  
  for (const block of blocks) {
    const lines = block.split('\n')
    if (lines.length < 2) continue
    
    // Parse index
    const index = parseInt(lines[0])
    if (isNaN(index)) continue
    
    // Parse time
    const timeMatch = lines[1].match(/(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})/)
    if (!timeMatch) continue
    
    const start = parseSrtTime(timeMatch[1])
    const end = parseSrtTime(timeMatch[2])
    
    // Parse text (remaining lines)
    const text = lines.slice(2).join('\n')
    
    subtitles.push({
      index,
      start,
      end,
      original: text,
      text
    })
  }
  
  return subtitles
}

// Parse SRT time string to seconds
function parseSrtTime(timeStr) {
  const match = timeStr.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})/)
  if (!match) return 0
  const [, h, m, s, ms] = match.map(Number)
  return h * 3600 + m * 60 + s + ms / 1000
}

// Convert subtitles array to SRT string
function toSrtString(subtitles) {
  return subtitles.map((sub, i) => {
    const start = formatSrtTime(sub.start)
    const end = formatSrtTime(sub.end)
    const text = sub.original || sub.text || ''
    return `${i + 1}\n${start} --> ${end}\n${text}`
  }).join('\n\n')
}

// Format seconds to SRT time
function formatSrtTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`
}

// Handle time update from player
function onTimeUpdate(time) {
  currentTime.value = time
}

// Handle seek from editor
function onSeek(time) {
  if (playerRef.value) {
    playerRef.value.seek(time)
  }
}

// Handle subtitle update from editor
function onSubtitleUpdate(subtitles) {
  if (editingType.value === 'original') {
    originalSubtitles.value = subtitles
  } else {
    translatedSubtitles.value = subtitles
  }
}

// Handle original subtitle update from bilingual editor
function onOriginalUpdate(subtitles) {
  originalSubtitles.value = subtitles
}

// Handle translated subtitle update from bilingual editor
function onTranslatedUpdate(subtitles) {
  translatedSubtitles.value = subtitles
}

// Save subtitles
async function saveSubtitles(subtitles) {
  saving.value = true
  error.value = null
  
  try {
    const fileType = editingType.value === 'original' ? 'subtitle_original' : 'subtitle_translated'
    const content = toSrtString(subtitles)
    
    await videosStore.saveFileContent(props.videoId, fileType, content)
    
    emit('saved', { type: fileType })
  } catch (e) {
    error.value = e.message || '保存失败'
    console.error('Failed to save subtitles:', e)
  } finally {
    saving.value = false
  }
}

// Save bilingual subtitles (both original and translated)
async function saveBilingualSubtitles({ original, translated }) {
  saving.value = true
  error.value = null
  
  try {
    // Save original subtitles
    if (original && original.length > 0) {
      const origContent = toSrtString(original)
      await videosStore.saveFileContent(props.videoId, 'subtitle_original', origContent)
    }
    
    // Save translated subtitles
    if (translated && translated.length > 0) {
      const transContent = toSrtString(translated)
      await videosStore.saveFileContent(props.videoId, 'subtitle_translated', transContent)
    }
    
    // Update local state
    originalSubtitles.value = original
    translatedSubtitles.value = translated
    
    emit('saved', { type: 'bilingual' })
  } catch (e) {
    error.value = e.message || '保存失败'
    console.error('Failed to save bilingual subtitles:', e)
  } finally {
    saving.value = false
  }
}

// Close modal
function handleClose() {
  // Check for unsaved changes
  if (editorRef.value?.hasChanges) {
    if (!confirm('有未保存的更改，确定关闭吗？')) {
      return
    }
  }
  emit('close')
}

// Watch for visibility and videoId changes
watch(() => [props.visible, props.videoId], ([visible, id]) => {
  if (visible && id) {
    activeTab.value = props.initialTab
    loadData()
  }
}, { immediate: true })

watch(() => props.visible, (visible) => {
  if (!visible) {
    // Reset state
    originalSubtitles.value = []
    translatedSubtitles.value = []
    currentTime.value = 0
    error.value = null
  }
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="preview-modal">
        <!-- Header -->
        <div class="modal-header">
          <h3>{{ video?.title || '预览与编辑' }}</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <!-- Loading state -->
        <div v-if="loading" class="modal-loading">
          <span class="spinner"></span>
          加载中...
        </div>
        
        <!-- Error state -->
        <div v-else-if="error" class="modal-error">
          <p>{{ error }}</p>
          <button @click="loadData">重试</button>
        </div>
        
        <!-- Content -->
        <template v-else-if="video">
          <!-- Tabs -->
          <div class="modal-tabs">
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'preview' }"
              @click="activeTab = 'preview'"
            >
              🎬 视频预览
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'edit' }"
              @click="activeTab = 'edit'"
            >
              ✏️ 字幕编辑
            </button>
          </div>
          
          <!-- Preview Tab -->
          <div v-show="activeTab === 'preview'" class="tab-content preview-content">
            <div class="preview-layout">
              <!-- Video player -->
              <div class="player-section">
                <VideoPlayer
                  ref="playerRef"
                  :src="videoSrc"
                  :subtitles="playerSubtitles"
                  :subtitle-mode="subtitleMode"
                  :current-time="currentTime"
                  :browser-compatible="browserCompatible"
                  :video-codec="videoCodec"
                  @timeupdate="onTimeUpdate"
                />
                
                <!-- Subtitle mode selector -->
                <div class="subtitle-controls">
                  <span class="control-label">字幕显示:</span>
                  <div class="mode-buttons">
                    <button 
                      class="mode-btn"
                      :class="{ active: subtitleMode === 'original' }"
                      :disabled="!hasOriginalSubtitle"
                      @click="subtitleMode = 'original'"
                    >
                      原文
                    </button>
                    <button 
                      class="mode-btn"
                      :class="{ active: subtitleMode === 'translated' }"
                      :disabled="!hasTranslatedSubtitle"
                      @click="subtitleMode = 'translated'"
                    >
                      译文
                    </button>
                    <button 
                      class="mode-btn"
                      :class="{ active: subtitleMode === 'dual' }"
                      :disabled="!hasOriginalSubtitle || !hasTranslatedSubtitle"
                      @click="subtitleMode = 'dual'"
                    >
                      双语
                    </button>
                    <button 
                      class="mode-btn"
                      :class="{ active: subtitleMode === 'none' }"
                      @click="subtitleMode = 'none'"
                    >
                      关闭
                    </button>
                  </div>
                </div>
              </div>
              
              <!-- Subtitle list (read-only) -->
              <div class="subtitle-preview">
                <h4>字幕列表</h4>
                <SubtitleEditor
                  :subtitles="playerSubtitles"
                  :current-time="currentTime"
                  :readonly="true"
                  @seek="onSeek"
                />
              </div>
            </div>
          </div>
          
          <!-- Edit Tab -->
          <div v-show="activeTab === 'edit'" class="tab-content edit-content">
            <div class="edit-layout">
              <!-- Mini player -->
              <div class="mini-player">
                <VideoPlayer
                  ref="playerRef"
                  :src="videoSrc"
                  :subtitles="playerSubtitles"
                  :subtitle-mode="subtitleMode"
                  :current-time="currentTime"
                  :browser-compatible="browserCompatible"
                  :video-codec="videoCodec"
                  @timeupdate="onTimeUpdate"
                />
              </div>
              
              <!-- Bilingual Editor section -->
              <div class="editor-section">
                <BilingualSubtitleEditor
                  ref="editorRef"
                  :original-subtitles="originalSubtitles"
                  :translated-subtitles="translatedSubtitles"
                  :current-time="currentTime"
                  @update:original="onOriginalUpdate"
                  @update:translated="onTranslatedUpdate"
                  @seek="onSeek"
                  @save="saveBilingualSubtitles"
                />
              </div>
            </div>
          </div>
        </template>
        
        <!-- Footer -->
        <div class="modal-footer">
          <div class="footer-info">
            <span v-if="saving" class="saving-indicator">
              <span class="spinner small"></span> 保存中...
            </span>
          </div>
          <button class="btn btn-secondary" @click="handleClose">关闭</button>
        </div>
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

.preview-modal {
  background-color: var(--bg-secondary);
  border-radius: 12px;
  width: 95%;
  max-width: 1200px;
  height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
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

.modal-error {
  color: var(--error);
  
  button {
    padding: 8px 16px;
    background-color: var(--accent-color);
    border: none;
    border-radius: 6px;
    color: white;
    cursor: pointer;
  }
}

.spinner {
  display: inline-block;
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  
  &.small {
    width: 14px;
    height: 14px;
    border-width: 2px;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
    color: white;
  }
}

.tab-content {
  flex: 1;
  overflow: hidden;
  padding: 16px;
}

// Preview layout
.preview-layout {
  display: grid;
  grid-template-columns: 1fr 350px;
  gap: 16px;
  height: 100%;
}

.player-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.subtitle-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
}

.control-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.mode-buttons {
  display: flex;
  gap: 4px;
}

.mode-btn {
  padding: 6px 12px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    background-color: var(--border-color);
  }
  
  &.active {
    background-color: var(--accent-color);
    color: white;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.subtitle-preview {
  display: flex;
  flex-direction: column;
  background-color: var(--bg-primary);
  border-radius: 8px;
  overflow: hidden;
  
  h4 {
    margin: 0;
    padding: 12px 16px;
    font-size: 14px;
    color: var(--text-primary);
    border-bottom: 1px solid var(--border-color);
  }
}

// Edit layout
.edit-layout {
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 16px;
  height: 100%;
}

.mini-player {
  height: fit-content;
}

.editor-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.edit-type-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
}

.selector-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.type-btn {
  padding: 6px 14px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    background-color: var(--border-color);
  }
  
  &.active {
    background-color: var(--accent-color);
    color: white;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-top: 1px solid var(--border-color);
}

.footer-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.saving-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &.btn-secondary {
    background-color: var(--bg-hover);
    color: var(--text-primary);
    
    &:hover {
      background-color: var(--border-color);
    }
  }
}

// Responsive
@media (max-width: 900px) {
  .preview-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
  
  .edit-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
  
  .mini-player {
    max-height: 250px;
  }
}
</style>
