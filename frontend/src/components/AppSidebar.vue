<script setup>
/**
 * Application sidebar navigation with collapsible sub-menus
 */
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

// Track which menu is expanded
const expandedMenu = ref(null)

// Navigation structure with sub-menus
const navItems = [
  { 
    key: 'home',
    name: '首页', 
    icon: '🏠',
    path: '/'
  },
  { 
    key: 'videos',
    name: '视频管理', 
    icon: '🎬',
    path: '/videos'
  },
  { 
    key: 'asr',
    name: '语音识别', 
    icon: '🎤',
    path: '/asr'
  },
  { 
    key: 'translate',
    name: '字幕翻译', 
    icon: '🌐',
    path: '/translate'
  },
  { 
    key: 'tts',
    name: '语音合成', 
    icon: '🔊',
    path: '/tts'
  },
  { 
    key: 'synthesis',
    name: '视频合成', 
    icon: '🎞️',
    path: '/synthesis'
  },
  { 
    key: 'asset',
    name: '素材生成', 
    icon: '🎨',
    path: '/asset'
  },
  { 
    key: 'tasks',
    name: '任务管理', 
    icon: '📋',
    path: '/tasks'
  },
  { 
    key: 'settings',
    name: '系统设置', 
    icon: '⚙️',
    children: [
      { path: '/settings/global', name: '通用设置' },
      { path: '/settings/ai-providers', name: 'AI 服务商' },
      { path: '/settings/reference-audio', name: '参考音频' },
      { path: '/settings/download', name: '下载服务' },
      { path: '/settings/asr', name: '语音识别' },
      { path: '/settings/translate', name: '翻译服务' },
      { path: '/settings/tts', name: '语音合成' },
      { path: '/settings/synthesis', name: '视频合成' },
      { path: '/settings/asset', name: '素材生成' }
    ]
  }
]

// Toggle menu expansion
function toggleMenu(key) {
  if (expandedMenu.value === key) {
    expandedMenu.value = null
  } else {
    expandedMenu.value = key
  }
}

// Handle menu item click
function handleMenuClick(item) {
  if (item.children) {
    toggleMenu(item.key)
  } else if (item.path) {
    router.push(item.path)
  }
}

// Check if a menu item or its children is active
function isMenuActive(item) {
  if (item.path && !item.children) {
    return route.path === item.path || route.fullPath === item.path
  }
  if (item.children) {
    return item.children.some(child => 
      route.path === child.path.split('?')[0] || route.fullPath === child.path
    )
  }
  return false
}

// Check if a sub-item is active
function isSubItemActive(subItem) {
  const subPath = subItem.path.split('?')[0]
  const subQuery = new URLSearchParams(subItem.path.split('?')[1] || '')
  
  if (route.path !== subPath) return false
  
  // If sub-item has query params, check them
  if (subItem.path.includes('?')) {
    for (const [key, value] of subQuery.entries()) {
      if (route.query[key] !== value) return false
    }
    return true
  }
  
  // No query params in sub-item, active if path matches and no conflicting query
  return true
}
</script>

<template>
  <aside class="app-sidebar" :class="{ collapsed: appStore.sidebarCollapsed }">
    <nav class="sidebar-nav">
      <div 
        v-for="item in navItems" 
        :key="item.key" 
        class="nav-group"
        :class="{ expanded: expandedMenu === item.key, active: isMenuActive(item) }"
      >
        <!-- Primary menu item -->
        <div 
          class="nav-item"
          :class="{ active: isMenuActive(item) && !item.children }"
          @click="handleMenuClick(item)"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-text">{{ item.name }}</span>
          <span v-if="item.children" class="nav-arrow">
            {{ expandedMenu === item.key ? '▼' : '▶' }}
          </span>
        </div>
        
        <!-- Sub-menu -->
        <div v-if="item.children" class="nav-submenu" :class="{ open: expandedMenu === item.key }">
          <RouterLink
            v-for="child in item.children"
            :key="child.path"
            :to="child.path"
            class="nav-subitem"
            :class="{ active: isSubItemActive(child) }"
          >
            {{ child.name }}
          </RouterLink>
        </div>
      </div>
    </nav>
  </aside>
</template>

<style lang="scss" scoped>
.app-sidebar {
  position: fixed;
  top: var(--header-height);
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background-color: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  transition: width 0.3s ease;
  overflow-y: auto;
  overflow-x: hidden;
  z-index: 90;
  
  &.collapsed {
    width: var(--sidebar-collapsed-width);
    
    .nav-text,
    .nav-arrow {
      opacity: 0;
      width: 0;
    }
    
    .nav-submenu {
      display: none;
    }
  }
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  padding: 16px 8px 80px;
  gap: 2px;
}

.nav-group {
  &.active > .nav-item {
    color: var(--accent-color);
  }
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
  
  &.active {
    color: var(--accent-color);
    background-color: var(--bg-hover);
  }
}

.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.nav-text {
  font-size: 14px;
  white-space: nowrap;
  flex: 1;
  transition: opacity 0.3s ease;
}

.nav-arrow {
  font-size: 10px;
  color: var(--text-muted);
  transition: opacity 0.3s ease;
}

.nav-submenu {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease;
  
  &.open {
    max-height: 500px;
  }
}

.nav-subitem {
  display: block;
  padding: 10px 16px 10px 46px;
  font-size: 13px;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: 6px;
  transition: all 0.2s ease;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
  
  &.active {
    color: var(--accent-color);
    background-color: var(--bg-hover);
  }
}
</style>
