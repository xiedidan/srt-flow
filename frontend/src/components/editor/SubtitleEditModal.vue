<script setup>
/**
 * Subtitle Edit Modal
 * Full-featured subtitle editor with video preview
 */
import { ref, computed, watch, onMounted } from 'vue'
import api from '@/api'
import SubtitleEditor from '@/components/preview/SubtitleEditor.vue'

const props = defineProps({
  videoId: {
    type: String,
    required: true
  },
  subtitleType: {
    type: String,
    default: 'original' // 'original' or 'translated'
  }
})

const emit = defineEmits(['close', 'saved'])

// State
const loading = ref(true)
const saving = ref(false)
const videoDetail = ref(null)
const subtitles = ref([])
const currentTime = ref(0)
const hasChanges = ref(false)
const error = ref(null)

// Video stream URL
const videoStreamUrl = computed(() => `/api/v1/videos/${props.videoId}/stream`)

// Subtitle file type
const fileType = computed(() => 
  props.subtitleType === 'translated' ? 'subtitle_translated' : 'subtitle_original'
)

// Parse SRT content to subtitle entries
function parseSrt(content) {
  const entries = []
  const blocks = content.trim().split(/\n\s*\n/)
  
  for (const block of blocks) {
    const lines = block.trim().split('\n')
    if (lines.length < 3) continue
    
    const index = parseInt(lines[0])
    const timeMatch = lines[1].match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})/)
    if (!timeMatch) continue
    
    const [, sh, sm, ss, sms, eh, em, es, ems] = timeMatch.map(Number)
    const start = sh * 3600 + sm * 60 + ss + sms / 1000
    const end = eh * 3600 + em * 60 + es + ems / 1000
    const text = lines.slice(2).join('\n')
    
    entries.push({ index, start, end, original: text, text })
  }
  
  return entries
}

// Generate SRT content from entries
function generateSrt(entries) {
  return entries.map((entry, i) => {
    const formatTime = (seconds) => {
      const h = Math.floor(seconds / 3600)
      const m = Math.floor((seconds % 3600) / 60)
      const s = Math.floor(seconds % 60)
      const ms = Math.round((seconds % 1) * 1000)
      return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`
    }
    
    return `${i + 1}\n${formatTime(entry.start)} --> ${formatTime(entry.end)}\n${entry.original || entry.text}`
  }).join('\n\n')
}

// Load video and subtitle data
async function loadData() {
  loading.value = true
  error.value = null
  
  try {
    // Load video detail
    const videoRes = await api.get(`/videos/${props.videoId}`)
    videoDetail.value = videoRes.data
    
    // Load subtitle content
    const subRes = await api.get(`/videos/${props.videoId}/files/${fileType.value}/content`)
    if (subRes.data?.content) {
      subtitles.value = parseSrt(subRes.data.content)
    }
  } catch (e) {
    console.error('Failed to load data:', e)
    error.value = e.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

// Handle subtitle update from editor
function onSubtitleUpdate(updated) {
  subtitles.value = updated
  hasChanges.value = true
}

// Handle seek from editor
function onSeek(time) {
  currentTime.value = time
  // Seek video element
  const video = document.querySelector('.subtitle-edit-modal video')
  if (video) {
    video.currentTime = time
  }
}

// Handle video time update
function onTimeUpdate(e) {
  currentTime.value = e.target.currentTime
}

// Save subtitles
async function handleSave() {
  saving.value = true
  
  try {
    const content = generateSrt(subtitles.value)
    await api.put(`/videos/${props.videoId}/files/${fileType.value}/content`, {
      content
    })
    
    hasChanges.value = false
    emit('saved')
  } catch (e) {
    console.error('Failed to save:', e)
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

// Handle close
function handleClose() {
  if (hasChanges.value) {
    if (!confirm('有未保存的更改，确定要关闭吗？')) {
      return
    }
  }
  emit('close')
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay subtitle-edit-modal" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>📝 编辑{{ subtitleType === 'translated' ? '翻译' : '原始' }}字幕</h3>
          <div class="header-actions">
            <span v-if="hasChanges" class="unsaved-badge">未保存</span>
            <button class="close-btn" @click="handleClose">✕</button>
          </div>
        </div>
        
        <div class="modal-body">
          <div v-if="loading" class="loading-state">
            <span>加载中...</span>
          </div>
          
          <div v-else-if="error" class="error-state">
            <span>{{ error }}</span>
            <button @click="loadData">重试</button>
          </div>
          
          <template v-else>
            <div class="editor-layout">
              <!-- Left: Video Preview -->
              <div class="video-section">
                <div class="video-wrapper">
                  <video 
                    :src="videoStreamUrl"
                    controls
                    @timeupdate="onTimeUpdate"
                  />
                </div>
                <div class="video-info">
                  <span class="video-title">{{ videoDetail?.title }}</span>
                </div>
              </div>
              
              <!-- Right: Subtitle Editor -->
              <div class="subtitle-section">
                <SubtitleEditor
                  :subtitles="subtitles"
                  :current-time="currentTime"
                  @update="onSubtitleUpdate"
                  @seek="onSeek"
                  @save="handleSave"
                />
              </div>
            </div>
          </template>
        </div>
        
        <div class="modal-footer">
          <div class="footer-info">
            <span v-if="subtitles.length">共 {{ subtitles.length }} 条字幕</span>
          </div>
          <div class="footer-actions">
            <button class="btn btn-secondary" @click="handleClose">关闭</button>
            <button 
              class="btn btn-primary" 
              :disabled="!hasChanges || saving"
              @click="handleSave"
            >
              {{ saving ? '保存中...' : '保存' }}
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
  width: 95%;
  max-width: 1200px;
  height: 85vh;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.unsaved-badge {
  font-size: 12px;
  padding: 4px 8px;
  background-color: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
  border-radius: 4px;
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
  overflow: hidden;
  padding: 20px;
}

.loading-state, .error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: var(--text-secondary);
  
  button {
    padding: 8px 16px;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
}

.editor-layout {
  display: flex;
  gap: 20px;
  height: 100%;
}

.video-section {
  width: 45%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.video-wrapper {
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
  
  video {
    width: 100%;
    display: block;
  }
}

.video-info {
  padding: 8px 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
}

.video-title {
  font-size: 14px;
  color: var(--text-primary);
}

.subtitle-section {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
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
