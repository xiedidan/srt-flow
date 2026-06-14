<script setup>
/**
 * Subtitle editor component with timeline adjustment
 * Features:
 * - Click to edit subtitle text inline
 * - Right-click context menu for merge/split operations
 * - Auto-scroll to current subtitle
 */
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  subtitles: {
    type: Array,
    default: () => []
  },
  currentTime: {
    type: Number,
    default: 0
  },
  readonly: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update', 'seek', 'save'])

const editingIndex = ref(-1)
const editForm = ref({ start: '', end: '', text: '' })
const listRef = ref(null)
const hasChanges = ref(false)

// Context menu state
const contextMenu = ref({
  show: false,
  x: 0,
  y: 0,
  index: -1
})

// Split modal state
const splitModal = ref({
  show: false,
  index: -1,
  text: '',
  splitPosition: 0
})

// Local copy of subtitles for editing
const localSubtitles = ref([])

watch(() => props.subtitles, (newVal) => {
  localSubtitles.value = JSON.parse(JSON.stringify(newVal || []))
  hasChanges.value = false
}, { immediate: true, deep: true })

// Current subtitle index based on time
const currentIndex = computed(() => {
  const time = props.currentTime
  return localSubtitles.value.findIndex(s => time >= s.start && time <= s.end)
})

// Auto-scroll to current subtitle
watch(currentIndex, async (idx) => {
  if (idx >= 0 && listRef.value && editingIndex.value === -1) {
    await nextTick()
    const item = listRef.value.querySelector(`[data-index="${idx}"]`)
    if (item) {
      item.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
})

// Format time for display (seconds to HH:MM:SS,mmm)
function formatSrtTime(seconds) {
  if (seconds === undefined || seconds === null || isNaN(seconds)) return '00:00:00,000'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`
}

// Parse SRT time to seconds
function parseSrtTime(timeStr) {
  const match = timeStr.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})/)
  if (!match) return 0
  const [, h, m, s, ms] = match.map(Number)
  return h * 3600 + m * 60 + s + ms / 1000
}

// Format time for display (short format)
function formatTimeShort(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// Click to edit subtitle text directly
function handleTextClick(index) {
  if (props.readonly) return
  startEdit(index)
}

// Start editing a subtitle
function startEdit(index) {
  if (props.readonly) return
  const sub = localSubtitles.value[index]
  editingIndex.value = index
  editForm.value = {
    start: formatSrtTime(sub.start),
    end: formatSrtTime(sub.end),
    text: sub.original || sub.text || ''
  }
  // Focus textarea after render
  nextTick(() => {
    const textarea = document.querySelector('.edit-textarea')
    if (textarea) {
      textarea.focus()
      textarea.select()
    }
  })
}

// Save edit
function saveEdit() {
  if (editingIndex.value < 0) return
  
  const start = parseSrtTime(editForm.value.start)
  const end = parseSrtTime(editForm.value.end)
  
  if (end <= start) {
    alert('结束时间必须大于开始时间')
    return
  }
  
  localSubtitles.value[editingIndex.value] = {
    ...localSubtitles.value[editingIndex.value],
    start,
    end,
    original: editForm.value.text,
    text: editForm.value.text
  }
  
  hasChanges.value = true
  editingIndex.value = -1
  emit('update', localSubtitles.value)
}

// Cancel edit
function cancelEdit() {
  editingIndex.value = -1
}

// Handle blur - save on blur
function handleEditBlur(event) {
  // Don't save if clicking on time inputs or action buttons
  const relatedTarget = event.relatedTarget
  if (relatedTarget && (
    relatedTarget.classList.contains('time-input') ||
    relatedTarget.classList.contains('edit-btn')
  )) {
    return
  }
  saveEdit()
}

// Right-click context menu
function handleContextMenu(event, index) {
  if (props.readonly) return
  event.preventDefault()
  
  contextMenu.value = {
    show: true,
    x: event.clientX,
    y: event.clientY,
    index
  }
}

// Close context menu
function closeContextMenu() {
  contextMenu.value.show = false
}

// Handle click outside to close context menu
function handleClickOutside(event) {
  if (contextMenu.value.show) {
    closeContextMenu()
  }
}

// Check if text contains Chinese characters
function containsChinese(text) {
  return /[\u4e00-\u9fa5]/.test(text)
}

// Merge two texts with appropriate separator (no space for Chinese)
function mergeTexts(text1, text2) {
  const t1 = (text1 || '').trim()
  const t2 = (text2 || '').trim()
  if (!t1) return t2
  if (!t2) return t1
  // If either text contains Chinese, don't add space
  const separator = (containsChinese(t1) || containsChinese(t2)) ? '' : ' '
  return t1 + separator + t2
}

// Merge with previous subtitle
function mergeWithPrevious() {
  const index = contextMenu.value.index
  if (index <= 0) return
  
  const current = localSubtitles.value[index]
  const previous = localSubtitles.value[index - 1]
  
  // Merge text with appropriate separator
  const mergedText = mergeTexts(previous.original || previous.text, current.original || current.text)
  
  // Update previous subtitle
  localSubtitles.value[index - 1] = {
    ...previous,
    end: current.end,
    original: mergedText,
    text: mergedText
  }
  
  // Remove current subtitle
  localSubtitles.value.splice(index, 1)
  
  // Re-index
  reindexSubtitles()
  
  hasChanges.value = true
  closeContextMenu()
  emit('update', localSubtitles.value)
  // Auto save after merge
  emit('save', localSubtitles.value)
}

// Merge with next subtitle
function mergeWithNext() {
  const index = contextMenu.value.index
  if (index >= localSubtitles.value.length - 1) return
  
  const current = localSubtitles.value[index]
  const next = localSubtitles.value[index + 1]
  
  // Merge text with appropriate separator
  const mergedText = mergeTexts(current.original || current.text, next.original || next.text)
  
  // Update current subtitle
  localSubtitles.value[index] = {
    ...current,
    end: next.end,
    original: mergedText,
    text: mergedText
  }
  
  // Remove next subtitle
  localSubtitles.value.splice(index + 1, 1)
  
  // Re-index
  reindexSubtitles()
  
  hasChanges.value = true
  closeContextMenu()
  emit('update', localSubtitles.value)
  // Auto save after merge
  emit('save', localSubtitles.value)
}

// Open split modal
function openSplitModal() {
  const index = contextMenu.value.index
  const sub = localSubtitles.value[index]
  const text = sub.original || sub.text || ''
  
  splitModal.value = {
    show: true,
    index,
    text,
    splitPosition: Math.floor(text.length / 2)
  }
  closeContextMenu()
}

// Handle split position change via click on text
function handleSplitClick(event) {
  const text = splitModal.value.text
  if (!text) return
  
  // Use caretPositionFromPoint or caretRangeFromPoint to get exact character position
  let position = 0
  
  if (document.caretPositionFromPoint) {
    // Firefox
    const pos = document.caretPositionFromPoint(event.clientX, event.clientY)
    if (pos) {
      position = pos.offset
    }
  } else if (document.caretRangeFromPoint) {
    // Chrome, Safari, Edge
    const range = document.caretRangeFromPoint(event.clientX, event.clientY)
    if (range) {
      position = range.startOffset
    }
  }
  
  // Clamp position to valid range
  position = Math.max(1, Math.min(text.length - 1, position))
  splitModal.value.splitPosition = position
}

// Get split preview texts
const splitPreview = computed(() => {
  const { text, splitPosition } = splitModal.value
  return {
    first: text.substring(0, splitPosition),
    second: text.substring(splitPosition)
  }
})

// Execute split
function executeSplit() {
  const { index, text, splitPosition } = splitModal.value
  
  if (splitPosition <= 0 || splitPosition >= text.length) {
    alert('请选择有效的切割位置')
    return
  }
  
  const sub = localSubtitles.value[index]
  const firstText = text.substring(0, splitPosition).trim()
  const secondText = text.substring(splitPosition).trim()
  
  if (!firstText || !secondText) {
    alert('切割后的字幕不能为空')
    return
  }
  
  // Calculate time split based on character ratio
  const totalDuration = sub.end - sub.start
  const ratio = firstText.length / text.length
  const splitTime = sub.start + totalDuration * ratio
  
  // Create two new subtitles
  const firstSub = {
    ...sub,
    end: splitTime,
    original: firstText,
    text: firstText
  }
  
  const secondSub = {
    ...sub,
    index: sub.index + 1,
    start: splitTime,
    original: secondText,
    text: secondText
  }
  
  // Replace current with two new subtitles
  localSubtitles.value.splice(index, 1, firstSub, secondSub)
  
  // Re-index
  reindexSubtitles()
  
  hasChanges.value = true
  splitModal.value.show = false
  emit('update', localSubtitles.value)
  // Auto save after split
  emit('save', localSubtitles.value)
}

// Cancel split
function cancelSplit() {
  splitModal.value.show = false
}

// Re-index all subtitles
function reindexSubtitles() {
  localSubtitles.value.forEach((s, i) => {
    s.index = i + 1
  })
}

// Delete subtitle
function deleteSubtitle(index) {
  if (props.readonly) return
  if (!confirm('确定删除这条字幕吗？')) return
  
  localSubtitles.value.splice(index, 1)
  reindexSubtitles()
  hasChanges.value = true
  emit('update', localSubtitles.value)
}

// Add new subtitle
function addSubtitle() {
  if (props.readonly) return
  
  const lastSub = localSubtitles.value[localSubtitles.value.length - 1]
  const newStart = lastSub ? lastSub.end + 0.1 : props.currentTime
  
  const newSub = {
    index: localSubtitles.value.length + 1,
    start: newStart,
    end: newStart + 3,
    original: '',
    translated: '',
    text: ''
  }
  
  localSubtitles.value.push(newSub)
  hasChanges.value = true
  emit('update', localSubtitles.value)
  
  nextTick(() => {
    startEdit(localSubtitles.value.length - 1)
  })
}

// Insert subtitle at current time
function insertAtCurrentTime() {
  if (props.readonly) return
  
  const time = props.currentTime
  let insertIndex = localSubtitles.value.findIndex(s => s.start > time)
  if (insertIndex === -1) insertIndex = localSubtitles.value.length
  
  const newSub = {
    index: insertIndex + 1,
    start: time,
    end: time + 3,
    original: '',
    translated: '',
    text: ''
  }
  
  localSubtitles.value.splice(insertIndex, 0, newSub)
  reindexSubtitles()
  
  hasChanges.value = true
  emit('update', localSubtitles.value)
  
  nextTick(() => {
    startEdit(insertIndex)
  })
}

// Offset all subtitles
const offsetValue = ref(0)
function applyOffset() {
  if (props.readonly || offsetValue.value === 0) return
  
  const offset = parseFloat(offsetValue.value)
  localSubtitles.value.forEach(sub => {
    sub.start = Math.max(0, sub.start + offset)
    sub.end = Math.max(0, sub.end + offset)
  })
  
  hasChanges.value = true
  offsetValue.value = 0
  emit('update', localSubtitles.value)
}

// Seek to subtitle
function seekTo(sub) {
  emit('seek', sub.start)
}

// Save all changes
function saveAll() {
  emit('save', localSubtitles.value)
}

// Export to SRT format
function exportSrt() {
  let srt = ''
  localSubtitles.value.forEach((sub, i) => {
    srt += `${i + 1}\n`
    srt += `${formatSrtTime(sub.start)} --> ${formatSrtTime(sub.end)}\n`
    srt += `${sub.original || sub.text || ''}\n\n`
  })
  
  const blob = new Blob([srt], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'subtitle.srt'
  a.click()
  URL.revokeObjectURL(url)
}

// Lifecycle
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

defineExpose({
  hasChanges,
  saveAll,
  exportSrt
})
</script>

<template>
  <div class="subtitle-editor">
    <!-- Toolbar -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <button 
          v-if="!readonly" 
          class="toolbar-btn" 
          @click="addSubtitle"
          title="添加字幕"
        >
          ➕ 添加
        </button>
        <button 
          v-if="!readonly" 
          class="toolbar-btn" 
          @click="insertAtCurrentTime"
          title="在当前时间插入"
        >
          📍 插入
        </button>
      </div>
      
      <div v-if="!readonly" class="toolbar-center">
        <span class="offset-label">时间偏移:</span>
        <input 
          v-model.number="offsetValue" 
          type="number" 
          step="0.1" 
          class="offset-input"
          placeholder="秒"
        />
        <button class="toolbar-btn small" @click="applyOffset">应用</button>
      </div>
      
      <div class="toolbar-right">
        <button class="toolbar-btn" @click="exportSrt" title="导出SRT">
          📥 导出
        </button>
        <button 
          v-if="!readonly && hasChanges" 
          class="toolbar-btn primary" 
          @click="saveAll"
        >
          💾 保存
        </button>
      </div>
    </div>
    
    <!-- Subtitle list -->
    <div ref="listRef" class="subtitle-list">
      <div 
        v-for="(sub, index) in localSubtitles" 
        :key="index"
        :data-index="index"
        class="subtitle-item"
        :class="{ 
          current: index === currentIndex,
          editing: index === editingIndex 
        }"
        @contextmenu="handleContextMenu($event, index)"
      >
        <!-- View mode -->
        <template v-if="editingIndex !== index">
          <div class="sub-index">{{ index + 1 }}</div>
          <div class="sub-time" @click="seekTo(sub)">
            <span class="time-start">{{ formatTimeShort(sub.start) }}</span>
            <span class="time-sep">→</span>
            <span class="time-end">{{ formatTimeShort(sub.end) }}</span>
          </div>
          <div 
            class="sub-text" 
            @click="handleTextClick(index)"
            :title="readonly ? '' : '点击编辑，右键更多操作'"
          >
            {{ sub.original || sub.text || '(空)' }}
          </div>
          <div v-if="!readonly" class="sub-actions">
            <button class="action-btn danger" @click="deleteSubtitle(index)" title="删除">🗑️</button>
          </div>
        </template>
        
        <!-- Edit mode -->
        <template v-else>
          <div class="sub-index">{{ index + 1 }}</div>
          <div class="edit-form">
            <div class="edit-row time-row">
              <label>开始:</label>
              <input 
                v-model="editForm.start" 
                type="text" 
                class="time-input"
                placeholder="00:00:00,000" 
              />
              <label>结束:</label>
              <input 
                v-model="editForm.end" 
                type="text" 
                class="time-input"
                placeholder="00:00:00,000" 
              />
            </div>
            <div class="edit-row">
              <textarea 
                v-model="editForm.text" 
                class="edit-textarea"
                rows="2" 
                placeholder="字幕内容"
                @keydown.ctrl.enter="saveEdit"
                @keydown.escape="cancelEdit"
                @blur="handleEditBlur"
              ></textarea>
            </div>
            <div class="edit-actions">
              <button class="edit-btn save" @click="saveEdit">保存</button>
              <button class="edit-btn cancel" @click="cancelEdit">取消</button>
            </div>
          </div>
        </template>
      </div>
      
      <div v-if="localSubtitles.length === 0" class="empty-list">
        暂无字幕
      </div>
    </div>
    
    <!-- Context Menu -->
    <Teleport to="body">
      <div 
        v-if="contextMenu.show" 
        class="context-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
        @click.stop
      >
        <div 
          class="context-menu-item"
          :class="{ disabled: contextMenu.index <= 0 }"
          @click="contextMenu.index > 0 && mergeWithPrevious()"
        >
          ⬆️ 向上合并
        </div>
        <div 
          class="context-menu-item"
          :class="{ disabled: contextMenu.index >= localSubtitles.length - 1 }"
          @click="contextMenu.index < localSubtitles.length - 1 && mergeWithNext()"
        >
          ⬇️ 向下合并
        </div>
        <div class="context-menu-divider"></div>
        <div 
          class="context-menu-item"
          @click="openSplitModal()"
        >
          ✂️ 切割句子
        </div>
        <div class="context-menu-divider"></div>
        <div 
          class="context-menu-item danger"
          @click="deleteSubtitle(contextMenu.index); closeContextMenu()"
        >
          🗑️ 删除
        </div>
      </div>
    </Teleport>
    
    <!-- Split Modal -->
    <Teleport to="body">
      <div v-if="splitModal.show" class="modal-overlay" @click.self="cancelSplit">
        <div class="split-modal">
          <div class="modal-header">
            <h3>✂️ 切割字幕</h3>
            <button class="close-btn" @click="cancelSplit">✕</button>
          </div>
          <div class="modal-body">
            <p class="split-hint">点击文字选择切割位置，或拖动滑块调整</p>
            
            <div class="split-text-container">
              <div class="split-text-clickable" @click="handleSplitClick">{{ splitModal.text }}</div>
              <div class="split-text-preview">
                <span class="split-first">{{ splitPreview.first }}</span>
                <span class="split-cursor">|</span>
                <span class="split-second">{{ splitPreview.second }}</span>
              </div>
            </div>
            
            <div class="split-slider">
              <input 
                type="range" 
                v-model.number="splitModal.splitPosition"
                :min="1"
                :max="splitModal.text.length - 1"
              />
              <span class="split-position">位置: {{ splitModal.splitPosition }} / {{ splitModal.text.length }}</span>
            </div>
            
            <div class="split-preview">
              <div class="preview-item">
                <span class="preview-label">第一段:</span>
                <span class="preview-text">{{ splitPreview.first || '(空)' }}</span>
              </div>
              <div class="preview-item">
                <span class="preview-label">第二段:</span>
                <span class="preview-text">{{ splitPreview.second || '(空)' }}</span>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="cancelSplit">取消</button>
            <button class="btn btn-primary" @click="executeSplit">确认切割</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>


<style lang="scss" scoped>
.subtitle-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left,
.toolbar-center,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-btn {
  padding: 6px 12px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: var(--border-color);
  }
  
  &.small {
    padding: 4px 8px;
    font-size: 12px;
  }
  
  &.primary {
    background-color: var(--accent-color);
    
    &:hover {
      background-color: var(--accent-hover);
    }
  }
}

.offset-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.offset-input {
  width: 60px;
  padding: 4px 8px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 12px;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.subtitle-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.subtitle-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 4px;
  background-color: var(--bg-primary);
  border-radius: 6px;
  border: 1px solid transparent;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.current {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.1);
  }
  
  &.editing {
    background-color: var(--bg-hover);
    flex-direction: column;
  }
}

.sub-index {
  min-width: 30px;
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.sub-time {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 100px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  font-variant-numeric: tabular-nums;
  
  &:hover {
    color: var(--accent-color);
  }
  
  .time-sep {
    color: var(--text-muted);
  }
}

.sub-text {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.4;
  cursor: pointer;
  word-break: break-word;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: rgba(59, 130, 246, 0.1);
  }
}

.sub-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  
  .subtitle-item:hover & {
    opacity: 1;
  }
}

.action-btn {
  padding: 4px 6px;
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.danger:hover {
    background-color: rgba(239, 68, 68, 0.2);
  }
}

.edit-form {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.edit-row {
  display: flex;
  gap: 8px;
  align-items: center;
  
  &.time-row {
    label {
      font-size: 12px;
      color: var(--text-secondary);
    }
    
    input {
      width: 110px;
    }
  }
  
  input, textarea {
    padding: 6px 10px;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 13px;
    font-family: inherit;
    
    &:focus {
      outline: none;
      border-color: var(--accent-color);
    }
  }
  
  textarea {
    flex: 1;
    resize: vertical;
    min-height: 50px;
  }
}

.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.edit-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  
  &.save {
    background-color: var(--accent-color);
    color: white;
    
    &:hover {
      background-color: var(--accent-hover);
    }
  }
  
  &.cancel {
    background-color: var(--bg-hover);
    color: var(--text-primary);
    
    &:hover {
      background-color: var(--border-color);
    }
  }
}

.empty-list {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
}

// Context Menu
.context-menu {
  position: fixed;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  min-width: 150px;
  z-index: 2000;
  padding: 4px 0;
}

.context-menu-item {
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.15s;
  
  &:hover:not(.disabled) {
    background-color: var(--bg-hover);
  }
  
  &.disabled {
    color: var(--text-muted);
    cursor: not-allowed;
  }
  
  &.danger {
    color: #ef4444;
    
    &:hover:not(.disabled) {
      background-color: rgba(239, 68, 68, 0.1);
    }
  }
}

.context-menu-divider {
  height: 1px;
  background-color: var(--border-color);
  margin: 4px 0;
}

// Split Modal
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2001;
}

.split-modal {
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
  
  h3 {
    margin: 0;
    font-size: 16px;
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
  padding: 20px;
}

.split-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
}

.split-text-container {
  background-color: var(--bg-primary);
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: hidden;
}

.split-text-clickable {
  padding: 16px;
  font-size: 15px;
  line-height: 1.6;
  cursor: text;
  word-break: break-word;
  color: var(--text-primary);
  user-select: none;
  
  &:hover {
    background-color: var(--bg-hover);
  }
}

.split-text-preview {
  padding: 12px 16px;
  font-size: 15px;
  line-height: 1.6;
  word-break: break-word;
  border-top: 1px solid var(--border-color);
  background-color: var(--bg-secondary);
}

.split-first {
  color: var(--accent-color);
}

.split-cursor {
  color: #ef4444;
  font-weight: bold;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.split-second {
  color: var(--text-secondary);
}

.split-slider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  
  input[type="range"] {
    flex: 1;
    height: 6px;
    -webkit-appearance: none;
    background: var(--border-color);
    border-radius: 3px;
    
    &::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 16px;
      height: 16px;
      background: var(--accent-color);
      border-radius: 50%;
      cursor: pointer;
    }
  }
  
  .split-position {
    font-size: 12px;
    color: var(--text-secondary);
    min-width: 80px;
  }
}

.split-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
  
  .preview-label {
    color: var(--text-secondary);
    min-width: 60px;
  }
  
  .preview-text {
    color: var(--text-primary);
    flex: 1;
    word-break: break-word;
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
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &.btn-primary {
    background-color: var(--accent-color);
    color: white;
    
    &:hover {
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
