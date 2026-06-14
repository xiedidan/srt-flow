<script setup>
/**
 * Synthesis Task Creation Modal
 * Allows user to configure video synthesis options before creating task
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'

const props = defineProps({
  visible: Boolean,
  video: Object
})

const emit = defineEmits(['close', 'submit'])
const router = useRouter()

// Form state
const subtitleMode = ref('dual')
const audioMode = ref('original')  // 'original', 'tts', 'mix'
const submitting = ref(false)
const loadingConfig = ref(true)
const hasTranslatedSubtitle = ref(false)
const hasOriginalSubtitle = ref(false)
const hasTtsAudio = ref(false)

// Subtitle mode options
const subtitleModeOptions = computed(() => {
  const options = []
  
  if (hasOriginalSubtitle.value && hasTranslatedSubtitle.value) {
    options.push({ value: 'dual', label: '双字幕叠加（翻译 + 原始）' })
  }
  if (hasTranslatedSubtitle.value) {
    options.push({ value: 'translated_only', label: '仅翻译字幕' })
  }
  if (hasOriginalSubtitle.value) {
    options.push({ value: 'original_only', label: '仅原始字幕' })
  }
  
  return options
})

// Audio mode options
const audioModeOptions = computed(() => {
  const options = [
    { value: 'original', label: '原始音频', description: '保留视频原声' }
  ]
  
  if (hasTtsAudio.value) {
    options.push(
      { value: 'tts', label: 'TTS 音频', description: '仅使用合成语音' },
      { value: 'mix', label: '混合音频', description: '原声 + TTS 语音叠加' }
    )
  }
  
  return options
})

// Check available subtitles and audio
function checkSubtitles() {
  if (!props.video?.files) {
    hasOriginalSubtitle.value = false
    hasTranslatedSubtitle.value = false
    hasTtsAudio.value = false
    return
  }
  
  hasOriginalSubtitle.value = !!props.video.files.subtitle_original
  hasTranslatedSubtitle.value = !!props.video.files.subtitle_translated
  hasTtsAudio.value = !!props.video.files.audio_tts
  
  // Set default mode based on available subtitles
  if (hasTranslatedSubtitle.value && hasOriginalSubtitle.value) {
    subtitleMode.value = 'dual'
  } else if (hasTranslatedSubtitle.value) {
    subtitleMode.value = 'translated_only'
  } else if (hasOriginalSubtitle.value) {
    subtitleMode.value = 'original_only'
  }
  
  // Set default audio mode
  if (hasTtsAudio.value) {
    audioMode.value = 'tts'  // Default to TTS if available
  } else {
    audioMode.value = 'original'
  }
}

// Load synthesis config
async function loadConfig() {
  loadingConfig.value = true
  try {
    const res = await api.get('/config/synthesis')
    if (res.data?.subtitle_mode) {
      // Only use config default if it's valid for current video
      const configMode = res.data.subtitle_mode
      const validModes = subtitleModeOptions.value.map(o => o.value)
      if (validModes.includes(configMode)) {
        subtitleMode.value = configMode
      }
    }
    // Audio mode config (if added to backend config in future)
    if (res.data?.audio_mode) {
      const configAudioMode = res.data.audio_mode
      const validAudioModes = audioModeOptions.value.map(o => o.value)
      if (validAudioModes.includes(configAudioMode)) {
        audioMode.value = configAudioMode
      }
    }
  } catch (e) {
    console.error('Failed to load synthesis config:', e)
  } finally {
    loadingConfig.value = false
  }
}

// Reset form when modal opens
watch(() => props.visible, (visible) => {
  if (visible) {
    checkSubtitles()
    loadConfig()
  }
})

onMounted(() => {
  if (props.visible) {
    checkSubtitles()
    loadConfig()
  }
})

// Check if can create task
const canCreate = computed(() => {
  return hasOriginalSubtitle.value || hasTranslatedSubtitle.value
})

async function handleSubmit() {
  if (submitting.value || !props.video || !canCreate.value) return
  
  submitting.value = true
  try {
    const taskData = {
      type: 'synthesize',
      payload: {
        video_id: props.video.id,
        subtitle_mode: subtitleMode.value,
        audio_mode: audioMode.value
      }
    }
    
    const res = await api.post('/tasks', taskData)
    emit('submit', res.data)
    
    if (confirm('任务创建成功！是否跳转到视频合成任务页面？')) {
      router.push('/synthesis')
    }
    emit('close')
  } catch (e) {
    console.error('Failed to create synthesis task:', e)
    alert('创建任务失败: ' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>🎬 创建视频合成任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div class="modal-body">
          <!-- Video Info -->
          <div v-if="video" class="video-info">
            <div class="video-title">{{ video.title }}</div>
            <div class="video-meta">
              <span>{{ video.source }}</span>
              <span v-if="video.duration">{{ Math.floor(video.duration / 60) }}:{{ String(Math.floor(video.duration % 60)).padStart(2, '0') }}</span>
            </div>
          </div>
          
          <!-- No subtitle warning -->
          <div v-if="!canCreate" class="warning-box error">
            <span class="warning-icon">❌</span>
            <span>该视频没有可用的字幕文件，请先进行语音识别或翻译</span>
          </div>
          
          <!-- Subtitle and Audio status -->
          <div v-else class="subtitle-status">
            <div class="status-item" :class="{ available: hasOriginalSubtitle }">
              <span class="status-icon">{{ hasOriginalSubtitle ? '✅' : '❌' }}</span>
              <span>原始字幕</span>
            </div>
            <div class="status-item" :class="{ available: hasTranslatedSubtitle }">
              <span class="status-icon">{{ hasTranslatedSubtitle ? '✅' : '❌' }}</span>
              <span>翻译字幕</span>
            </div>
            <div class="status-item" :class="{ available: hasTtsAudio }">
              <span class="status-icon">{{ hasTtsAudio ? '✅' : '❌' }}</span>
              <span>TTS 音频</span>
            </div>
          </div>
          
          <!-- Subtitle Mode Selection -->
          <div v-if="canCreate" class="form-group">
            <label for="subtitle-mode">字幕模式</label>
            <select 
              id="subtitle-mode" 
              v-model="subtitleMode" 
              class="form-select"
              :disabled="loadingConfig"
            >
              <option v-for="opt in subtitleModeOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
            <p class="form-hint">
              选择要烧录到视频中的字幕类型。双字幕模式会同时显示原始和翻译字幕。
            </p>
          </div>

          <!-- Audio Mode Selection -->
          <div v-if="canCreate" class="form-group">
            <label for="audio-mode">音频模式</label>
            <select 
              id="audio-mode" 
              v-model="audioMode" 
              class="form-select"
              :disabled="loadingConfig"
            >
              <option v-for="opt in audioModeOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
            <p class="form-hint">
              {{ audioModeOptions.find(o => o.value === audioMode)?.description }}
            </p>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleClose">取消</button>
          <button 
            class="btn btn-primary" 
            :disabled="submitting || loadingConfig || !canCreate"
            @click="handleSubmit"
          >
            {{ submitting ? '创建中...' : '开始合成' }}
          </button>
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
  max-width: 480px;
  max-height: 80vh;
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

.video-info {
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  margin-bottom: 20px;
}

.video-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.warning-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 13px;
  color: #f59e0b;
  
  &.error {
    background-color: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.3);
    color: #ef4444;
  }
}

.warning-icon {
  font-size: 16px;
}

.subtitle-status {
  display: flex;
  gap: 16px;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  margin-bottom: 20px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
  
  &.available {
    color: var(--text-primary);
  }
}

.status-icon {
  font-size: 14px;
}

.form-group {
  margin-bottom: 20px;
  
  > label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 8px;
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
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.form-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
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
