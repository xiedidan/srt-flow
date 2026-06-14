<script setup>
/**
 * ASR Task Creation Modal
 * Allows user to confirm source language before creating ASR task
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
const sourceLanguage = ref('auto')
const submitting = ref(false)
const globalConfig = ref(null)
const loadingConfig = ref(true)
const hasExistingSubtitle = ref(false)

// Language options
const languageOptions = [
  { value: 'auto', label: '自动检测' },
  { value: 'zh', label: '中文' },
  { value: 'en', label: '英语' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
  { value: 'ru', label: '俄语' },
  { value: 'pt', label: '葡萄牙语' },
  { value: 'it', label: '意大利语' },
  { value: 'ar', label: '阿拉伯语' },
  { value: 'hi', label: '印地语' },
  { value: 'th', label: '泰语' },
  { value: 'vi', label: '越南语' }
]

// Load global config to get default source language
async function loadGlobalConfig() {
  loadingConfig.value = true
  try {
    // API interceptor returns { data, message } on success
    const res = await api.get('/config/global')
    globalConfig.value = res.data
    // Set default source language from config
    if (globalConfig.value?.default_source_language) {
      sourceLanguage.value = globalConfig.value.default_source_language
    }
  } catch (e) {
    console.error('Failed to load global config:', e)
  } finally {
    loadingConfig.value = false
  }
}

// Check if video already has subtitle
function checkExistingSubtitle() {
  if (props.video?.files?.subtitle_original) {
    hasExistingSubtitle.value = true
  } else {
    hasExistingSubtitle.value = false
  }
}

// Reset form when modal opens
watch(() => props.visible, (visible) => {
  if (visible) {
    loadGlobalConfig()
    checkExistingSubtitle()
  }
})

onMounted(() => {
  if (props.visible) {
    loadGlobalConfig()
    checkExistingSubtitle()
  }
})

async function handleSubmit() {
  if (submitting.value || !props.video) return
  
  // Confirm if existing subtitle will be overwritten
  if (hasExistingSubtitle.value) {
    const confirmed = confirm('该视频已有识别结果，继续将覆盖原有字幕文件。是否继续？')
    if (!confirmed) return
  }
  
  submitting.value = true
  try {
    const taskData = {
      type: 'asr',
      payload: {
        video_id: props.video.id,
        language: sourceLanguage.value
      }
    }
    
    // API interceptor returns { data, message } on success
    const res = await api.post('/tasks', taskData)
    emit('submit', res.data)
    
    // Ask user if they want to navigate to ASR tasks page
    if (confirm('任务创建成功！是否跳转到语音识别任务页面？')) {
      router.push('/asr')
    }
    emit('close')
  } catch (e) {
    console.error('Failed to create ASR task:', e)
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
          <h3>🎤 创建语音识别任务</h3>
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
          
          <!-- Warning for existing subtitle -->
          <div v-if="hasExistingSubtitle" class="warning-box">
            <span class="warning-icon">⚠️</span>
            <span>该视频已有识别结果，重新识别将覆盖原有字幕文件</span>
          </div>
          
          <!-- Language Selection -->
          <div class="form-group">
            <label for="source-language">源语言（视频中的语言）</label>
            <select 
              id="source-language" 
              v-model="sourceLanguage" 
              class="form-select"
              :disabled="loadingConfig"
            >
              <option v-for="lang in languageOptions" :key="lang.value" :value="lang.value">
                {{ lang.label }}
              </option>
            </select>
            <p class="form-hint">
              选择视频中说话的语言。如果不确定，可以选择"自动检测"，但指定语言通常能获得更好的识别效果。
            </p>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleClose">取消</button>
          <button 
            class="btn btn-primary" 
            :disabled="submitting || loadingConfig"
            @click="handleSubmit"
          >
            {{ submitting ? '创建中...' : '开始识别' }}
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
}

.warning-icon {
  font-size: 16px;
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
