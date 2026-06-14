<script setup>
/**
 * Task detail modal component
 */
import { computed, watch, ref } from 'vue'
import { useTasksStore } from '@/stores/tasks'

const props = defineProps({
  visible: Boolean,
  taskId: String
})

const emit = defineEmits(['close', 'retry', 'cancel'])

const tasksStore = useTasksStore()
const activeTab = ref('info')

// Task type labels
const typeLabels = {
  download: '下载',
  asr: '语音识别',
  translate: '翻译',
  tts: '语音合成',
  synthesize: '视频合成',
  asset_gen: '素材生成',
  edit: '编辑'
}

// Status config
const statusConfig = {
  pending: { label: '等待中', class: 'status-pending' },
  running: { label: '运行中', class: 'status-running' },
  completed: { label: '已完成', class: 'status-completed' },
  failed: { label: '失败', class: 'status-failed' },
  cancelled: { label: '已取消', class: 'status-cancelled' }
}

const task = computed(() => tasksStore.currentTask)
const typeLabel = computed(() => task.value ? (typeLabels[task.value.type] || task.value.type) : '')
const status = computed(() => task.value ? (statusConfig[task.value.status] || statusConfig.pending) : null)

const canRetry = computed(() => task.value?.status === 'failed')
const canCancel = computed(() => ['pending', 'running'].includes(task.value?.status))

// Fetch task when taskId changes
watch(() => props.taskId, async (newId) => {
  if (newId && props.visible) {
    await tasksStore.fetchTask(newId)
  }
}, { immediate: true })

watch(() => props.visible, (visible) => {
  if (!visible) {
    tasksStore.clearCurrentTask()
    activeTab.value = 'info'
  }
})

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatPayload(payload) {
  if (!payload) return '-'
  return JSON.stringify(payload, null, 2)
}

function formatResult(result) {
  if (!result) return '-'
  return JSON.stringify(result, null, 2)
}

function handleClose() {
  emit('close')
}

function handleRetry() {
  if (task.value) {
    emit('retry', task.value)
  }
}

function handleCancel() {
  if (task.value) {
    emit('cancel', task.value)
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>任务详情</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div v-if="tasksStore.loading" class="modal-loading">
          加载中...
        </div>
        
        <template v-else-if="task">
          <div class="modal-tabs">
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'info' }"
              @click="activeTab = 'info'"
            >
              基本信息
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'payload' }"
              @click="activeTab = 'payload'"
            >
              任务参数
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'result' }"
              @click="activeTab = 'result'"
            >
              执行结果
            </button>
          </div>
          
          <div class="modal-body">
            <!-- Info Tab -->
            <div v-show="activeTab === 'info'" class="tab-content">
              <div class="info-grid">
                <div class="info-item">
                  <label>任务 ID</label>
                  <span class="mono">{{ task.id }}</span>
                </div>
                <div class="info-item">
                  <label>任务类型</label>
                  <span>{{ typeLabel }}</span>
                </div>
                <div class="info-item">
                  <label>状态</label>
                  <span class="status-badge" :class="status?.class">{{ status?.label }}</span>
                </div>
                <div class="info-item">
                  <label>进度</label>
                  <div class="progress-wrapper">
                    <div class="progress-bar">
                      <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
                    </div>
                    <span>{{ task.progress }}%</span>
                  </div>
                </div>
                <div class="info-item">
                  <label>创建时间</label>
                  <span>{{ formatDateTime(task.created_at) }}</span>
                </div>
                <div class="info-item">
                  <label>开始时间</label>
                  <span>{{ formatDateTime(task.started_at) }}</span>
                </div>
                <div class="info-item">
                  <label>完成时间</label>
                  <span>{{ formatDateTime(task.completed_at) }}</span>
                </div>
                <div class="info-item">
                  <label>重试次数</label>
                  <span>{{ task.retry_count || 0 }}</span>
                </div>
                <div v-if="task.video_id" class="info-item">
                  <label>关联视频</label>
                  <span class="mono">{{ task.video_id }}</span>
                </div>
                <div v-if="task.error" class="info-item full-width">
                  <label>错误信息</label>
                  <span class="error-text">{{ task.error }}</span>
                </div>
              </div>
            </div>
            
            <!-- Payload Tab -->
            <div v-show="activeTab === 'payload'" class="tab-content">
              <pre class="code-block">{{ formatPayload(task.payload) }}</pre>
            </div>
            
            <!-- Result Tab -->
            <div v-show="activeTab === 'result'" class="tab-content">
              <pre class="code-block">{{ formatResult(task.result) }}</pre>
            </div>
          </div>
          
          <div class="modal-footer">
            <button v-if="canRetry" class="btn btn-primary" @click="handleRetry">
              🔁 重试任务
            </button>
            <button v-if="canCancel" class="btn btn-danger" @click="handleCancel">
              ⏹️ 取消任务
            </button>
            <button class="btn btn-secondary" @click="handleClose">关闭</button>
          </div>
        </template>
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
  max-width: 640px;
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

.modal-loading {
  padding: 60px;
  text-align: center;
  color: var(--text-secondary);
}

.modal-tabs {
  display: flex;
  gap: 4px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
}

.tab-btn {
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
    color: var(--text-primary);
  }
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.tab-content {
  min-height: 200px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  
  &.full-width {
    grid-column: 1 / -1;
  }
  
  label {
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  
  span {
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .mono {
    font-family: monospace;
    font-size: 12px;
    word-break: break-all;
  }
  
  .error-text {
    color: var(--error);
    font-size: 13px;
  }
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  
  &.status-pending { background-color: rgba(245, 158, 11, 0.2); color: var(--warning); }
  &.status-running { background-color: rgba(59, 130, 246, 0.2); color: var(--info); }
  &.status-completed { background-color: rgba(34, 197, 94, 0.2); color: var(--success); }
  &.status-failed { background-color: rgba(239, 68, 68, 0.2); color: var(--error); }
  &.status-cancelled { background-color: rgba(102, 102, 102, 0.2); color: var(--text-muted); }
}

.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
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

.code-block {
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  font-family: monospace;
  font-size: 13px;
  color: var(--text-primary);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.btn {
  padding: 8px 16px;
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
  
  &.btn-danger {
    background-color: var(--error);
    color: white;
    
    &:hover {
      background-color: #dc2626;
    }
  }
}
</style>
