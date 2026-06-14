<script setup>
/**
 * Home dashboard view
 */
import { ref, onMounted } from 'vue'
import api from '@/api'

const stats = ref({
  totalVideos: 0,
  runningTasks: 0,
  completedToday: 0
})

const loading = ref(false)

async function fetchStats() {
  loading.value = true
  try {
    const { data } = await api.get('/stats')
    if (data) {
      stats.value = data
    }
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStats()
})
</script>

<template>
  <div class="home-view">
    <h2 class="page-title">仪表盘</h2>
    
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">🎬</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.totalVideos }}</span>
          <span class="stat-label">视频总数</span>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">⚡</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.runningTasks }}</span>
          <span class="stat-label">运行中任务</span>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">✅</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.completedToday }}</span>
          <span class="stat-label">今日完成</span>
        </div>
      </div>
    </div>
    
    <div class="quick-actions">
      <h3>快速操作</h3>
      <div class="action-buttons">
        <RouterLink to="/videos" class="action-btn">
          <span class="icon">📥</span>
          <span>下载视频</span>
        </RouterLink>
        <RouterLink to="/tasks" class="action-btn">
          <span class="icon">📋</span>
          <span>查看任务</span>
        </RouterLink>
        <RouterLink to="/settings" class="action-btn">
          <span class="icon">⚙️</span>
          <span>系统设置</span>
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.home-view {
  max-width: 1200px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 24px;
  color: var(--text-primary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background-color: var(--bg-secondary);
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.stat-icon {
  font-size: 32px;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.quick-actions {
  h3 {
    font-size: 18px;
    margin-bottom: 16px;
    color: var(--text-primary);
  }
}

.action-buttons {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  text-decoration: none;
  transition: all 0.2s ease;
  
  &:hover {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
  }
  
  .icon {
    font-size: 18px;
  }
}
</style>
