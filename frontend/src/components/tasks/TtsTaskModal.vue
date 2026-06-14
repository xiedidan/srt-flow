<script setup>
/**
 * TTS Task Creation Modal for Video Management
 * Simplified version for single video TTS task creation
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { listReferenceAudios, getAudioStreamUrl } from '@/api/referenceAudio'
import TTSVoiceSelect from '@/components/settings/TTSVoiceSelect.vue'

const props = defineProps({
  visible: Boolean,
  video: Object
})

const emit = defineEmits(['close', 'submit'])
const router = useRouter()

// TTS options
const engine = ref('chattts')
const speaker = ref('')
const outputFormat = ref('m4a')
const useGpu = ref(true)
const minSpeed = ref(0.5)
const maxSpeed = ref(2.0)
const enableTimeStretch = ref(true)

// Online TTS voice selection
const azureVoice = ref('zh-CN-XiaoxiaoNeural')
const edgeVoice = ref('zh-CN-XiaoxiaoNeural')
const volcVoice = ref('zh_female_qingxin')

// Voice preview state
const previewLoading = ref(false)
const previewAudio = ref(null)
const previewPlaying = ref(false)

// Reference audio state
const referenceAudios = ref([])
const selectedReferenceAudioId = ref('')
const loadingReferenceAudios = ref(false)
const playingAudioId = ref(null)
const audioElement = ref(null)

// Loading state
const loadingConfig = ref(true)
const submitting = ref(false)

// TTS engine options - include online services
const engineOptions = [
  { value: 'chattts', label: 'ChatTTS (推荐)', description: '自然度高，支持情感', supportsCloning: false, isOnline: false },
  { value: 'azure_tts', label: 'Azure TTS', description: '微软在线服务，高质量', supportsCloning: false, isOnline: true },
  { value: 'edge_tts', label: 'Edge TTS', description: '免费在线服务', supportsCloning: false, isOnline: true },
  { value: 'volc_tts', label: '火山引擎 TTS', description: '字节跳动在线服务', supportsCloning: false, isOnline: true },
  { value: 'coqui', label: 'Coqui TTS', description: '开源，多语言支持', supportsCloning: true, isOnline: false },
  { value: 'sparktts', label: 'SparkTTS', description: '讯飞开源，中文优秀', supportsCloning: true, isOnline: false },
  { value: 'indextts', label: 'IndexTTS', description: '零样本克隆', supportsCloning: true, isOnline: false },
  { value: 'cozyvoice', label: 'CozyVoice', description: '阿里开源，多风格', supportsCloning: true, isOnline: false },
  { value: 'vits', label: 'VITS', description: '轻量快速', supportsCloning: false, isOnline: false }
]

// Output format options
const formatOptions = [
  { value: 'm4a', label: 'M4A (AAC)', description: '推荐，体积小' },
  { value: 'mp3', label: 'MP3', description: '兼容性好' },
  { value: 'wav', label: 'WAV', description: '无损，体积大' }
]

// Check if current engine is online TTS
const isOnlineTTS = computed(() => {
  return ['azure_tts', 'edge_tts', 'volc_tts'].includes(engine.value)
})

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

// Check if video has translated subtitle
const hasTranslatedSubtitle = computed(() => {
  return !!props.video?.files?.subtitle_translated
})

// Check if video has TTS audio already
const hasTtsAudio = computed(() => {
  return !!props.video?.files?.audio_tts
})

// Get current voice for online TTS
const currentOnlineVoice = computed(() => {
  switch (engine.value) {
    case 'azure_tts': return azureVoice.value
    case 'edge_tts': return edgeVoice.value
    case 'volc_tts': return volcVoice.value
    default: return ''
  }
})

// Can submit
const canSubmit = computed(() => {
  return props.video && hasTranslatedSubtitle.value && !submitting.value && !loadingConfig.value
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
      // Online TTS voices
      if (res.data.azure_tts_voice) azureVoice.value = res.data.azure_tts_voice
      if (res.data.edge_tts_voice) edgeVoice.value = res.data.edge_tts_voice
      if (res.data.volc_tts_voice) volcVoice.value = res.data.volc_tts_voice
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

// Toggle audio playback for reference audio
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

// Preview voice for online TTS
async function previewVoice() {
  if (!isOnlineTTS.value || previewLoading.value) return
  
  // Stop current preview if playing
  if (previewAudio.value) {
    previewAudio.value.pause()
    previewAudio.value = null
    previewPlaying.value = false
  }
  
  previewLoading.value = true
  try {
    const response = await api.post('/tts/voice-preview', {
      engine: engine.value,
      voice: currentOnlineVoice.value,
      text: '你好，这是语音合成的试听效果。Hello, this is a voice preview.'
    }, { responseType: 'blob' })
    
    // Create audio from blob
    const audioBlob = new Blob([response], { type: 'audio/mpeg' })
    const audioUrl = URL.createObjectURL(audioBlob)
    previewAudio.value = new Audio(audioUrl)
    previewAudio.value.play()
    previewPlaying.value = true
    
    previewAudio.value.onended = () => {
      previewPlaying.value = false
      URL.revokeObjectURL(audioUrl)
    }
    previewAudio.value.onerror = () => {
      previewPlaying.value = false
      URL.revokeObjectURL(audioUrl)
    }
  } catch (e) {
    console.error('Failed to preview voice:', e)
    alert('试听失败: ' + (e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    previewLoading.value = false
  }
}

// Stop voice preview
function stopPreview() {
  if (previewAudio.value) {
    previewAudio.value.pause()
    previewAudio.value = null
    previewPlaying.value = false
  }
}

// Reset form when modal opens
watch(() => props.visible, (visible) => {
  if (visible) {
    loadTtsConfig()
    loadReferenceAudios()
    selectedReferenceAudioId.value = ''
    stopPreview()
  }
})

onMounted(() => {
  if (props.visible) {
    loadTtsConfig()
    loadReferenceAudios()
  }
})

onUnmounted(() => {
  stopPreview()
  if (audioElement.value) {
    audioElement.value.pause()
    audioElement.value = null
  }
})

// Submit task
async function handleSubmit() {
  if (!canSubmit.value) return
  
  submitting.value = true
  try {
    let speakerValue = speaker.value || null
    if (selectedReferenceAudio.value && currentEngineSupportsCloning.value) {
      speakerValue = `ref:${selectedReferenceAudio.value.id}`
    }
    
    const payload = {
      video_id: props.video.id,
      subtitle_path: props.video.files?.subtitle_translated,
      engine: engine.value,
      speaker: speakerValue,
      reference_audio_id: selectedReferenceAudio.value?.id || null,
      output_format: outputFormat.value,
      use_gpu: useGpu.value,
      min_speed: minSpeed.value,
      max_speed: maxSpeed.value,
      enable_time_stretch: enableTimeStretch.value
    }
    
    // Add online TTS voice settings
    if (engine.value === 'azure_tts') {
      payload.azure_tts_voice = azureVoice.value
    } else if (engine.value === 'edge_tts') {
      payload.edge_tts_voice = edgeVoice.value
    } else if (engine.value === 'volc_tts') {
      payload.volc_tts_voice = volcVoice.value
    }
    
    await api.post('/tasks', { type: 'tts', payload })
    
    emit('submit')
    
    if (confirm('任务创建成功！是否跳转到语音合成任务页面？')) {
      router.push('/tts')
    }
    emit('close')
  } catch (e) {
    console.error('Failed to create TTS task:', e)
    alert('创建任务失败: ' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  stopPreview()
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>🔊 创建语音合成任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div class="modal-body">
          <!-- Video Info -->
          <div v-if="video" class="video-info-card">
            <img v-if="video.thumbnail" :src="video.thumbnail" class="video-thumb" alt="" />
            <div class="video-thumb placeholder" v-else>🎬</div>
            <div class="video-details">
              <div class="video-title">{{ video.title }}</div>
              <div class="video-meta">
                <span>{{ video.source }}</span>
                <span v-if="video.duration">{{ formatDuration(video.duration) }}</span>
              </div>
              <div v-if="hasTtsAudio" class="warning-badge">⚠️ 已有语音，将被覆盖</div>
            </div>
          </div>
          
          <!-- No subtitle warning -->
          <div v-if="!hasTranslatedSubtitle" class="warning-box error">
            <span class="warning-icon">❌</span>
            <span>该视频没有翻译字幕，请先进行语音识别和翻译</span>
          </div>
          
          <!-- TTS Options -->
          <template v-if="hasTranslatedSubtitle">
            <div class="form-group">
              <label>TTS 引擎</label>
              <select v-model="engine" class="form-select" :disabled="loadingConfig">
                <option v-for="opt in engineOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}{{ opt.isOnline ? ' (在线)' : '' }}
                </option>
              </select>
              <p class="form-hint">{{ engineOptions.find(e => e.value === engine)?.description }}</p>
            </div>
            
            <div class="form-group">
              <label>输出格式</label>
              <select v-model="outputFormat" class="form-select" :disabled="loadingConfig">
                <option v-for="opt in formatOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>

            <!-- Online TTS Voice Selection -->
            <div v-if="isOnlineTTS" class="form-group">
              <label>语音角色</label>
              <div class="voice-select-row">
                <TTSVoiceSelect
                  v-if="engine === 'azure_tts'"
                  v-model="azureVoice"
                  engine="azure_tts"
                />
                <TTSVoiceSelect
                  v-else-if="engine === 'edge_tts'"
                  v-model="edgeVoice"
                  engine="edge_tts"
                />
                <TTSVoiceSelect
                  v-else-if="engine === 'volc_tts'"
                  v-model="volcVoice"
                  engine="volc_tts"
                />
                <button 
                  class="preview-btn" 
                  :class="{ playing: previewPlaying }"
                  :disabled="previewLoading"
                  @click="previewPlaying ? stopPreview() : previewVoice()"
                  :title="previewPlaying ? '停止试听' : '试听语音'"
                >
                  {{ previewLoading ? '⏳' : (previewPlaying ? '⏹️' : '▶️') }}
                  {{ previewLoading ? '加载中...' : (previewPlaying ? '停止' : '试听') }}
                </button>
              </div>
              <p class="form-hint">选择在线 TTS 服务的语音角色，点击试听按钮可预览效果</p>
            </div>

            <!-- Local TTS Speaker (for non-online engines) -->
            <div v-if="!isOnlineTTS && !currentEngineSupportsCloning" class="form-group">
              <label>说话人/音色（可选）</label>
              <input v-model="speaker" type="text" class="form-input" placeholder="留空使用默认音色"
                :disabled="loadingConfig" />
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
          </template>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleClose">取消</button>
          <button class="btn btn-primary" :disabled="!canSubmit" @click="handleSubmit">
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
  max-width: 520px;
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
  .video-title { font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .video-meta { font-size: 12px; color: var(--text-muted); display: flex; gap: 8px; }
  .warning-badge { margin-top: 6px; font-size: 12px; color: var(--warning, #f59e0b); }
}

.warning-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #f59e0b;
  
  &.error {
    background-color: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.3);
    color: #ef4444;
  }
}

.form-group {
  margin-bottom: 16px;
  
  > label { display: block; font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: 8px; }
  
  &.checkbox-group {
    label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: normal;
      cursor: pointer;
      
      input { accent-color: var(--accent-color); }
    }
  }
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
  &::placeholder { color: var(--text-muted); }
}

.form-hint { margin-top: 6px; font-size: 12px; color: var(--text-muted); line-height: 1.4; }

.voice-select-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  
  > :first-child {
    flex: 1;
  }
}

.preview-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    border-color: var(--accent-color);
    background-color: var(--bg-hover);
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  &.playing {
    background-color: rgba(59, 130, 246, 0.1);
    border-color: var(--accent-color);
    color: var(--accent-color);
  }
}

.reference-audio-section {
  .optional-badge {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: normal;
    margin-left: 6px;
  }
}

.loading-hint {
  text-align: center;
  padding: 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.empty-audio-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-muted);
  
  .link-btn {
    color: var(--accent-color);
    text-decoration: none;
    &:hover { text-decoration: underline; }
  }
}

.reference-audio-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.audio-option {
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
  
  .audio-radio input { accent-color: var(--accent-color); }
  .audio-info { flex: 1; min-width: 0; }
  .audio-name { font-size: 13px; color: var(--text-primary); }
  .audio-desc { font-size: 12px; color: var(--text-muted); }
  .audio-meta { font-size: 11px; color: var(--text-muted); display: flex; gap: 8px; margin-top: 2px; }
  .audio-desc-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 150px; }
}

.play-btn {
  padding: 6px 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  
  &:hover { background-color: var(--bg-hover); }
  &.playing { background-color: rgba(59, 130, 246, 0.2); border-color: var(--accent-color); }
}

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

.speed-range {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
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
