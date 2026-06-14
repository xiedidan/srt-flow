<script setup>
/**
 * Whisper model selector with download status and progress
 * 
 * - Model files are cross-platform, shared by all Whisper engines
 * - Engine executables are platform-specific, need to select platform
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  getModels,
  getModelStatus,
  downloadModel,
  deleteModel,
  getEngineList,
  getEngineStatus,
  downloadEngine,
  deleteEngine
} from '@/api/asr'

const props = defineProps({
  modelValue: String,
  engine: {
    type: String,
    default: 'faster_whisper_xxl'
  }
})

const emit = defineEmits(['update:modelValue'])

// State
const models = ref([])
const engineStatus = ref([])
const loading = ref(false)
const downloadingModel = ref(null)
const downloadingEngine = ref(null)
const downloadProgress = ref({})
const engineProgress = ref({})
const deletingModel = ref(false)
const deletingEngine = ref(false)
const selectedPlatform = ref('windows')
let pollTimer = null

const platformOptions = [
  { value: 'windows', label: 'Windows' },
  { value: 'linux', label: 'Linux' },
  { value: 'macos', label: 'macOS' }
]

const modelOptions = [
  { value: 'tiny', label: 'Tiny' },
  { value: 'base', label: 'Base' },
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
  { value: 'large-v2', label: 'Large V2' },
  { value: 'large-v3', label: 'Large V3' }
]

// Check if current engine is a local Whisper engine (needs executable)
const isLocalEngine = computed(() => 
  props.engine === 'faster_whisper_xxl'
)

// Model options with download status
const optionsWithStatus = computed(() => {
  return modelOptions.map(opt => {
    const modelInfo = models.value.find(m => m.model_size === opt.value)
    const downloaded = modelInfo?.downloaded || false
    const sizeMb = modelInfo?.size_mb || 0
    return {
      ...opt,
      downloaded,
      sizeMb,
      label: downloaded ? `${opt.label} (已下载 ${Math.round(sizeMb)}MB)` : opt.label
    }
  })
})

// Current model info
const currentModelInfo = computed(() => {
  return models.value.find(m => m.model_size === props.modelValue) || {}
})

// Current engine info for selected platform
const currentEngineInfo = computed(() => {
  return engineStatus.value.find(x => x.platform === selectedPlatform.value) || {}
})

// Model downloading state
const isModelDownloading = computed(() => {
  return downloadingModel.value === props.modelValue ||
         currentModelInfo.value.download_status === 'downloading'
})

// Engine downloading state
const isEngineDownloading = computed(() => {
  return downloadingEngine.value === selectedPlatform.value ||
         currentEngineInfo.value.download_status === 'downloading'
})

// Model download progress
const modelDownloadProgress = computed(() => {
  if (!isModelDownloading.value) return null
  const info = downloadProgress.value[props.modelValue] || currentModelInfo.value
  return {
    progress: info.download_progress || 0,
    downloadedMb: info.downloaded_mb || 0,
    totalMb: info.total_mb || info.total_size_mb || 0
  }
})

// Engine download progress
const engineDownloadProgress = computed(() => {
  if (!isEngineDownloading.value) return null
  const info = engineProgress.value[selectedPlatform.value] || currentEngineInfo.value
  return {
    progress: info.download_progress || 0,
    downloadedMb: info.downloaded_mb || 0,
    totalMb: info.total_mb || 0
  }
})

// Check if current model is downloaded
const isModelDownloaded = computed(() => currentModelInfo.value?.downloaded || false)

// Check if current engine is downloaded
const isEngineDownloaded = computed(() => currentEngineInfo.value?.downloaded || false)

// Load models status
async function loadModels() {
  loading.value = true
  try {
    const { data } = await getModels()
    models.value = data.models || []
    
    const downloadingItem = models.value.find(m => m.download_status === 'downloading')
    if (downloadingItem) {
      downloadingModel.value = downloadingItem.model_size
      startPolling()
    }
  } catch (e) {
    console.error('Failed to load models:', e)
  } finally {
    loading.value = false
  }
}

// Load engine status for current engine
async function loadEngineStatus() {
  if (!isLocalEngine.value) return
  
  try {
    const { data } = await getEngineList(props.engine)
    engineStatus.value = data.platforms || []
    
    const downloadingItem = engineStatus.value.find(x => x.download_status === 'downloading')
    if (downloadingItem) {
      downloadingEngine.value = downloadingItem.platform
      startPolling()
    }
  } catch (e) {
    console.error('Failed to load engine status:', e)
  }
}

// Handle model download
async function handleModelDownload() {
  const modelSize = props.modelValue
  const modelInfo = models.value.find(m => m.model_size === modelSize)
  
  if (modelInfo?.downloaded) {
    if (!confirm(`模型 ${modelSize} 已下载，确定要重新下载吗？`)) return
  }
  
  downloadingModel.value = modelSize
  downloadProgress.value[modelSize] = {
    download_progress: 0,
    downloaded_mb: 0,
    total_mb: modelInfo?.total_size_mb || 0
  }
  
  try {
    await downloadModel(modelSize)
    startPolling()
  } catch (e) {
    console.error('Model download failed:', e)
    alert('模型下载启动失败: ' + e.message)
    downloadingModel.value = null
  }
}

// Handle engine download
async function handleEngineDownload() {
  const platform = selectedPlatform.value
  const info = engineStatus.value.find(x => x.platform === platform)
  
  if (info?.downloaded) {
    if (!confirm(`引擎 (${platform}) 已下载，确定要重新下载吗？`)) return
  }
  
  downloadingEngine.value = platform
  engineProgress.value[platform] = {
    download_progress: 0,
    downloaded_mb: 0,
    total_mb: 0
  }
  
  try {
    await downloadEngine(props.engine, platform)
    startPolling()
  } catch (e) {
    console.error('Engine download failed:', e)
    alert('引擎下载启动失败: ' + e.message)
    downloadingEngine.value = null
  }
}

// Handle model delete
async function handleModelDelete() {
  const modelSize = props.modelValue
  const modelInfo = models.value.find(m => m.model_size === modelSize)
  
  if (!modelInfo?.downloaded) {
    alert('该模型未下载')
    return
  }
  
  const sizeMb = Math.round(modelInfo.size_mb)
  if (!confirm(`确定要删除模型 ${modelSize} 吗？将释放约 ${sizeMb} MB 空间`)) return
  
  deletingModel.value = true
  try {
    await deleteModel(modelSize)
    await loadModels()
  } catch (e) {
    console.error('Model delete failed:', e)
    alert('模型删除失败: ' + e.message)
  } finally {
    deletingModel.value = false
  }
}

// Handle engine delete
async function handleEngineDelete() {
  const platform = selectedPlatform.value
  const info = engineStatus.value.find(x => x.platform === platform)
  
  if (!info?.downloaded) {
    alert('该平台的引擎未下载')
    return
  }
  
  const sizeMb = Math.round(info.size_mb)
  if (!confirm(`确定要删除引擎 (${platform}) 吗？将释放约 ${sizeMb} MB 空间`)) return
  
  deletingEngine.value = true
  try {
    await deleteEngine(props.engine, platform)
    await loadEngineStatus()
  } catch (e) {
    console.error('Engine delete failed:', e)
    alert('引擎删除失败: ' + e.message)
  } finally {
    deletingEngine.value = false
  }
}

// Poll download status
function startPolling() {
  if (pollTimer) return
  
  pollTimer = setInterval(async () => {
    if (!downloadingModel.value && !downloadingEngine.value) {
      stopPolling()
      return
    }
    
    try {
      // Poll model status
      if (downloadingModel.value) {
        const { data } = await getModelStatus(downloadingModel.value)
        downloadProgress.value[downloadingModel.value] = {
          download_progress: data.download_progress,
          downloaded_mb: data.downloaded_mb,
          total_mb: data.total_mb
        }
        
        if (data.download_status === 'completed') {
          downloadingModel.value = null
          await loadModels()
        } else if (data.download_status === 'failed') {
          alert('模型下载失败: ' + (data.download_error || '未知错误'))
          downloadingModel.value = null
        }
      }
      
      // Poll engine status
      if (downloadingEngine.value) {
        const { data } = await getEngineStatus(props.engine, downloadingEngine.value)
        engineProgress.value[downloadingEngine.value] = {
          download_progress: data.download_progress,
          downloaded_mb: data.downloaded_mb,
          total_mb: data.total_mb
        }
        
        if (data.download_status === 'completed') {
          downloadingEngine.value = null
          await loadEngineStatus()
        } else if (data.download_status === 'failed') {
          alert('引擎下载失败: ' + (data.download_error || '未知错误'))
          downloadingEngine.value = null
        }
      }
      
      // Stop polling if nothing is downloading
      if (!downloadingModel.value && !downloadingEngine.value) {
        stopPolling()
      }
    } catch (e) {
      console.error('Status poll failed:', e)
    }
  }, 1000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleModelChange(event) {
  emit('update:modelValue', event.target.value)
}

// Watch engine change to reload engine status
watch(() => props.engine, () => {
  loadEngineStatus()
}, { immediate: false })

onMounted(() => {
  loadModels()
  loadEngineStatus()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="whisper-model-select">
    <!-- Engine executable section (for local Whisper engines) -->
    <div v-if="isLocalEngine" class="section engine-section">
      <div class="section-title">引擎可执行文件</div>
      <div class="select-row">
        <select
          v-model="selectedPlatform"
          class="item-select"
          :disabled="isEngineDownloading || deletingEngine"
        >
          <option v-for="opt in platformOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
            {{ engineStatus.find(x => x.platform === opt.value)?.downloaded ? '(已下载)' : '' }}
          </option>
        </select>
        
        <button
          type="button"
          class="btn-action btn-download"
          :disabled="isEngineDownloading || deletingEngine"
          @click="handleEngineDownload"
        >
          {{ isEngineDownloading ? '下载中...' : '下载引擎' }}
        </button>
        
        <button
          type="button"
          class="btn-action btn-delete"
          :disabled="isEngineDownloading || deletingEngine || !isEngineDownloaded"
          @click="handleEngineDelete"
        >
          {{ deletingEngine ? '删除中...' : '删除引擎' }}
        </button>
      </div>
      
      <!-- Engine download progress -->
      <div v-if="isEngineDownloading && engineDownloadProgress" class="download-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: engineDownloadProgress.progress + '%' }"></div>
        </div>
        <div class="progress-text">
          引擎: {{ engineDownloadProgress.downloadedMb.toFixed(1) }} / {{ engineDownloadProgress.totalMb.toFixed(1) }} MB
          ({{ engineDownloadProgress.progress }}%)
        </div>
      </div>
      
      <p v-else class="hint">选择目标平台后下载引擎可执行文件</p>
    </div>
    
    <!-- Model selection (shared by all local engines) -->
    <div v-if="isLocalEngine" class="section model-section">
      <div class="section-title">模型文件</div>
      <div class="select-row">
        <select
          :value="modelValue"
          @change="handleModelChange"
          class="item-select"
          :disabled="isModelDownloading || deletingModel"
        >
          <option v-for="opt in optionsWithStatus" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
        
        <button
          type="button"
          class="btn-action btn-download"
          :disabled="isModelDownloading || deletingModel"
          @click="handleModelDownload"
        >
          {{ isModelDownloading ? '下载中...' : '下载模型' }}
        </button>
        
        <button
          type="button"
          class="btn-action btn-delete"
          :disabled="isModelDownloading || deletingModel || !isModelDownloaded"
          @click="handleModelDelete"
        >
          {{ deletingModel ? '删除中...' : '删除模型' }}
        </button>
      </div>
      
      <!-- Model download progress -->
      <div v-if="isModelDownloading && modelDownloadProgress" class="download-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: modelDownloadProgress.progress + '%' }"></div>
        </div>
        <div class="progress-text">
          模型: {{ modelDownloadProgress.downloadedMb.toFixed(1) }} / {{ modelDownloadProgress.totalMb.toFixed(1) }} MB
          ({{ modelDownloadProgress.progress }}%)
        </div>
      </div>
      
      <p v-else class="hint">选择模型后点击下载按钮获取模型文件（模型跨平台共享）</p>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.whisper-model-select {
  width: 100%;
}

.section {
  &:not(:last-child) {
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-color);
  }
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.select-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.item-select {
  flex: 1;
  max-width: 300px;
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
    opacity: 0.7;
    cursor: not-allowed;
  }
}

.btn-action {
  padding: 8px 12px;
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-download {
  background-color: var(--accent-color);
  
  &:hover:not(:disabled) {
    background-color: var(--accent-hover);
  }
}

.btn-delete {
  background-color: var(--danger, #dc3545);
  
  &:hover:not(:disabled) {
    background-color: var(--danger-hover, #c82333);
  }
}

.download-progress {
  margin-top: 10px;
}

.progress-bar {
  height: 8px;
  background-color: var(--bg-primary);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: var(--accent-color);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
