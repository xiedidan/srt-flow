<script setup>
/**
 * Task submit modal component
 */
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  taskType: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['close', 'submit'])

const selectedTaskType = ref(props.taskType || 'download')
const payload = ref({})
const submitting = ref(false)

// Task type options
const taskTypes = [
  { value: 'download', label: '下载视频', icon: '⬇️' },
  { value: 'asr', label: '语音识别', icon: '🎤' },
  { value: 'translate', label: '字幕翻译', icon: '🌐' },
  { value: 'tts', label: '语音合成', icon: '🔊' },
  { value: 'synthesize', label: '视频合成', icon: '🎬' },
  { value: 'asset_gen', label: '素材生成', icon: '📦' }
]

// Whether to show task type selector (hide if taskType is passed from parent)
const showTypeSelector = computed(() => !props.taskType)

// Form fields based on task type
const formFields = computed(() => {
  switch (selectedTaskType.value) {
    case 'download':
      return [
        { key: 'url', label: '视频 URL', type: 'text', placeholder: 'https://www.youtube.com/watch?v=...' }
      ]
    case 'asr':
      return [
        { key: 'video_id', label: '视频 ID', type: 'text', placeholder: '选择要识别的视频' },
        { key: 'language', label: '源语言', type: 'select', options: [
          { value: 'auto', label: '自动检测' },
          { value: 'zh', label: '中文' },
          { value: 'en', label: '英语' },
          { value: 'ja', label: '日语' },
          { value: 'ko', label: '韩语' },
          { value: 'fr', label: '法语' },
          { value: 'de', label: '德语' },
          { value: 'es', label: '西班牙语' },
          { value: 'ru', label: '俄语' }
        ]},
        { key: 'model', label: '模型', type: 'select', options: [
          { value: 'large-v3', label: 'Whisper Large V3' },
          { value: 'medium', label: 'Whisper Medium' },
          { value: 'small', label: 'Whisper Small' }
        ]}
      ]
    case 'translate':
      return [
        { key: 'video_id', label: '视频 ID', type: 'text', placeholder: '选择要翻译的视频' },
        { key: 'target_lang', label: '目标语言', type: 'select', options: [
          { value: 'zh', label: '中文' },
          { value: 'en', label: '英文' },
          { value: 'ja', label: '日文' }
        ]}
      ]
    case 'tts':
      return [
        { key: 'video_id', label: '视频 ID', type: 'text', placeholder: '选择要合成语音的视频' },
        { key: 'engine', label: 'TTS 引擎', type: 'select', options: [
          { value: 'coqui', label: 'Coqui TTS' },
          { value: 'chattts', label: 'ChatTTS' },
          { value: 'sparktts', label: 'SparkTTS' }
        ]}
      ]
    case 'synthesize':
      return [
        { key: 'video_id', label: '视频 ID', type: 'text', placeholder: '选择要合成的视频' },
        { key: 'burn_subtitle', label: '烧录字幕', type: 'checkbox' },
        { key: 'replace_audio', label: '替换音频', type: 'checkbox' }
      ]
    case 'asset_gen':
      return [
        { key: 'video_id', label: '视频 ID', type: 'text', placeholder: '选择要生成素材的视频' },
        { key: 'generate_title', label: '生成标题', type: 'checkbox' },
        { key: 'generate_summary', label: '生成摘要', type: 'checkbox' },
        { key: 'generate_thumbnail', label: '生成缩略图', type: 'checkbox' }
      ]
    default:
      return []
  }
})

// Reset payload when task type changes
function initPayload() {
  payload.value = {}
  // Set default values for checkboxes and selects
  formFields.value.forEach(field => {
    if (field.type === 'checkbox') {
      payload.value[field.key] = true
    }
    if (field.type === 'select' && field.options?.length) {
      payload.value[field.key] = field.options[0].value
    }
  })
}

// Initialize on mount
onMounted(() => {
  initPayload()
})

const isValid = computed(() => {
  // Check required fields
  for (const field of formFields.value) {
    if (field.type !== 'checkbox' && !payload.value[field.key]) {
      return false
    }
  }
  return true
})

async function handleSubmit() {
  if (!isValid.value || submitting.value) return
  
  submitting.value = true
  try {
    emit('submit', {
      type: selectedTaskType.value,
      payload: { ...payload.value }
    })
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
    <div class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>提交新任务</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div class="modal-body">
          <!-- Task Type Selection -->
          <div v-if="showTypeSelector" class="form-group">
            <label>任务类型</label>
            <div class="type-grid">
              <button
                v-for="type in taskTypes"
                :key="type.value"
                class="type-btn"
                :class="{ active: selectedTaskType === type.value }"
                @click="selectedTaskType = type.value; initPayload()"
              >
                <span class="type-icon">{{ type.icon }}</span>
                <span class="type-label">{{ type.label }}</span>
              </button>
            </div>
          </div>
          
          <!-- Dynamic Form Fields -->
          <div v-for="field in formFields" :key="field.key" class="form-group">
            <label :for="field.key">{{ field.label }}</label>
            
            <input
              v-if="field.type === 'text'"
              :id="field.key"
              v-model="payload[field.key]"
              type="text"
              class="form-input"
              :placeholder="field.placeholder"
            />
            
            <select
              v-else-if="field.type === 'select'"
              :id="field.key"
              v-model="payload[field.key]"
              class="form-select"
            >
              <option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
            
            <label v-else-if="field.type === 'checkbox'" class="checkbox-label">
              <input
                type="checkbox"
                v-model="payload[field.key]"
              />
              <span>{{ field.label }}</span>
            </label>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleClose">取消</button>
          <button 
            class="btn btn-primary" 
            :disabled="!isValid || submitting"
            @click="handleSubmit"
          >
            {{ submitting ? '提交中...' : '提交任务' }}
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

.form-group {
  margin-bottom: 20px;
  
  > label {
    display: block;
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }
}

.type-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.type-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  &.active {
    background-color: rgba(59, 130, 246, 0.1);
    border-color: var(--accent-color);
  }
  
  .type-icon {
    font-size: 20px;
  }
  
  .type-label {
    font-size: 12px;
    color: var(--text-primary);
  }
}

.form-input,
.form-select {
  width: 100%;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
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

.form-select {
  cursor: pointer;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  
  input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent-color);
  }
  
  span {
    font-size: 14px;
    color: var(--text-primary);
  }
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
