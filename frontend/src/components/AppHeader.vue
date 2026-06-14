<script setup>
/**
 * Application header component
 */
import { useAppStore } from '@/stores/app'
import { useTasksStore } from '@/stores/tasks'

const appStore = useAppStore()
const tasksStore = useTasksStore()
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <button class="menu-toggle" @click="appStore.toggleSidebar">
        <span class="icon">☰</span>
      </button>
      <h1 class="logo">SRT Flow</h1>
    </div>
    
    <div class="header-center">
      <!-- Search or breadcrumb can go here -->
    </div>
    
    <div class="header-right">
      <div class="task-indicator" v-if="tasksStore.runningTasks.length > 0">
        <span class="pulse"></span>
        <span class="count">{{ tasksStore.runningTasks.length }} 任务运行中</span>
      </div>
    </div>
  </header>
</template>

<style lang="scss" scoped>
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-toggle {
  background: none;
  border: none;
  color: var(--text-primary);
  font-size: 20px;
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  
  &:hover {
    background-color: var(--bg-hover);
  }
}

.logo {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.task-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background-color: var(--accent-color);
  border-radius: 16px;
  font-size: 13px;
  
  .pulse {
    width: 8px;
    height: 8px;
    background-color: #4ade80;
    border-radius: 50%;
    animation: pulse 1.5s infinite;
  }
  
  .count {
    color: var(--text-primary);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
