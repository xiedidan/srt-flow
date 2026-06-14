<script setup>
/**
 * Sentence Merge Editor Component
 * 
 * Displays original and merged subtitle entries side by side,
 * allowing users to manually adjust merge results.
 */
import { ref, computed, watch } from 'vue'
import { adjustMergedEntries } from '@/api/tts'

const props = defineProps({
  originalEntries: {
    type: Array,
    required: true,
  },
  mergedEntries: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:mergedEntries', 'regenerate'])

// Local state for merged entries
const localMergedEntries = ref([])

// Selected entry for operations
const selectedIndex = ref(null)

// Edit modal state
const showEditModal = ref(false)
const editingIndex = ref(null)
const editingText = ref('')

// Split modal state
const showSplitModal = ref(false)
const splittingIndex = ref(null)
const splitPosition = ref(0)

// Processing state
const processing = ref(false)

// Initialize local entries from props
watch(() => props.mergedEntries, (newVal) => {
  localMergedEntries.value = JSON.parse(JSON.stringify(newVal))
}, { immediate: true, deep: true })

// Format time for display
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 1000)
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`
}

// Get original entries for a merged entry
function getOriginalTexts(originalIndices) {
  return originalIndices.map(idx => {
    const entry = props.originalEntries.find(e => e.index === idx + 1)
    return entry ? entry.text : ''
  }).filter(t => t)
}

// Check if entry can merge with previous
function canMergeWithPrevious(index) {
  return index > 0
}

// Check if entry can merge with next
function canMergeWithNext(index) {
  return index < localMergedEntries.value.length - 1
}

// Check if entry can be split
function canSplit(index) {
  const entry = localMergedEntries.value[index]
  return entry && entry.merged_text.length > 1
}

// Merge with previous entry
async function mergeWithPrevious(index) {
  if (!canMergeWithPrevious(index) || processing.value) return
  
  processing.value = true
  try {
    const result = await adjustMergedEntries(
      localMergedEntries.value,
      'merge',
      index,
      { mergeWithIndex: index - 1 }
    )
    localMergedEntries.value = result.entries
    emit('update:mergedEntries', result.entries)
    selectedIndex.value = null
  } catch (e) {
    console.error('Failed to merge entries:', e)
  } finally {
    processing.value = false
  }
}

// Merge with next entry
async function mergeWithNext(index) {
  if (!canMergeWithNext(index) || processing.value) return
  
  processing.value = true
  try {
    const result = await adjustMergedEntries(
      localMergedEntries.value,
      'merge',
      index,
      { mergeWithIndex: index + 1 }
    )
    localMergedEntries.value = result.entries
    emit('update:mergedEntries', result.entries)
    selectedIndex.value = null
  } catch (e) {
    console.error('Failed to merge entries:', e)
  } finally {
    processing.value = false
  }
}

// Open edit modal
function openEditModal(index) {
  editingIndex.value = index
  editingText.value = localMergedEntries.value[index].merged_text
  showEditModal.value = true
}

// Save edited text
async function saveEdit() {
  if (processing.value) return
  
  processing.value = true
  try {
    const result = await adjustMergedEntries(
      localMergedEntries.value,
      'edit',
      editingIndex.value,
      { newText: editingText.value }
    )
    localMergedEntries.value = result.entries
    emit('update:mergedEntries', result.entries)
    showEditModal.value = false
  } catch (e) {
    console.error('Failed to edit entry:', e)
  } finally {
    processing.value = false
  }
}

// Open split modal
function openSplitModal(index) {
  splittingIndex.value = index
  const text = localMergedEntries.value[index].merged_text
  splitPosition.value = Math.floor(text.length / 2)
  showSplitModal.value = true
}

// Get split preview
const splitPreview = computed(() => {
  if (splittingIndex.value === null) return { first: '', second: '' }
  const text = localMergedEntries.value[splittingIndex.value]?.merged_text || ''
  return {
    first: text.substring(0, splitPosition.value),
    second: text.substring(splitPosition.value),
  }
})

// Execute split
async function executeSplit() {
  if (processing.value) return
  
  processing.value = true
  try {
    const result = await adjustMergedEntries(
      localMergedEntries.value,
      'split',
      splittingIndex.value,
      { splitAtChar: splitPosition.value }
    )
    localMergedEntries.value = result.entries
    emit('update:mergedEntries', result.entries)
    showSplitModal.value = false
  } catch (e) {
    console.error('Failed to split entry:', e)
  } finally {
    processing.value = false
  }
}

// Toggle selection
function toggleSelect(index) {
  if (selectedIndex.value === index) {
    selectedIndex.value = null
  } else {
    selectedIndex.value = index
  }
}
</script>

<template>
  <div class="sentence-merge-editor">
    <!-- Header Stats -->
    <div class="merge-stats">
      <div class="stat-item">
        <span class="stat-label">原始字幕</span>
        <span class="stat-value">{{ originalEntries.length }} 条</span>
      </div>
      <div class="stat-arrow">→</div>
      <div class="stat-item">
        <span class="stat-label">合并后</span>
        <span class="stat-value highlight">{{ localMergedEntries.length }} 条</span>
      </div>
      <div class="stat-reduction" v-if="originalEntries.length > localMergedEntries.length">
        减少 {{ originalEntries.length - localMergedEntries.length }} 条
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <span>正在执行 AI 句子合并...</span>
    </div>

    <!-- Merged Entries List -->
    <div v-else class="entries-container">
      <div 
        v-for="(entry, index) in localMergedEntries"
        :key="index"
        class="merged-entry"
        :class="{ selected: selectedIndex === index }"
        @click="toggleSelect(index)"
      >
        <div class="entry-header">
          <span class="entry-index">#{{ index + 1 }}</span>
          <span class="entry-time">
            {{ formatTime(entry.start_time) }} - {{ formatTime(entry.end_time) }}
          </span>
          <span class="entry-source" v-if="entry.original_indices.length > 1">
            合并自 {{ entry.original_indices.length }} 条
          </span>
        </div>
        
        <div class="entry-content">
          <div class="merged-text">{{ entry.merged_text }}</div>
          
          <!-- Show original texts if merged from multiple -->
          <div v-if="entry.original_indices.length > 1" class="original-texts">
            <div class="original-label">原始:</div>
            <div 
              v-for="(text, i) in getOriginalTexts(entry.original_indices)"
              :key="i"
              class="original-text-item"
            >
              {{ text }}
            </div>
          </div>
        </div>

        <!-- Action Buttons (shown when selected) -->
        <div v-if="selectedIndex === index" class="entry-actions">
          <button 
            class="action-btn"
            :disabled="!canMergeWithPrevious(index) || processing"
            @click.stop="mergeWithPrevious(index)"
            title="与上一条合并"
          >
            ⬆️ 合并上
          </button>
          <button 
            class="action-btn"
            :disabled="!canMergeWithNext(index) || processing"
            @click.stop="mergeWithNext(index)"
            title="与下一条合并"
          >
            ⬇️ 合并下
          </button>
          <button 
            class="action-btn"
            :disabled="!canSplit(index) || processing"
            @click.stop="openSplitModal(index)"
            title="拆分"
          >
            ✂️ 拆分
          </button>
          <button 
            class="action-btn"
            :disabled="processing"
            @click.stop="openEditModal(index)"
            title="编辑"
          >
            ✏️ 编辑
          </button>
        </div>
      </div>
    </div>

    <!-- Regenerate Button -->
    <div class="regenerate-section">
      <button 
        class="regenerate-btn"
        :disabled="loading || processing"
        @click="emit('regenerate')"
      >
        🔄 重新生成
      </button>
      <span class="regenerate-hint">不满意？重新调用 AI 生成合并结果</span>
    </div>

    <!-- Edit Modal -->
    <Teleport to="body">
      <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
        <div class="modal-content edit-modal">
          <div class="modal-header">
            <h4>编辑文本</h4>
            <button class="close-btn" @click="showEditModal = false">✕</button>
          </div>
          <div class="modal-body">
            <textarea 
              v-model="editingText"
              class="edit-textarea"
              rows="4"
              placeholder="输入合并后的文本..."
            ></textarea>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showEditModal = false">取消</button>
            <button 
              class="btn btn-primary" 
              :disabled="!editingText.trim() || processing"
              @click="saveEdit"
            >
              {{ processing ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Split Modal -->
    <Teleport to="body">
      <div v-if="showSplitModal" class="modal-overlay" @click.self="showSplitModal = false">
        <div class="modal-content split-modal">
          <div class="modal-header">
            <h4>拆分句子</h4>
            <button class="close-btn" @click="showSplitModal = false">✕</button>
          </div>
          <div class="modal-body">
            <div class="split-preview">
              <div class="split-part first">
                <span class="part-label">第一部分</span>
                <div class="part-text">{{ splitPreview.first || '(空)' }}</div>
              </div>
              <div class="split-divider">|</div>
              <div class="split-part second">
                <span class="part-label">第二部分</span>
                <div class="part-text">{{ splitPreview.second || '(空)' }}</div>
              </div>
            </div>
            <div class="split-slider">
              <label>拆分位置: {{ splitPosition }}</label>
              <input 
                type="range"
                v-model.number="splitPosition"
                :min="1"
                :max="localMergedEntries[splittingIndex]?.merged_text.length - 1 || 1"
                class="slider"
              />
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showSplitModal = false">取消</button>
            <button 
              class="btn btn-primary" 
              :disabled="processing"
              @click="executeSplit"
            >
              {{ processing ? '拆分中...' : '确认拆分' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>


<style lang="scss" scoped>
.sentence-merge-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.merge-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  
  .stat-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    
    .stat-label {
      font-size: 12px;
      color: var(--text-muted);
    }
    
    .stat-value {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      
      &.highlight {
        color: var(--accent-color);
      }
    }
  }
  
  .stat-arrow {
    font-size: 20px;
    color: var(--text-muted);
  }
  
  .stat-reduction {
    margin-left: auto;
    padding: 4px 10px;
    background-color: rgba(34, 197, 94, 0.1);
    color: var(--success, #22c55e);
    border-radius: 12px;
    font-size: 12px;
  }
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  gap: 16px;
  color: var(--text-muted);
  
  .loading-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.entries-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}

.merged-entry {
  padding: 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  &.selected {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.05);
  }
}

.entry-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  
  .entry-index {
    font-size: 12px;
    font-weight: 600;
    color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.1);
    padding: 2px 8px;
    border-radius: 4px;
  }
  
  .entry-time {
    font-size: 11px;
    color: var(--text-muted);
    font-family: monospace;
  }
  
  .entry-source {
    font-size: 11px;
    color: var(--success, #22c55e);
    margin-left: auto;
  }
}

.entry-content {
  .merged-text {
    font-size: 14px;
    color: var(--text-primary);
    line-height: 1.5;
  }
  
  .original-texts {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px dashed var(--border-color);
    
    .original-label {
      font-size: 11px;
      color: var(--text-muted);
      margin-bottom: 4px;
    }
    
    .original-text-item {
      font-size: 12px;
      color: var(--text-secondary);
      padding: 2px 0;
      padding-left: 8px;
      border-left: 2px solid var(--border-color);
      margin-bottom: 2px;
    }
  }
}

.entry-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  
  .action-btn {
    padding: 6px 12px;
    font-size: 12px;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    
    &:hover:not(:disabled) {
      border-color: var(--accent-color);
      color: var(--accent-color);
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
}

.regenerate-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  
  .regenerate-btn {
    padding: 8px 16px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-secondary);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    
    &:hover:not(:disabled) {
      border-color: var(--accent-color);
      color: var(--accent-color);
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
  
  .regenerate-hint {
    font-size: 12px;
    color: var(--text-muted);
  }
}

// Modal styles
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.modal-content {
  background-color: var(--bg-secondary);
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  
  h4 {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
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
}

.modal-body {
  padding: 20px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.edit-textarea {
  width: 100%;
  padding: 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  resize: vertical;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.split-preview {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  
  .split-part {
    flex: 1;
    padding: 12px;
    background-color: var(--bg-primary);
    border-radius: 6px;
    
    .part-label {
      display: block;
      font-size: 11px;
      color: var(--text-muted);
      margin-bottom: 4px;
    }
    
    .part-text {
      font-size: 13px;
      color: var(--text-primary);
      word-break: break-all;
    }
  }
  
  .split-divider {
    display: flex;
    align-items: center;
    font-size: 20px;
    color: var(--accent-color);
  }
}

.split-slider {
  label {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }
  
  .slider {
    width: 100%;
    height: 6px;
    -webkit-appearance: none;
    appearance: none;
    background: var(--bg-primary);
    border-radius: 3px;
    outline: none;
    
    &::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 18px;
      height: 18px;
      background: var(--accent-color);
      border-radius: 50%;
      cursor: pointer;
    }
    
    &::-moz-range-thumb {
      width: 18px;
      height: 18px;
      background: var(--accent-color);
      border-radius: 50%;
      cursor: pointer;
      border: none;
    }
  }
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
    
    &:hover:not(:disabled) {
      background-color: var(--border-color);
    }
  }
}
</style>
