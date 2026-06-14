<script setup>
/**
 * ASR (Speech Recognition) Tasks View
 * Enhanced with list/card view toggle, task details, and subtitle editing
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTasksStore } from '@/stores/tasks'
import { useVideosStore } from '@/stores/videos'
import { useWebSocket } from '@/composables/useWebSocket'
import { useViewMode } from '@/composables/useViewMode'
import TaskCard from '@/components/tasks/TaskCard.vue'
import TaskDetailModal from '@/components/tasks/TaskDetailModal.vue'
import AsrTaskCreateModal from '@/components/asr/AsrTaskCreateModal.vue'
import SubtitleEditorModal from '@/components/asr/SubtitleEditorModal.vue'
import Pagination from '@/components/common/Pagination.vue'

const tasksStore = useTasksStore()
const videosStore = useVideosStore()

const taskType = 'asr'
const { viewMode } = useViewMode('asr', 'card')
const showCreateModal = ref(false)
const showDetailModal = ref(false)
const showSubtitleEditor = ref(false)
const selectedTaskId = ref(null)
const selectedTask = ref(null)
const currentPage = ref(1)
const pageSize = ref(12)
const statusFilter = ref('all')
const tagFilter = ref('')
const tagSearchOpen = ref(false)
const tagSearchQuery = ref('')

// WebSocket for real-time updates
const { connected } = useWebSocket((data) => {
  if (data.type === 'task_update' && data.data) {
    tasksStore.updateTaskFromWs(data.data)
  } else if (data.type === 'task_progress' && data.data) {
    tasksStore.updateTaskFromWs(data.data)
  }
})

// All available tags
const allTags = computed(() => videosStore.allTags)

// Filtered tags based on search query
const filteredTags = computed(() => {
  if (!tagSearchQuery.value) return allTags.value
  const q = tagSearchQuery.value.toLowerCase()
  return allTags.value.filter(tag => tag.toLowerCase().includes(q))
})

// Filter tasks by type, status, and tag
const filteredTasks = computed(() => {
  let tasks = tasksStore.tasks.filter(t => t.type === taskType)
  if (statusFilter.value !== 'all') {
    tasks = tasks.filter(t => t.status === statusFilter.value)
  }
  // Tag filter is applied server-side, but we can double-check here
  return tasks
})

// Paginated tasks
const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredTasks.value.slice(start, end)
})

const totalPages = computed(() => 
  Math.ceil(filteredTasks.value.length / pageSize.value)
)

// Task statistics
const stats = computed(() => ({
  total: tasksStore.tasks.filter(t => t.type === taskType).length,
  running: tasksStore.tasks.filter(t => t.type === taskType && t.status === 'running').length,
  completed: tasksStore.tasks.filter(t => t.type === taskType && t.status === 'completed').length,
  failed: tasksStore.tasks.filter(t => t.type === taskType && t.status === 'failed').length
}))

// Status config
const statusConfig = {
  pending: { label: '等待中', class: 'status-pending', icon: '⏳' },
  running: { label: '运行中', class: 'status-running', icon: '🔄' },
  completed: { label: '已完成', class: 'status-completed', icon: '✅' },
  failed: { label: '失败', class: 'status-failed', icon: '❌' },
  cancelled: { label: '已取消', class: 'status-cancelled', icon: '🚫' }
}

function handleCreateTask() {
  showCreateModal.value = true
}

function handleTaskClick(taskId) {
  selectedTaskId.value = taskId
  showDetailModal.value = true
}

function handleViewDetail(task) {
  selectedTaskId.value = task.id
  showDetailModal.value = true
}

async function handleEditSubtitle(task) {
  selectedTask.value = task
  showSubtitleEditor.value = true
}

function handlePageChange(page) {
  currentPage.value = page
}

function handleStatusFilter(status) {
  statusFilter.value = status
  currentPage.value = 1
  refreshTasks()
}

function handleTagFilter(tag) {
  tagFilter.value = tag
  tagSearchOpen.value = false
  tagSearchQuery.value = ''
  currentPage.value = 1
  refreshTasks()
}

function clearTagFilter() {
  tagFilter.value = ''
  tagSearchOpen.value = false
  tagSearchQuery.value = ''
  currentPage.value = 1
  refreshTasks()
}

async function handleRetry(task) {
  try {
    await tasksStore.retryTask(task.id)
  } catch (e) {
    console.error('Failed to retry task:', e)
  }
}

async function handleCancel(task) {
  if (!confirm('确定要取消这个任务吗？')) return
  try {
    await tasksStore.cancelTask(task.id)
  } catch (e) {
    console.error('Failed to cancel task:', e)
  }
}

function handleTasksCreated(count) {
  refreshTasks()
}

function refreshTasks() {
  const params = { type: taskType }
  if (tagFilter.value) {
    params.tag = tagFilter.value
  }
  tasksStore.fetchTasks(params)
}

function formatTime(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getVideoTitle(task) {
  // Use video_title from backend if available
  if (task.video_title) {
    return task.video_title
  }
  // Fallback to local lookup
  if (task.payload?.video_id) {
    const video = videosStore.videos.find(v => v.id === task.payload.video_id)
    return video?.title || task.payload.video_id.slice(0, 8) + '...'
  }
  return '-'
}

// Auto refresh every 30s as fallback
let refreshInterval
onMounted(() => {
  refreshTasks()
  videosStore.fetchVideos({ page_size: 100 }) // Load videos to get tags
  refreshInterval = setInterval(refreshTasks, 30000)
})
onUnmounted(() => {
  clearInterval(refreshInterval)
})
</script>

<template>
  <div class="asr-tasks-view">
    <div class="view-header">
      <div class="header-content">
        <div class="title-row">
          <h1 class="view-title">🎤 语音识别</h1>
          <span class="ws-status" :class="{ connected }">
            {{ connected ? '● 实时' : '○ 离线' }}
          </span>
        </div>
        <p class="view-description">将视频音频转换为文字字幕</p>
      </div>
      <div class="header-actions">
        <button class="btn-refresh" @click="refreshTasks" title="刷新">🔄</button>
        <button class="btn-primary" @click="handleCreateTask">
          <span class="btn-icon">➕</span>
          新建识别任务
        </button>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- Status filter -->
        <div class="status-filters">
          <button 
            class="filter-btn" 
            :class="{ active: statusFilter === 'all' }"
            @click="handleStatusFilter('all')"
          >
            全部 <span class="count">{{ stats.total }}</span>
          </button>
          <button 
            class="filter-btn" 
            :class="{ active: statusFilter === 'running' }"
            @click="handleStatusFilter('running')"
          >
            进行中 <span class="count running">{{ stats.running }}</span>
          </button>
          <button 
            class="filter-btn" 
            :class="{ active: statusFilter === 'completed' }"
            @click="handleStatusFilter('completed')"
          >
            已完成 <span class="count completed">{{ stats.completed }}</span>
          </button>
          <button 
            class="filter-btn" 
            :class="{ active: statusFilter === 'failed' }"
            @click="handleStatusFilter('failed')"
          >
            失败 <span class="count failed">{{ stats.failed }}</span>
          </button>
        </div>
        
        <!-- Tag filter -->
        <div class="tag-filter">
          <div class="tag-dropdown" :class="{ open: tagSearchOpen }">
            <button 
              class="tag-trigger" 
              :class="{ active: tagFilter }"
              @click="tagSearchOpen = !tagSearchOpen"
            >
              <span v-if="tagFilter">🏷️ {{ tagFilter }}</span>
              <span v-else>🏷️ 标签筛选</span>
              <span class="dropdown-arrow">{{ tagSearchOpen ? '▲' : '▼' }}</span>
            </button>
            <button 
              v-if="tagFilter" 
              class="tag-clear" 
              @click.stop="clearTagFilter"
              title="清除筛选"
            >✕</button>
            
            <div v-if="tagSearchOpen" class="tag-dropdown-menu">
              <input 
                v-model="tagSearchQuery"
                type="text"
                class="tag-search-input"
                placeholder="搜索标签..."
                @click.stop
              />
              <div class="tag-list">
                <div 
                  v-for="tag in filteredTags" 
                  :key="tag"
                  class="tag-option"
                  :class="{ selected: tagFilter === tag }"
                  @click="handleTagFilter(tag)"
                >
                  🏷️ {{ tag }}
                </div>
                <div v-if="filteredTags.length === 0" class="tag-empty">
                  无匹配标签
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="toolbar-right">
        <!-- View toggle -->
        <div class="view-toggle">
          <button 
            :class="{ active: viewMode === 'card' }" 
            @click="viewMode = 'card'" 
            title="卡片视图"
          >▦</button>
          <button 
            :class="{ active: viewMode === 'list' }" 
            @click="viewMode = 'list'" 
            title="列表视图"
          >☰</button>
        </div>
      </div>
    </div>

    <!-- Task Content -->
    <div class="tasks-content">
      <!-- Card View -->
      <div v-if="viewMode === 'card' && paginatedTasks.length > 0" class="tasks-grid">
        <div 
          v-for="task in paginatedTasks" 
          :key="task.id" 
          class="task-card-enhanced"
          :class="statusConfig[task.status]?.class"
        >
          <div class="card-header">
            <span class="task-status">
              <span class="status-icon">{{ statusConfig[task.status]?.icon }}</span>
              {{ statusConfig[task.status]?.label }}
            </span>
            <span class="task-time">{{ formatTime(task.created_at) }}</span>
          </div>
          
          <div class="card-body">
            <div class="video-title">{{ getVideoTitle(task) }}</div>
            <div class="task-id">ID: {{ task.id.slice(0, 8) }}...</div>
            
            <div v-if="task.status === 'running'" class="task-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
              </div>
              <span class="progress-text">{{ task.progress }}%</span>
            </div>
            
            <div v-if="task.error" class="task-error">{{ task.error }}</div>
          </div>
          
          <div class="card-footer">
            <button class="action-btn" @click="handleViewDetail(task)" title="查看详情">
              📋 详情
            </button>
            <button 
              v-if="task.status === 'completed'" 
              class="action-btn primary" 
              @click="handleEditSubtitle(task)"
              title="编辑字幕"
            >
              ✏️ 字幕
            </button>
            <button 
              v-if="task.status === 'failed'" 
              class="action-btn" 
              @click="handleRetry(task)"
              title="重试"
            >
              🔁 重试
            </button>
            <button 
              v-if="['pending', 'running'].includes(task.status)" 
              class="action-btn danger" 
              @click="handleCancel(task)"
              title="取消"
            >
              ⏹️ 取消
            </button>
          </div>
        </div>
      </div>

      <!-- List View -->
      <div v-else-if="viewMode === 'list' && paginatedTasks.length > 0" class="tasks-list">
        <table class="task-table">
          <thead>
            <tr>
              <th>状态</th>
              <th>视频</th>
              <th>任务ID</th>
              <th>进度</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in paginatedTasks" :key="task.id" :class="statusConfig[task.status]?.class">
              <td>
                <span class="status-badge" :class="statusConfig[task.status]?.class">
                  {{ statusConfig[task.status]?.icon }} {{ statusConfig[task.status]?.label }}
                </span>
              </td>
              <td class="video-cell">{{ getVideoTitle(task) }}</td>
              <td class="id-cell">{{ task.id.slice(0, 8) }}...</td>
              <td class="progress-cell">
                <template v-if="task.status === 'running'">
                  <div class="mini-progress">
                    <div class="mini-progress-fill" :style="{ width: `${task.progress}%` }"></div>
                  </div>
                  <span>{{ task.progress }}%</span>
                </template>
                <template v-else-if="task.status === 'completed'">100%</template>
                <template v-else>-</template>
              </td>
              <td class="time-cell">{{ formatTime(task.created_at) }}</td>
              <td class="actions-cell">
                <button class="table-action" @click="handleViewDetail(task)" title="详情">📋</button>
                <button 
                  v-if="task.status === 'completed'" 
                  class="table-action primary" 
                  @click="handleEditSubtitle(task)"
                  title="编辑字幕"
                >✏️</button>
                <button 
                  v-if="task.status === 'failed'" 
                  class="table-action" 
                  @click="handleRetry(task)"
                  title="重试"
                >🔁</button>
                <button 
                  v-if="['pending', 'running'].includes(task.status)" 
                  class="table-action danger" 
                  @click="handleCancel(task)"
                  title="取消"
                >⏹️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty State -->
      <div v-else class="empty-state">
        <div class="empty-icon">🎤</div>
        <h3>暂无语音识别任务</h3>
        <p>点击上方按钮创建第一个识别任务</p>
      </div>
    </div>

    <!-- Pagination -->
    <Pagination
      v-if="totalPages > 1"
      :page="currentPage"
      :total-pages="totalPages"
      :total="filteredTasks.length"
      @change="handlePageChange"
    />

    <!-- Modals -->
    <AsrTaskCreateModal
      v-if="showCreateModal"
      @close="showCreateModal = false"
      @created="handleTasksCreated"
    />
    <TaskDetailModal
      :visible="showDetailModal"
      :task-id="selectedTaskId"
      @close="showDetailModal = false; selectedTaskId = null"
      @retry="handleRetry"
      @cancel="handleCancel"
    />
    <SubtitleEditorModal
      v-if="showSubtitleEditor"
      :task="selectedTask"
      @close="showSubtitleEditor = false; selectedTask = null"
    />
  </div>
</template>


<style lang="scss" scoped>
.asr-tasks-view {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.header-content {
  flex: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.view-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.ws-status {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  
  &.connected {
    color: var(--success, #22c55e);
  }
}

.view-description {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.btn-refresh {
  padding: 8px 12px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
  }
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background-color: var(--accent-color);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background-color: var(--accent-hover);
    transform: translateY(-1px);
  }
}

.btn-icon {
  font-size: 16px;
}

/* Toolbar */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 12px 16px;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.status-filters {
  display: flex;
  gap: 4px;
}

.filter-btn {
  padding: 6px 12px;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
  
  &.active {
    background-color: var(--accent-color);
    color: white;
  }
  
  .count {
    margin-left: 4px;
    font-weight: 600;
    
    &.running { color: var(--info); }
    &.completed { color: var(--success); }
    &.failed { color: var(--error); }
  }
  
  &.active .count {
    color: inherit;
  }
}

.tag-filter {
  margin-left: 12px;
  padding-left: 12px;
  border-left: 1px solid var(--border-color);
}

.tag-dropdown {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
}

.tag-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  &.active {
    background-color: rgba(59, 130, 246, 0.1);
    border-color: var(--accent-color);
    color: var(--accent-color);
  }
  
  .dropdown-arrow {
    font-size: 10px;
    color: var(--text-muted);
  }
}

.tag-clear {
  padding: 4px 6px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--error);
  }
}

.tag-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  min-width: 200px;
  max-width: 280px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 100;
  overflow: hidden;
}

.tag-search-input {
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
  
  &:focus {
    outline: none;
  }
  
  &::placeholder {
    color: var(--text-muted);
  }
}

.tag-list {
  max-height: 200px;
  overflow-y: auto;
}

.tag-option {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.15s;
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.selected {
    background-color: rgba(59, 130, 246, 0.1);
    color: var(--accent-color);
  }
}

.tag-empty {
  padding: 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-muted);
}

.tag-select {
  padding: 6px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  min-width: 140px;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.view-toggle {
  display: flex;
  background-color: var(--bg-primary);
  border-radius: 6px;
  overflow: hidden;
  
  button {
    padding: 8px 12px;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 16px;
    
    &:hover {
      background-color: var(--bg-hover);
    }
    
    &.active {
      background-color: var(--accent-color);
      color: white;
    }
  }
}

/* Tasks Content */
.tasks-content {
  min-height: 400px;
}

/* Card View */
.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.task-card-enhanced {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--accent-color);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
  
  &.status-running { border-left: 4px solid var(--info); }
  &.status-completed { border-left: 4px solid var(--success); }
  &.status-failed { border-left: 4px solid var(--error); }
  &.status-pending { border-left: 4px solid var(--warning); }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
}

.task-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.status-icon {
  font-size: 14px;
}

.task-time {
  font-size: 12px;
  color: var(--text-muted);
}

.card-body {
  padding: 16px;
}

.video-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-id {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background-color: var(--bg-primary);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: var(--accent-color);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 36px;
}

.task-error {
  font-size: 12px;
  color: var(--error);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-footer {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  background-color: var(--bg-primary);
}

.action-btn {
  flex: 1;
  padding: 8px 12px;
  background-color: var(--bg-hover);
  border: none;
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--border-color);
  }
  
  &.primary {
    background-color: var(--accent-color);
    color: white;
    
    &:hover {
      background-color: var(--accent-hover);
    }
  }
  
  &.danger:hover {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error);
  }
}

/* List View */
.tasks-list {
  margin-bottom: 24px;
}

.task-table {
  width: 100%;
  border-collapse: collapse;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
  
  th, td {
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
  }
  
  th {
    background-color: var(--bg-primary);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
  }
  
  td {
    font-size: 14px;
    color: var(--text-primary);
  }
  
  tbody tr {
    transition: background-color 0.2s;
    
    &:hover {
      background-color: var(--bg-hover);
    }
    
    &:last-child td {
      border-bottom: none;
    }
  }
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  
  &.status-pending { background-color: rgba(245, 158, 11, 0.2); color: var(--warning); }
  &.status-running { background-color: rgba(59, 130, 246, 0.2); color: var(--info); }
  &.status-completed { background-color: rgba(34, 197, 94, 0.2); color: var(--success); }
  &.status-failed { background-color: rgba(239, 68, 68, 0.2); color: var(--error); }
  &.status-cancelled { background-color: rgba(102, 102, 102, 0.2); color: var(--text-muted); }
}

.video-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.id-cell {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-muted);
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mini-progress {
  width: 60px;
  height: 4px;
  background-color: var(--bg-primary);
  border-radius: 2px;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background-color: var(--accent-color);
  transition: width 0.3s;
}

.time-cell {
  font-size: 13px;
  color: var(--text-secondary);
}

.actions-cell {
  display: flex;
  gap: 4px;
}

.table-action {
  padding: 6px 8px;
  background: none;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.primary:hover {
    background-color: rgba(59, 130, 246, 0.2);
  }
  
  &.danger:hover {
    background-color: rgba(239, 68, 68, 0.2);
  }
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state h3 {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.empty-state p {
  font-size: 14px;
  margin: 0;
}
</style>
