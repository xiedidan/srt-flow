<script setup>
/**
 * Subtitle Editor Tasks View
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTasksStore } from '@/stores/tasks'
import { useWebSocket } from '@/composables/useWebSocket'
import TaskCard from '@/components/tasks/TaskCard.vue'
import TaskDetailModal from '@/components/tasks/TaskDetailModal.vue'
import TaskSubmitModal from '@/components/tasks/TaskSubmitModal.vue'
import Pagination from '@/components/common/Pagination.vue'

const tasksStore = useTasksStore()
const taskType = 'editor'
const showSubmitModal = ref(false)
const selectedTaskId = ref(null)
const currentPage = ref(1)
const pageSize = ref(12)

// WebSocket for real-time updates
const { connected } = useWebSocket((data) => {
  if (data.type === 'task_update' && data.data) {
    tasksStore.updateTaskFromWs(data.data)
  } else if (data.type === 'task_progress' && data.data) {
    tasksStore.updateTaskFromWs(data.data)
  }
})

const filteredTasks = computed(() => 
  tasksStore.tasks.filter(t => t.type === taskType)
)

const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredTasks.value.slice(start, end)
})

const totalPages = computed(() => 
  Math.ceil(filteredTasks.value.length / pageSize.value)
)

const stats = computed(() => ({
  total: filteredTasks.value.length,
  running: filteredTasks.value.filter(t => t.status === 'running').length,
  completed: filteredTasks.value.filter(t => t.status === 'completed').length,
  failed: filteredTasks.value.filter(t => t.status === 'failed').length
}))

function handleCreateTask() {
  showSubmitModal.value = true
}

function handleTaskClick(taskId) {
  selectedTaskId.value = taskId
}

function handlePageChange(page) {
  currentPage.value = page
}

function refreshTasks() {
  tasksStore.fetchTasks()
}

// Auto refresh every 30s as fallback
let refreshInterval
onMounted(() => {
  tasksStore.fetchTasks()
  refreshInterval = setInterval(refreshTasks, 30000)
})
onUnmounted(() => {
  clearInterval(refreshInterval)
})
</script>

<template>
  <div class="editor-tasks-view">
    <div class="view-header">
      <div class="header-content">
        <div class="title-row">
          <h1 class="view-title">✂️ 视频剪辑</h1>
          <span class="ws-status" :class="{ connected }">
            {{ connected ? '● 实时' : '○ 离线' }}
          </span>
        </div>
        <p class="view-description">编辑和优化视频内容</p>
      </div>
      <div class="header-actions">
        <button class="btn-refresh" @click="refreshTasks" title="刷新">🔄</button>
        <button class="btn-primary" @click="handleCreateTask">
          <span class="btn-icon">➕</span>
          新建剪辑任务
        </button>
      </div>
    </div>

    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-label">全部</span>
        <span class="stat-value">{{ stats.total }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">进行中</span>
        <span class="stat-value stat-running">{{ stats.running }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">已完成</span>
        <span class="stat-value stat-completed">{{ stats.completed }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">失败</span>
        <span class="stat-value stat-failed">{{ stats.failed }}</span>
      </div>
    </div>

    <div v-if="paginatedTasks.length > 0" class="tasks-grid">
      <TaskCard
        v-for="task in paginatedTasks"
        :key="task.id"
        :task="task"
        @click="handleTaskClick(task.id)"
      />
    </div>

    <div v-else class="empty-state">
      <div class="empty-icon">✂️</div>
      <h3>暂无剪辑任务</h3>
      <p>点击上方按钮创建第一个剪辑任务</p>
    </div>

    <Pagination
      v-if="totalPages > 1"
      :current-page="currentPage"
      :total-pages="totalPages"
      @page-change="handlePageChange"
    />

    <TaskSubmitModal
      v-if="showSubmitModal"
      :task-type="taskType"
      @close="showSubmitModal = false"
    />
    <TaskDetailModal
      v-if="selectedTaskId"
      :task-id="selectedTaskId"
      @close="selectedTaskId = null"
    />
  </div>
</template>

<style lang="scss" scoped>
.editor-tasks-view {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
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

.stats-bar {
  display: flex;
  gap: 16px;
  padding: 16px;
  background-color: var(--bg-secondary);
  border-radius: 12px;
  margin-bottom: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);

  &.stat-running {
    color: var(--status-running);
  }

  &.stat-completed {
    color: var(--status-completed);
  }

  &.stat-failed {
    color: var(--status-failed);
  }
}

.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

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
