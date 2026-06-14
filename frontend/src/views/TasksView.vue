<script setup>
/**
 * Tasks management view
 * Displays task list with filtering, pagination, and real-time updates
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTasksStore } from '@/stores/tasks'
import { useWebSocket } from '@/composables/useWebSocket'
import { useViewMode } from '@/composables/useViewMode'
import TaskCard from '@/components/tasks/TaskCard.vue'
import TaskDetailModal from '@/components/tasks/TaskDetailModal.vue'
import Pagination from '@/components/common/Pagination.vue'

const tasksStore = useTasksStore()

// View mode with persistence
const { viewMode } = useViewMode('tasks', 'card')

// Tab state
const activeTab = ref('all')
const tabs = [
  { key: 'all', label: '全部', status: null },
  { key: 'running', label: '运行中', status: 'running' },
  { key: 'pending', label: '等待中', status: 'pending' },
  { key: 'completed', label: '已完成', status: 'completed' },
  { key: 'failed', label: '失败', status: 'failed' }
]

// Task type filter
const selectedType = ref('')
const taskTypes = [
  { value: '', label: '全部类型' },
  { value: 'download', label: '下载' },
  { value: 'asr', label: '语音识别' },
  { value: 'translate', label: '翻译' },
  { value: 'tts', label: '语音合成' },
  { value: 'synthesize', label: '视频合成' },
  { value: 'asset_gen', label: '素材生成' }
]

// Modal state
const showDetailModal = ref(false)
const selectedTaskId = ref(null)

// Computed
const filteredTasks = computed(() => tasksStore.tasks)

// WebSocket for real-time updates
const { connected } = useWebSocket((data) => {
  if (data.type === 'task_update' && data.data) {
    tasksStore.updateTaskFromWs(data.data)
  } else if (data.type === 'task_progress' && data.data) {
    tasksStore.updateTaskFromWs(data.data)
  }
})

// Tab counts
const tabCounts = computed(() => ({
  all: tasksStore.pagination.total,
  running: tasksStore.runningTasks.length,
  pending: tasksStore.pendingTasks.length,
  completed: tasksStore.completedTasks.length,
  failed: tasksStore.failedTasks.length
}))

// Methods
function handleTabChange(tab) {
  activeTab.value = tab.key
  tasksStore.setFilters({ status: tab.status })
}

function handleTypeChange() {
  tasksStore.setFilters({ type: selectedType.value || null })
}

function handlePageChange(page) {
  tasksStore.setPage(page)
}

function handleViewTask(task) {
  selectedTaskId.value = task.id
  showDetailModal.value = true
}

async function handleRetryTask(task) {
  try {
    await tasksStore.retryTask(task.id, 'normal')
    showDetailModal.value = false
  } catch (e) {
    console.error('Retry failed:', e)
  }
}

async function handleCancelTask(task) {
  if (!confirm('确定要取消此任务吗？')) return
  try {
    await tasksStore.cancelTask(task.id)
    showDetailModal.value = false
  } catch (e) {
    console.error('Cancel failed:', e)
  }
}

function refreshTasks() {
  tasksStore.fetchTasks()
}

// Lifecycle
onMounted(() => {
  tasksStore.fetchTasks()
})

// Auto refresh every 30s as fallback
let refreshInterval
onMounted(() => {
  refreshInterval = setInterval(refreshTasks, 30000)
})
onUnmounted(() => {
  clearInterval(refreshInterval)
})
</script>

<template>
  <div class="tasks-view">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">任务管理</h2>
        <span class="ws-status" :class="{ connected }">
          {{ connected ? '● 实时' : '○ 离线' }}
        </span>
      </div>
      <div class="header-actions">
        <button class="btn-refresh" @click="refreshTasks" title="刷新">
          🔄
        </button>
      </div>
    </div>
    
    <div class="info-banner">
      <span class="info-icon">💡</span>
      <span class="info-text">此页面汇总所有任务。如需创建新任务，请前往对应的任务类型页面（语音识别、字幕翻译等）。</span>
    </div>
    
    <div class="filters-bar">
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="handleTabChange(tab)"
        >
          {{ tab.label }}
          <span v-if="tabCounts[tab.key] > 0" class="tab-count">
            {{ tabCounts[tab.key] }}
          </span>
        </button>
      </div>
      
      <div class="filters-right">
        <select v-model="selectedType" class="type-filter" @change="handleTypeChange">
          <option v-for="type in taskTypes" :key="type.value" :value="type.value">
            {{ type.label }}
          </option>
        </select>
        
        <div class="view-toggle">
          <button :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'" title="卡片视图">▦</button>
          <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图">☰</button>
        </div>
      </div>
    </div>
    
    <div class="tasks-content">
      <div v-if="tasksStore.loading" class="loading">
        <span class="loading-spinner">⏳</span>
        加载中...
      </div>
      
      <div v-else-if="filteredTasks.length === 0" class="empty-state">
        <span class="icon">📋</span>
        <p>暂无任务</p>
        <p class="empty-hint">前往对应的任务类型页面创建任务</p>
      </div>
      
      <template v-else>
        <div class="tasks-grid" :class="viewMode">
          <TaskCard
            v-for="task in filteredTasks"
            :key="task.id"
            :task="task"
            :view-mode="viewMode"
            @view="handleViewTask"
            @retry="handleRetryTask"
            @cancel="handleCancelTask"
          />
        </div>
        
        <div class="pagination-wrapper">
          <Pagination
            :page="tasksStore.pagination.page"
            :total-pages="tasksStore.totalPages"
            :total="tasksStore.pagination.total"
            @change="handlePageChange"
          />
        </div>
      </template>
    </div>
    
    <!-- Task Detail Modal -->
    <TaskDetailModal
      :visible="showDetailModal"
      :task-id="selectedTaskId"
      @close="showDetailModal = false"
      @retry="handleRetryTask"
      @cancel="handleCancelTask"
    />
    

  </div>
</template>

<style lang="scss" scoped>
.tasks-view {
  max-width: 1200px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.ws-status {
  font-size: 12px;
  color: var(--text-muted);
  
  &.connected {
    color: var(--success);
  }
}

.header-actions {
  display: flex;
  gap: 12px;
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
  padding: 8px 16px;
  background-color: var(--accent-color);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background-color: var(--accent-hover);
  }
}

.filters-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.filters-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.view-toggle {
  display: flex;
  background-color: var(--bg-secondary);
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

.tabs {
  display: flex;
  gap: 8px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 14px;
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
}

.tab-count {
  padding: 2px 6px;
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  font-size: 12px;
}

.type-filter {
  padding: 8px 12px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.tasks-content {
  min-height: 400px;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 80px 20px;
  color: var(--text-secondary);
}

.loading-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
  
  .icon {
    font-size: 64px;
    margin-bottom: 16px;
  }
  
  p {
    color: var(--text-secondary);
    margin: 0 0 8px 0;
  }
  
  .empty-hint {
    font-size: 13px;
    color: var(--text-muted);
  }
}

.info-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background-color: var(--bg-secondary);
  border-left: 3px solid var(--accent-color);
  border-radius: 6px;
  margin-bottom: 24px;
}

.info-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.info-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.tasks-grid {
  &.card {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
  }
  
  &.list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}
</style>
