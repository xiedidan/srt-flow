/**
 * Videos state store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { videosApi } from '@/api/videos'

export const useVideosStore = defineStore('videos', () => {
  // State
  const videos = ref([])
  const currentVideo = ref(null)
  const loading = ref(false)
  const pagination = ref({
    page: 1,
    pageSize: 20,
    total: 0
  })
  const filters = ref({
    tag: null,
    keyword: ''
  })
  const selectedIds = ref([])

  // Getters
  const totalPages = computed(() =>
    Math.ceil(pagination.value.total / pagination.value.pageSize)
  )

  const allTags = computed(() => {
    const tagSet = new Set()
    videos.value.forEach(v => {
      (v.tags || []).forEach(t => tagSet.add(t))
    })
    return Array.from(tagSet).sort()
  })

  const isAllSelected = computed(() =>
    videos.value.length > 0 && selectedIds.value.length === videos.value.length
  )

  // Actions
  async function fetchVideos(params = {}) {
    loading.value = true
    try {
      const queryParams = {
        page: pagination.value.page,
        page_size: pagination.value.pageSize,
        ...filters.value,
        ...params
      }
      // Remove null/undefined/empty values
      Object.keys(queryParams).forEach(key => {
        if (queryParams[key] === null || queryParams[key] === undefined || queryParams[key] === '') {
          delete queryParams[key]
        }
      })

      const response = await videosApi.list(queryParams)
      videos.value = response.data?.items || []
      pagination.value.total = response.data?.total || 0
    } finally {
      loading.value = false
    }
  }

  async function fetchVideo(videoId) {
    loading.value = true
    try {
      const response = await videosApi.get(videoId)
      currentVideo.value = response.data
      return response.data
    } finally {
      loading.value = false
    }
  }

  async function updateVideo(videoId, data) {
    const response = await videosApi.update(videoId, data)
    // Update in list
    const idx = videos.value.findIndex(v => v.id === videoId)
    if (idx !== -1) {
      videos.value[idx] = { ...videos.value[idx], ...response.data }
    }
    if (currentVideo.value?.id === videoId) {
      currentVideo.value = { ...currentVideo.value, ...response.data }
    }
    return response.data
  }

  async function getFileContent(videoId, fileType) {
    const response = await videosApi.getFileContent(videoId, fileType)
    return response.data
  }

  async function saveFileContent(videoId, fileType, content) {
    const response = await videosApi.saveFileContent(videoId, fileType, content)
    return response.data
  }

  function setPage(page) {
    pagination.value.page = page
    fetchVideos()
  }

  function setFilters(newFilters) {
    filters.value = { ...filters.value, ...newFilters }
    pagination.value.page = 1
    fetchVideos()
  }

  function clearCurrentVideo() {
    currentVideo.value = null
  }

  // Selection
  function toggleSelect(videoId) {
    const idx = selectedIds.value.indexOf(videoId)
    if (idx === -1) {
      selectedIds.value.push(videoId)
    } else {
      selectedIds.value.splice(idx, 1)
    }
  }

  function toggleSelectAll() {
    if (isAllSelected.value) {
      selectedIds.value = []
    } else {
      selectedIds.value = videos.value.map(v => v.id)
    }
  }

  function clearSelection() {
    selectedIds.value = []
  }

  // Update download progress from WebSocket
  function updateDownloadProgress(taskId, progress, status) {
    // Find video with matching download task (task_id field from API)
    const video = videos.value.find(v => 
      v.is_downloading && v.task_id === taskId
    )
    if (video) {
      video.download_progress = progress
      if (status) video.download_status = status
    }
  }

  // Update download metadata from WebSocket (title, thumbnail, etc.)
  function updateDownloadMetadata(taskId, metadata) {
    // Find video with matching download task
    const video = videos.value.find(v => 
      v.is_downloading && v.task_id === taskId
    )
    if (video && metadata) {
      if (metadata.title) video.title = metadata.title
      if (metadata.thumbnail_url) video.thumbnail_url = metadata.thumbnail_url
      if (metadata.duration) video.duration = metadata.duration
      if (metadata.channel_name) video.channel_name = metadata.channel_name
    }
  }

  // Update video from WebSocket task update
  function updateFromTaskUpdate(taskData) {
    const { task_id, task_type, status } = taskData
    
    // Only handle download tasks
    if (task_type !== 'download') return
    
    // Find video by task_id
    const video = videos.value.find(v => 
      v.is_downloading && v.task_id === task_id
    )
    
    if (video) {
      video.download_status = status
      
      // If completed or failed, refresh to get updated video data
      if (status === 'completed' || status === 'failed') {
        setTimeout(() => fetchVideos(), 1000)
      }
    }
  }

  return {
    videos,
    currentVideo,
    loading,
    pagination,
    filters,
    selectedIds,
    totalPages,
    allTags,
    isAllSelected,
    fetchVideos,
    fetchVideo,
    updateVideo,
    getFileContent,
    saveFileContent,
    setPage,
    setFilters,
    clearCurrentVideo,
    toggleSelect,
    toggleSelectAll,
    clearSelection,
    updateDownloadProgress,
    updateDownloadMetadata,
    updateFromTaskUpdate
  }
})
