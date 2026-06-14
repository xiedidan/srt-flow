<script setup>
/**
 * Reference Audio Manager Component
 * 
 * Manages TTS reference audio files for voice cloning.
 * Supports upload, playback, edit description, and delete.
 */
import { ref, onMounted, computed } from 'vue'
import {
  listReferenceAudios,
  uploadReferenceAudio,
  updateReferenceAudio,
  deleteReferenceAudio,
  getAudioStreamUrl
} from '@/api/referenceAudio'

// State
const audios = ref([])
const loading = ref(false)
const uploading = ref(false)
const error = ref(null)

// Edit modal state
const editingAudio = ref(null)
const editName = ref('')
const editDescription = ref('')
const editEmotion = ref('')
const editContent = ref('')
const saving = ref(false)

// Upload modal state
const showUploadModal = ref(false)
const uploadName = ref('')
const uploadDescription = ref('')
const uploadEmotion = ref('')
const uploadContent = ref('')
const selectedFile = ref(null)

// Delete confirmation state
const deletingAudio = ref(null)
const deleting = ref(false)

// Audio player state
const playingId = ref(null)
const audioElement = ref(null)

// File input ref
const fileInput = ref(null)

// Computed
const hasAudios = computed(() => audios.value.length > 0)

// Methods
async function loadAudios() {
  loading.value = true
  error.value = null
  try {
    audios.value = await listReferenceAudios()
  } catch (e) {
    error.value = e.message || '加载失败'
    console.error('Failed to load reference audios:', e)
  } finally {
    loading.value = false
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (!file) return
  
  // Reset input
  event.target.value = ''
  
  // Validate file type
  const allowedTypes = ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/flac', 'audio/ogg', 'audio/aac', 'audio/x-m4a']
  if (!allowedTypes.includes(file.type) && !file.name.match(/\.(wav|mp3|m4a|flac|ogg|aac)$/i)) {
    error.value = '不支持的文件格式，请上传 WAV、MP3、M4A、FLAC、OGG 或 AAC 格式'
    return
  }
  
  // Validate file size (50MB)
  if (file.size > 50 * 1024 * 1024) {
    error.value = '文件过大，最大支持 50MB'
    return
  }
  
  // Show upload modal for entering name and other info
  selectedFile.value = file
  uploadName.value = file.name.replace(/\.[^/.]+$/, '') // Default name from filename
  uploadDescription.value = ''
  uploadEmotion.value = ''
  uploadContent.value = ''
  showUploadModal.value = true
}

function closeUploadModal() {
  showUploadModal.value = false
  selectedFile.value = null
  uploadName.value = ''
  uploadDescription.value = ''
  uploadEmotion.value = ''
  uploadContent.value = ''
}

async function confirmUpload() {
  if (!selectedFile.value || !uploadName.value.trim()) {
    error.value = '请填写名称'
    return
  }
  
  uploading.value = true
  error.value = null
  
  try {
    const newAudio = await uploadReferenceAudio(selectedFile.value, uploadName.value.trim(), {
      description: uploadDescription.value.trim() || undefined,
      emotion: uploadEmotion.value.trim() || undefined,
      content: uploadContent.value.trim() || undefined
    })
    audios.value.unshift(newAudio)
    closeUploadModal()
  } catch (e) {
    error.value = e.message || '上传失败'
    console.error('Failed to upload reference audio:', e)
  } finally {
    uploading.value = false
  }
}

function formatDuration(seconds) {
  if (!seconds) return '--:--'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatSampleRate(rate) {
  if (!rate) return '--'
  return `${(rate / 1000).toFixed(1)} kHz`
}

// Playback
function togglePlay(audio) {
  if (playingId.value === audio.id) {
    // Stop playing
    if (audioElement.value) {
      audioElement.value.pause()
      audioElement.value = null
    }
    playingId.value = null
  } else {
    // Stop previous
    if (audioElement.value) {
      audioElement.value.pause()
    }
    
    // Start new
    const url = getAudioStreamUrl(audio.id)
    audioElement.value = new Audio(url)
    audioElement.value.play()
    playingId.value = audio.id
    
    // Handle end
    audioElement.value.onended = () => {
      playingId.value = null
      audioElement.value = null
    }
    
    // Handle error
    audioElement.value.onerror = () => {
      error.value = '播放失败'
      playingId.value = null
      audioElement.value = null
    }
  }
}

// Edit
function openEdit(audio) {
  editingAudio.value = audio
  editName.value = audio.name || ''
  editDescription.value = audio.description || ''
  editEmotion.value = audio.emotion || ''
  editContent.value = audio.content || ''
}

function closeEdit() {
  editingAudio.value = null
  editName.value = ''
  editDescription.value = ''
  editEmotion.value = ''
  editContent.value = ''
}

async function saveEdit() {
  if (!editingAudio.value) return
  if (!editName.value.trim()) {
    error.value = '名称不能为空'
    return
  }
  
  saving.value = true
  try {
    const updated = await updateReferenceAudio(editingAudio.value.id, {
      name: editName.value.trim(),
      description: editDescription.value.trim() || null,
      emotion: editEmotion.value.trim() || null,
      content: editContent.value.trim() || null
    })
    // Update in list
    const index = audios.value.findIndex(a => a.id === updated.id)
    if (index !== -1) {
      audios.value[index] = updated
    }
    closeEdit()
  } catch (e) {
    error.value = e.message || '保存失败'
    console.error('Failed to update reference audio:', e)
  } finally {
    saving.value = false
  }
}

// Delete
function confirmDelete(audio) {
  deletingAudio.value = audio
}

function cancelDelete() {
  deletingAudio.value = null
}

async function executeDelete() {
  if (!deletingAudio.value) return
  
  deleting.value = true
  try {
    await deleteReferenceAudio(deletingAudio.value.id)
    // Remove from list
    audios.value = audios.value.filter(a => a.id !== deletingAudio.value.id)
    cancelDelete()
  } catch (e) {
    error.value = e.message || '删除失败'
    console.error('Failed to delete reference audio:', e)
  } finally {
    deleting.value = false
  }
}

// Lifecycle
onMounted(() => {
  loadAudios()
})
</script>

<template>
  <div class="reference-audio-manager">
    <!-- Header -->
    <div class="manager-header">
      <div class="header-info">
        <p class="description">
          管理用于语音克隆的参考音频文件。上传清晰的人声音频（建议 5-30 秒），TTS 引擎将模仿该音色进行语音合成。
        </p>
      </div>
      <button class="btn btn-primary" @click="triggerUpload" :disabled="uploading">
        <span v-if="uploading" class="spinner"></span>
        <span v-else>📤</span>
        {{ uploading ? '上传中...' : '上传音频' }}
      </button>
      <input
        ref="fileInput"
        type="file"
        accept=".wav,.mp3,.m4a,.flac,.ogg,.aac,audio/*"
        style="display: none"
        @change="handleFileSelect"
      />
    </div>

    <!-- Error message -->
    <div v-if="error" class="error-message">
      {{ error }}
      <button class="close-btn" @click="error = null">×</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>加载中...</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="!hasAudios" class="empty-state">
      <div class="empty-icon">🎵</div>
      <p>暂无参考音频</p>
      <p class="hint">点击上方按钮上传音频文件</p>
    </div>

    <!-- Audio list -->
    <div v-else class="audio-list">
      <div
        v-for="audio in audios"
        :key="audio.id"
        class="audio-item"
      >
        <div class="audio-info">
          <div class="audio-name">{{ audio.name }}</div>
          <div class="audio-filename">{{ audio.original_filename }}</div>
          <div class="audio-meta">
            <span class="meta-item">⏱️ {{ formatDuration(audio.duration) }}</span>
            <span class="meta-item">📊 {{ formatSampleRate(audio.sample_rate) }}</span>
            <span class="meta-item">💾 {{ formatFileSize(audio.file_size) }}</span>
            <span v-if="audio.emotion" class="meta-item">🎭 {{ audio.emotion }}</span>
          </div>
          <div v-if="audio.description" class="audio-description">
            {{ audio.description }}
          </div>
          <div v-if="audio.content" class="audio-content">
            📝 {{ audio.content }}
          </div>
        </div>
        
        <div class="audio-actions">
          <button
            class="action-btn play-btn"
            :class="{ playing: playingId === audio.id }"
            @click="togglePlay(audio)"
            :title="playingId === audio.id ? '停止' : '试听'"
          >
            {{ playingId === audio.id ? '⏹️' : '▶️' }}
          </button>
          <button
            class="action-btn edit-btn"
            @click="openEdit(audio)"
            title="编辑"
          >
            ✏️
          </button>
          <button
            class="action-btn delete-btn"
            @click="confirmDelete(audio)"
            title="删除"
          >
            🗑️
          </button>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <div v-if="editingAudio" class="modal-overlay" @click.self="closeEdit">
      <div class="modal">
        <div class="modal-header">
          <h3>编辑参考音频</h3>
          <button class="close-btn" @click="closeEdit">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>文件名</label>
            <div class="readonly-value">{{ editingAudio.original_filename }}</div>
          </div>
          <div class="form-group">
            <label for="edit-name">名称 <span class="required">*</span></label>
            <input
              id="edit-name"
              type="text"
              v-model="editName"
              placeholder="输入音频名称"
              maxlength="100"
            />
          </div>
          <div class="form-group">
            <label for="edit-emotion">情绪</label>
            <input
              id="edit-emotion"
              type="text"
              v-model="editEmotion"
              placeholder="如：开心、悲伤、平静、激动等"
              maxlength="50"
            />
          </div>
          <div class="form-group">
            <label for="edit-content">内容</label>
            <textarea
              id="edit-content"
              v-model="editContent"
              placeholder="音频中说的文字内容"
              rows="2"
              maxlength="2000"
            ></textarea>
          </div>
          <div class="form-group">
            <label for="edit-description">描述</label>
            <textarea
              id="edit-description"
              v-model="editDescription"
              placeholder="其他描述信息，如：男声、女声、特定角色等"
              rows="2"
              maxlength="500"
            ></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeEdit" :disabled="saving">
            取消
          </button>
          <button class="btn btn-primary" @click="saveEdit" :disabled="saving || !editName.trim()">
            <span v-if="saving" class="spinner small"></span>
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Upload Modal -->
    <div v-if="showUploadModal" class="modal-overlay" @click.self="closeUploadModal">
      <div class="modal">
        <div class="modal-header">
          <h3>上传参考音频</h3>
          <button class="close-btn" @click="closeUploadModal">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>文件</label>
            <div class="readonly-value">{{ selectedFile?.name }}</div>
          </div>
          <div class="form-group">
            <label for="upload-name">名称 <span class="required">*</span></label>
            <input
              id="upload-name"
              type="text"
              v-model="uploadName"
              placeholder="输入音频名称"
              maxlength="100"
            />
          </div>
          <div class="form-group">
            <label for="upload-emotion">情绪</label>
            <input
              id="upload-emotion"
              type="text"
              v-model="uploadEmotion"
              placeholder="如：开心、悲伤、平静、激动等"
              maxlength="50"
            />
          </div>
          <div class="form-group">
            <label for="upload-content">内容</label>
            <textarea
              id="upload-content"
              v-model="uploadContent"
              placeholder="音频中说的文字内容"
              rows="2"
              maxlength="2000"
            ></textarea>
          </div>
          <div class="form-group">
            <label for="upload-description">描述</label>
            <textarea
              id="upload-description"
              v-model="uploadDescription"
              placeholder="其他描述信息，如：男声、女声、特定角色等"
              rows="2"
              maxlength="500"
            ></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeUploadModal" :disabled="uploading">
            取消
          </button>
          <button class="btn btn-primary" @click="confirmUpload" :disabled="uploading || !uploadName.trim()">
            <span v-if="uploading" class="spinner small"></span>
            {{ uploading ? '上传中...' : '上传' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="deletingAudio" class="modal-overlay" @click.self="cancelDelete">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3>确认删除</h3>
          <button class="close-btn" @click="cancelDelete">×</button>
        </div>
        <div class="modal-body">
          <p>确定要删除音频文件 <strong>{{ deletingAudio.original_filename }}</strong> 吗？</p>
          <p class="warning">此操作不可恢复。</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="cancelDelete" :disabled="deleting">
            取消
          </button>
          <button class="btn btn-danger" @click="executeDelete" :disabled="deleting">
            <span v-if="deleting" class="spinner small"></span>
            {{ deleting ? '删除中...' : '删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>


<style lang="scss" scoped>
.reference-audio-manager {
  .manager-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
    gap: 16px;
    
    .header-info {
      flex: 1;
    }
    
    .description {
      color: var(--text-secondary);
      font-size: 14px;
      margin: 0;
      line-height: 1.5;
    }
  }
  
  .error-message {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    color: #ef4444;
    margin-bottom: 16px;
    
    .close-btn {
      background: none;
      border: none;
      color: inherit;
      font-size: 18px;
      cursor: pointer;
      padding: 0 4px;
      
      &:hover {
        opacity: 0.7;
      }
    }
  }
  
  .loading-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: var(--text-secondary);
    
    .empty-icon {
      font-size: 48px;
      margin-bottom: 16px;
    }
    
    p {
      margin: 4px 0;
    }
    
    .hint {
      font-size: 13px;
      opacity: 0.7;
    }
  }
  
  .audio-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .audio-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    transition: border-color 0.2s;
    
    &:hover {
      border-color: var(--primary-color);
    }
  }
  
  .audio-info {
    flex: 1;
    min-width: 0;
    
    .audio-name {
      font-weight: 600;
      font-size: 15px;
      color: var(--text-primary);
      margin-bottom: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .audio-filename {
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 6px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .audio-meta {
      display: flex;
      gap: 16px;
      font-size: 13px;
      color: var(--text-secondary);
      
      .meta-item {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
    
    .audio-description {
      margin-top: 8px;
      font-size: 13px;
      color: var(--text-secondary);
      font-style: italic;
    }
    
    .audio-content {
      margin-top: 6px;
      font-size: 13px;
      color: var(--text-secondary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
  
  .audio-actions {
    display: flex;
    gap: 8px;
    margin-left: 16px;
  }
  
  .action-btn {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 8px;
    background-color: var(--bg-secondary);
    cursor: pointer;
    font-size: 16px;
    transition: all 0.2s;
    
    &:hover {
      background-color: var(--primary-color);
      transform: scale(1.05);
    }
    
    &.play-btn.playing {
      background-color: var(--primary-color);
      animation: pulse 1s infinite;
    }
    
    &.delete-btn:hover {
      background-color: #ef4444;
    }
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
  
  // Buttons
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    
    &.btn-primary {
      background-color: var(--primary-color);
      color: white;
      
      &:hover:not(:disabled) {
        filter: brightness(1.1);
      }
    }
    
    &.btn-secondary {
      background-color: var(--bg-tertiary);
      color: var(--text-primary);
      
      &:hover:not(:disabled) {
        background-color: var(--border-color);
      }
    }
    
    &.btn-danger {
      background-color: #ef4444;
      color: white;
      
      &:hover:not(:disabled) {
        background-color: #dc2626;
      }
    }
  }
  
  // Spinner
  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    
    &.small {
      width: 14px;
      height: 14px;
    }
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  // Modal
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  
  .modal {
    background-color: var(--bg-secondary);
    border-radius: 12px;
    width: 100%;
    max-width: 480px;
    max-height: 90vh;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
    
    &.modal-small {
      max-width: 400px;
    }
  }
  
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
    
    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }
    
    .close-btn {
      background: none;
      border: none;
      font-size: 24px;
      color: var(--text-secondary);
      cursor: pointer;
      padding: 0;
      line-height: 1;
      
      &:hover {
        color: var(--text-primary);
      }
    }
  }
  
  .modal-body {
    padding: 20px;
    max-height: 60vh;
    overflow-y: auto;
    
    .form-group {
      margin-bottom: 16px;
      
      &:last-child {
        margin-bottom: 0;
      }
      
      label {
        display: block;
        font-size: 14px;
        font-weight: 500;
        color: var(--text-secondary);
        margin-bottom: 8px;
        
        .required {
          color: #ef4444;
        }
      }
      
      .readonly-value {
        padding: 10px 12px;
        background-color: var(--bg-tertiary);
        border-radius: 6px;
        font-size: 14px;
        color: var(--text-primary);
      }
      
      input[type="text"] {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--border-color);
        border-radius: 6px;
        background-color: var(--bg-primary);
        color: var(--text-primary);
        font-size: 14px;
        
        &:focus {
          outline: none;
          border-color: var(--primary-color);
        }
        
        &::placeholder {
          color: var(--text-secondary);
          opacity: 0.6;
        }
      }
      
      textarea {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--border-color);
        border-radius: 6px;
        background-color: var(--bg-primary);
        color: var(--text-primary);
        font-size: 14px;
        resize: vertical;
        
        &:focus {
          outline: none;
          border-color: var(--primary-color);
        }
        
        &::placeholder {
          color: var(--text-secondary);
          opacity: 0.6;
        }
      }
    }
    
    .warning {
      color: #ef4444;
      font-size: 13px;
      margin-top: 8px;
    }
  }
  
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    padding: 16px 20px;
    border-top: 1px solid var(--border-color);
  }
}
</style>
