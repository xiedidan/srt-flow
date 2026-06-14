<script setup>
/**
 * Main application layout with header, sidebar, and content area
 */
import { useAppStore } from '@/stores/app'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'

const appStore = useAppStore()
</script>

<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': appStore.sidebarCollapsed }">
    <AppHeader />
    <div class="app-body">
      <AppSidebar />
      <main class="app-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--bg-primary);
}

.app-body {
  display: flex;
  flex: 1;
  padding-top: var(--header-height);
}

.app-content {
  flex: 1;
  margin-left: var(--sidebar-width);
  padding: 24px;
  transition: margin-left 0.3s ease;
  overflow-y: auto;
}

.sidebar-collapsed .app-content {
  margin-left: var(--sidebar-collapsed-width);
}
</style>
