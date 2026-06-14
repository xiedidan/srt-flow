<template>
  <div class="bilingual-editor">
    <div class="editor-toolbar">
      <div class="toolbar-group">
        <input v-model="searchQuery" type="text" class="search-input" placeholder="搜索..." />
      </div>
      <div v-if="!readonly" class="toolbar-group">
        <span class="offset-label">时间偏移:</span>
        <input v-model.number="offsetValue" type="number" step="0.1" class="offset-input" />
        <button class="toolbar-btn small" @click="applyOffsetBoth">应用</button>
      </div>
      <div class="toolbar-group">
        <button class="toolbar-btn" @click="exportSrt('original')">导出原文</button>
        <button class="toolbar-btn" @click="exportSrt('translated')">导出译文</button>
        <button v-if="!readonly && hasChanges" class="toolbar-btn primary" @click="saveAll">保存</button>
      </div>
    </div>
    <div class="table-header">
      <div class="col-time">时间</div>
      <div class="col-original">
        <span>原文</span>
        <span class="col-count">{{ localOriginal.length }}</span>
      </div>
      <div class="col-translated">
        <span>译文</span>
        <span class="col-count">{{ localTranslated.length }}</span>
      </div>
    </div>
    <div ref="listRef" class="subtitle-table">
      <div v-for="row in filteredRows" :key="row.id" :data-row-id="row.id" class="table-row" :class="{ current: row.id === currentRowId }">
        <div class="col-time" @click="seekTo(row.time)">{{ formatTimeShort(row.time) }}</div>
        <div class="col-original" :class="{ empty: !row.original, editing: isEditing('original', row.original) }" @click="handleCellClick('original', row.original)" @contextmenu="handleContextMenu($event, 'original', row.original)">
          <template v-if="row.original">
            <template v-if="!isEditing('original', row.original)">
              <div class="cell-time">{{ formatTimeShort(row.original.start) }} - {{ formatTimeShort(row.original.end) }}</div>
              <div class="cell-text">{{ row.original.original || row.original.text || '(空)' }}</div>
            </template>
            <template v-else>
              <div class="edit-panel" @click.stop>
                <div class="edit-times">
                  <input v-model="editForm.start" type="text" class="time-input" placeholder="00:00:00,000" />
                  <span>-</span>
                  <input v-model="editForm.end" type="text" class="time-input" placeholder="00:00:00,000" />
                </div>
                <textarea v-model="editForm.text" class="edit-textarea" rows="2" @keydown.ctrl.enter="saveEdit" @keydown.escape="cancelEdit"></textarea>
                <div class="edit-actions">
                  <button class="btn-save" @click="saveEdit">保存</button>
                  <button class="btn-cancel" @click="cancelEdit">取消</button>
                </div>
              </div>
            </template>
          </template>
          <template v-else><div class="empty-cell">-</div></template>
        </div>
        <div class="col-translated" :class="{ empty: !row.translated, editing: isEditing('translated', row.translated) }" @click="handleCellClick('translated', row.translated)" @contextmenu="handleContextMenu($event, 'translated', row.translated)">
          <template v-if="row.translated">
            <template v-if="!isEditing('translated', row.translated)">
              <div class="cell-time">{{ formatTimeShort(row.translated.start) }} - {{ formatTimeShort(row.translated.end) }}</div>
              <div class="cell-text">{{ row.translated.original || row.translated.text || '(空)' }}</div>
            </template>
            <template v-else>
              <div class="edit-panel" @click.stop>
                <div class="edit-times">
                  <input v-model="editForm.start" type="text" class="time-input" placeholder="00:00:00,000" />
                  <span>-</span>
                  <input v-model="editForm.end" type="text" class="time-input" placeholder="00:00:00,000" />
                </div>
                <textarea v-model="editForm.text" class="edit-textarea" rows="2" @keydown.ctrl.enter="saveEdit" @keydown.escape="cancelEdit"></textarea>
                <div class="edit-actions">
                  <button class="btn-save" @click="saveEdit">保存</button>
                  <button class="btn-cancel" @click="cancelEdit">取消</button>
                </div>
              </div>
            </template>
          </template>
          <template v-else><div class="empty-cell">-</div></template>
        </div>
      </div>
      <div v-if="filteredRows.length === 0" class="empty-state">{{ searchQuery ? '无匹配结果' : '暂无字幕' }}</div>
    </div>
    <div class="status-bar">
      <span>原文 {{ localOriginal.length }} 条 | 译文 {{ localTranslated.length }} 条</span>
      <span class="hint">点击编辑，右键更多操作</span>
      <span v-if="hasChanges" class="unsaved">有未保存的更改</span>
    </div>

    <!-- Context Menu -->
    <Teleport to="body">
      <div v-if="contextMenu.show" class="context-menu" :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }" @click.stop>
        <div class="context-menu-item" :class="{ disabled: contextMenu.subIdx <= 0 }" @click="contextMenu.subIdx > 0 && mergeWithPrevious()">⬆️ 向上合并</div>
        <div class="context-menu-item" :class="{ disabled: contextMenu.subIdx >= getListLength(contextMenu.panel) - 1 }" @click="contextMenu.subIdx < getListLength(contextMenu.panel) - 1 && mergeWithNext()">⬇️ 向下合并</div>
        <div class="context-menu-divider"></div>
        <div class="context-menu-item" @click="openSplitModal()">✂️ 切割句子</div>
        <div class="context-menu-divider"></div>
        <div class="context-menu-item danger" @click="deleteSubtitle()">🗑️ 删除</div>
      </div>
    </Teleport>

    <!-- Split Modal -->
    <Teleport to="body">
      <div v-if="splitModal.show" class="modal-overlay" @click.self="cancelSplit">
        <div class="split-modal">
          <div class="modal-header">
            <h3>✂️ 切割字幕 ({{ splitModal.panel === 'original' ? '原文' : '译文' }})</h3>
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
              <input type="range" v-model.number="splitModal.splitPosition" :min="1" :max="splitModal.text.length - 1" />
              <span class="split-position">位置: {{ splitModal.splitPosition }} / {{ splitModal.text.length }}</span>
            </div>
            <div class="split-preview-items">
              <div class="preview-item"><span class="preview-label">第一段:</span><span class="preview-text">{{ splitPreview.first || '(空)' }}</span></div>
              <div class="preview-item"><span class="preview-label">第二段:</span><span class="preview-text">{{ splitPreview.second || '(空)' }}</span></div>
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

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  originalSubtitles: { type: Array, default: () => [] },
  translatedSubtitles: { type: Array, default: () => [] },
  currentTime: { type: Number, default: 0 },
  readonly: { type: Boolean, default: false }
})

const emit = defineEmits(['update:original', 'update:translated', 'seek', 'save'])

const localOriginal = ref([])
const localTranslated = ref([])
const hasChanges = ref(false)
const listRef = ref(null)
const offsetValue = ref(0)
const searchQuery = ref('')
const editingPanel = ref(null)
const editingIndex = ref(-1)
const editForm = ref({ start: '', end: '', text: '' })
const contextMenu = ref({ show: false, x: 0, y: 0, panel: null, subIdx: -1 })
const splitModal = ref({ show: false, panel: null, subIdx: -1, text: '', splitPosition: 0 })

watch(() => props.originalSubtitles, (val) => {
  localOriginal.value = JSON.parse(JSON.stringify(val || []))
  hasChanges.value = false
}, { immediate: true, deep: true })

watch(() => props.translatedSubtitles, (val) => {
  localTranslated.value = JSON.parse(JSON.stringify(val || []))
}, { immediate: true, deep: true })

const alignedRows = computed(() => {
  const rows = []
  const origMap = new Map()
  const transMap = new Map()
  localOriginal.value.forEach((sub, idx) => {
    const key = Math.round(sub.start * 10) / 10
    origMap.set(key, { ...sub, _idx: idx })
  })
  localTranslated.value.forEach((sub, idx) => {
    const key = Math.round(sub.start * 10) / 10
    transMap.set(key, { ...sub, _idx: idx })
  })
  const allTimes = new Set([...origMap.keys(), ...transMap.keys()])
  Array.from(allTimes).sort((a, b) => a - b).forEach((time, i) => {
    rows.push({ id: 'row-' + i, time, original: origMap.get(time) || null, translated: transMap.get(time) || null })
  })
  return rows
})

const filteredRows = computed(() => {
  if (!searchQuery.value.trim()) return alignedRows.value
  const q = searchQuery.value.toLowerCase()
  return alignedRows.value.filter(row => {
    const origText = row.original?.original || row.original?.text || ''
    const transText = row.translated?.original || row.translated?.text || ''
    return origText.toLowerCase().includes(q) || transText.toLowerCase().includes(q)
  })
})

const currentRowId = computed(() => {
  const time = props.currentTime
  for (const row of alignedRows.value) {
    if ((row.original && time >= row.original.start && time <= row.original.end) ||
        (row.translated && time >= row.translated.start && time <= row.translated.end)) {
      return row.id
    }
  }
  return null
})

watch(currentRowId, async (id) => {
  if (id && listRef.value) {
    await nextTick()
    const item = listRef.value.querySelector('[data-row-id="' + id + '"]')
    if (item) item.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
})

function formatSrtTime(seconds) {
  if (!seconds || isNaN(seconds)) return '00:00:00,000'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') + ',' + String(ms).padStart(3, '0')
}

function formatTimeShort(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00.0'
  const mins = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(1)
  return mins + ':' + secs.padStart(4, '0')
}

function handleCellClick(panel, sub) {
  if (props.readonly || !sub) return
  startEdit(panel, sub._idx)
}

function isEditing(panel, sub) {
  return sub && editingPanel.value === panel && editingIndex.value === sub._idx
}

function startEdit(panel, idx) {
  if (props.readonly) return
  const list = panel === 'original' ? localOriginal.value : localTranslated.value
  const sub = list[idx]
  if (!sub) return
  editingPanel.value = panel
  editingIndex.value = idx
  editForm.value = {
    start: formatSrtTime(sub.start),
    end: formatSrtTime(sub.end),
    text: sub.original || sub.text || ''
  }
  nextTick(() => {
    const ta = document.querySelector('.edit-textarea')
    if (ta) ta.focus()
  })
}

function parseSrtTime(timeStr) {
  const match = timeStr.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})/)
  if (!match) return 0
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]) + Number(match[4]) / 1000
}

function saveEdit() {
  if (editingIndex.value < 0 || !editingPanel.value) return
  const start = parseSrtTime(editForm.value.start)
  const end = parseSrtTime(editForm.value.end)
  if (end <= start) {
    alert('结束时间必须大于开始时间')
    return
  }
  const list = editingPanel.value === 'original' ? localOriginal.value : localTranslated.value
  list[editingIndex.value] = {
    ...list[editingIndex.value],
    start,
    end,
    original: editForm.value.text,
    text: editForm.value.text
  }
  hasChanges.value = true
  editingPanel.value = null
  editingIndex.value = -1
  emit('update:original', localOriginal.value)
  emit('update:translated', localTranslated.value)
}

function cancelEdit() {
  editingPanel.value = null
  editingIndex.value = -1
}

// Context menu handlers
function handleContextMenu(event, panel, sub) {
  if (props.readonly || !sub) return
  event.preventDefault()
  contextMenu.value = { show: true, x: event.clientX, y: event.clientY, panel, subIdx: sub._idx }
}

function closeContextMenu() {
  contextMenu.value.show = false
}

function handleClickOutside() {
  if (contextMenu.value.show) closeContextMenu()
}

function getList(panel) {
  return panel === 'original' ? localOriginal : localTranslated
}

function getListLength(panel) {
  return panel === 'original' ? localOriginal.value.length : localTranslated.value.length
}

function reindexList(list) {
  list.forEach((s, i) => { s.index = i + 1 })
}

function emitUpdates() {
  emit('update:original', localOriginal.value)
  emit('update:translated', localTranslated.value)
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

function mergeWithPrevious() {
  const { panel, subIdx } = contextMenu.value
  if (subIdx <= 0) return
  const list = getList(panel)
  const current = list.value[subIdx]
  const previous = list.value[subIdx - 1]
  const mergedText = mergeTexts(previous.original || previous.text, current.original || current.text)
  list.value[subIdx - 1] = { ...previous, end: current.end, original: mergedText, text: mergedText }
  list.value.splice(subIdx, 1)
  reindexList(list.value)
  hasChanges.value = true
  closeContextMenu()
  emitUpdates()
  // Auto save after merge
  saveAll()
}

function mergeWithNext() {
  const { panel, subIdx } = contextMenu.value
  const list = getList(panel)
  if (subIdx >= list.value.length - 1) return
  const current = list.value[subIdx]
  const next = list.value[subIdx + 1]
  const mergedText = mergeTexts(current.original || current.text, next.original || next.text)
  list.value[subIdx] = { ...current, end: next.end, original: mergedText, text: mergedText }
  list.value.splice(subIdx + 1, 1)
  reindexList(list.value)
  hasChanges.value = true
  closeContextMenu()
  emitUpdates()
  // Auto save after merge
  saveAll()
}

function deleteSubtitle() {
  if (props.readonly) return
  const { panel, subIdx } = contextMenu.value
  if (!confirm('确定删除这条字幕吗？')) return
  const list = getList(panel)
  list.value.splice(subIdx, 1)
  reindexList(list.value)
  hasChanges.value = true
  closeContextMenu()
  emitUpdates()
}

// Split modal handlers
function openSplitModal() {
  const { panel, subIdx } = contextMenu.value
  const list = getList(panel)
  const sub = list.value[subIdx]
  const text = sub.original || sub.text || ''
  splitModal.value = { show: true, panel, subIdx, text, splitPosition: Math.floor(text.length / 2) }
  closeContextMenu()
}

const splitPreview = computed(() => {
  const { text, splitPosition } = splitModal.value
  return { first: text.substring(0, splitPosition), second: text.substring(splitPosition) }
})

function handleSplitClick(event) {
  const text = splitModal.value.text
  if (!text) return
  let position = 0
  if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(event.clientX, event.clientY)
    if (pos) position = pos.offset
  } else if (document.caretRangeFromPoint) {
    const range = document.caretRangeFromPoint(event.clientX, event.clientY)
    if (range) position = range.startOffset
  }
  splitModal.value.splitPosition = Math.max(1, Math.min(text.length - 1, position))
}

function executeSplit() {
  const { panel, subIdx, text, splitPosition } = splitModal.value
  if (splitPosition <= 0 || splitPosition >= text.length) {
    alert('请选择有效的切割位置')
    return
  }
  const firstText = text.substring(0, splitPosition).trim()
  const secondText = text.substring(splitPosition).trim()
  if (!firstText || !secondText) {
    alert('切割后的字幕不能为空')
    return
  }
  const list = getList(panel)
  const sub = list.value[subIdx]
  const totalDuration = sub.end - sub.start
  const ratio = firstText.length / text.length
  const splitTime = sub.start + totalDuration * ratio
  list.value[subIdx] = { ...sub, end: splitTime, original: firstText, text: firstText }
  list.value.splice(subIdx + 1, 0, { ...sub, index: sub.index + 1, start: splitTime, original: secondText, text: secondText })
  reindexList(list.value)
  hasChanges.value = true
  splitModal.value.show = false
  emitUpdates()
  // Auto save after split
  saveAll()
}

function cancelSplit() {
  splitModal.value.show = false
}

onMounted(() => { document.addEventListener('click', handleClickOutside) })
onUnmounted(() => { document.removeEventListener('click', handleClickOutside) })

function seekTo(time) { emit('seek', time) }

function applyOffsetBoth() {
  if (props.readonly || offsetValue.value === 0) return
  const offset = parseFloat(offsetValue.value)
  localOriginal.value.forEach(sub => { sub.start = Math.max(0, sub.start + offset); sub.end = Math.max(0, sub.end + offset) })
  localTranslated.value.forEach(sub => { sub.start = Math.max(0, sub.start + offset); sub.end = Math.max(0, sub.end + offset) })
  offsetValue.value = 0
  hasChanges.value = true
  emit('update:original', localOriginal.value)
  emit('update:translated', localTranslated.value)
}

function saveAll() { emit('save', { original: localOriginal.value, translated: localTranslated.value }) }

function exportSrt(panel) {
  const list = panel === 'original' ? localOriginal.value : localTranslated.value
  const filename = panel === 'original' ? 'subtitle_original.srt' : 'subtitle_translated.srt'
  const srt = list.map((sub, i) => (i + 1) + '\n' + formatSrtTime(sub.start) + ' --> ' + formatSrtTime(sub.end) + '\n' + (sub.original || sub.text || '')).join('\n\n')
  const blob = new Blob([srt], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

defineExpose({ hasChanges, saveAll, exportSrt })
</script>


<style lang="scss" scoped>
.bilingual-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 12px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.search-input {
  width: 180px;
  padding: 6px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
}

.toolbar-btn {
  padding: 6px 10px;
  background: var(--bg-hover);
  border: none;
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
}

.toolbar-btn.small { padding: 4px 8px; }
.toolbar-btn.primary { background: var(--accent-color); color: white; }

.offset-label { font-size: 12px; color: var(--text-secondary); }
.offset-input {
  width: 60px;
  padding: 4px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 12px;
}

.table-header {
  display: flex;
  background: var(--bg-primary);
  border-bottom: 2px solid var(--border-color);
  font-size: 13px;
  font-weight: 600;
}

.table-header .col-time {
  width: 70px;
  padding: 10px 8px;
  color: var(--text-secondary);
  text-align: center;
}

.table-header .col-original,
.table-header .col-translated {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-left: 1px solid var(--border-color);
}

.col-count {
  font-size: 11px;
  font-weight: normal;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 2px 6px;
  border-radius: 10px;
}

.subtitle-table { flex: 1; overflow-y: auto; }

.table-row {
  display: flex;
  border-bottom: 1px solid var(--border-color);
}

.table-row:hover { background: var(--bg-hover); }
.table-row.current { background: rgba(59, 130, 246, 0.1); }

.table-row .col-time {
  width: 70px;
  padding: 10px 8px;
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  cursor: pointer;
}

.table-row .col-original,
.table-row .col-translated {
  flex: 1;
  padding: 8px 12px;
  border-left: 1px solid var(--border-color);
  cursor: pointer;
  min-height: 50px;
}

.table-row .col-original.empty,
.table-row .col-translated.empty {
  cursor: default;
  background: var(--bg-secondary);
}

.table-row .col-original.editing,
.table-row .col-translated.editing {
  cursor: default;
  background: var(--bg-primary);
}

.edit-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.edit-times {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.time-input {
  width: 100px;
  padding: 4px 6px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 11px;
  font-family: monospace;
}

.edit-textarea {
  padding: 6px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  resize: vertical;
  min-height: 40px;
}

.edit-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.btn-save, .btn-cancel {
  padding: 4px 10px;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}

.btn-save {
  background: var(--accent-color);
  color: white;
}

.btn-cancel {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.cell-time {
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.cell-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

.empty-cell {
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
  padding: 8px 0;
}

.empty-state {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
}

.status-bar {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
}

.status-bar .hint {
  color: var(--text-muted);
}

.status-bar .unsaved {
  color: var(--warning);
  margin-left: auto;
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
}

.context-menu-item:hover:not(.disabled) {
  background-color: var(--bg-hover);
}

.context-menu-item.disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}

.context-menu-item.danger {
  color: #ef4444;
}

.context-menu-item.danger:hover:not(.disabled) {
  background-color: rgba(239, 68, 68, 0.1);
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
}

.modal-header h3 {
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
}

.close-btn:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
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
}

.split-text-clickable:hover {
  background-color: var(--bg-hover);
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
}

.split-slider input[type="range"] {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  background: var(--border-color);
  border-radius: 3px;
}

.split-slider input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: var(--accent-color);
  border-radius: 50%;
  cursor: pointer;
}

.split-position {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 100px;
}

.split-preview-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.preview-label {
  color: var(--text-secondary);
  min-width: 60px;
}

.preview-text {
  color: var(--text-primary);
  flex: 1;
  word-break: break-word;
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
}

.btn.btn-primary {
  background-color: var(--accent-color);
  color: white;
}

.btn.btn-primary:hover {
  background-color: var(--accent-hover);
}

.btn.btn-secondary {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.btn.btn-secondary:hover {
  background-color: var(--border-color);
}
</style>
