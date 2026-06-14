/**
 * Vue Router configuration
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/videos',
    name: 'videos',
    component: () => import('@/views/VideosView.vue'),
    meta: { title: '视频管理' }
  },
  {
    path: '/asr',
    name: 'asr-tasks',
    component: () => import('@/views/AsrTasksView.vue'),
    meta: { title: '语音识别', taskType: 'asr' }
  },
  {
    path: '/translate',
    name: 'translate-tasks',
    component: () => import('@/views/TranslateTasksView.vue'),
    meta: { title: '字幕翻译', taskType: 'translate' }
  },
  {
    path: '/tts',
    name: 'tts-tasks',
    component: () => import('@/views/TtsTasksView.vue'),
    meta: { title: '语音合成', taskType: 'tts' }
  },
  {
    path: '/synthesis',
    name: 'synthesis-tasks',
    component: () => import('@/views/SynthesisTasksView.vue'),
    meta: { title: '视频合成', taskType: 'synthesis' }
  },
  {
    path: '/asset',
    name: 'asset-tasks',
    component: () => import('@/views/AssetTasksView.vue'),
    meta: { title: '素材生成', taskType: 'asset' }
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('@/views/TasksView.vue'),
    meta: { title: '任务管理' }
  },
  {
    path: '/settings',
    redirect: '/settings/global'
  },
  {
    path: '/settings/:section',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '系统设置' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// Update document title on navigation
router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - SRT Flow` : 'SRT Flow'
  next()
})

export default router
