<script setup>
/**
 * Subtitle Style Preview Component
 * 
 * Uses FFmpeg backend to generate accurate subtitle preview.
 * Falls back to CSS simulation if API fails.
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import api from '@/api'

const props = defineProps({
  // Translated subtitle style
  translatedFont: { type: String, default: 'Microsoft YaHei' },
  translatedFontSize: { type: Number, default: 24 },
  translatedBold: { type: Boolean, default: false },
  translatedColor: { type: String, default: '#FFFACD' },
  translatedAlpha: { type: Number, default: 0.85 },
  translatedOutlineColor: { type: String, default: '#000000' },
  translatedOutlineWidth: { type: Number, default: 2 },
  translatedShadowEnabled: { type: Boolean, default: false },
  translatedShadowOffset: { type: Number, default: 1 },
  translatedMarginV: { type: Number, default: 60 },
  translatedBackgroundEnabled: { type: Boolean, default: false },
  translatedBackgroundColor: { type: String, default: '#000000' },
  translatedBackgroundAlpha: { type: Number, default: 0.5 },
  translatedBackgroundPaddingH: { type: Number, default: 10 },
  translatedBackgroundPaddingV: { type: Number, default: 5 },
  
  // Original subtitle style
  originalFont: { type: String, default: 'Microsoft YaHei' },
  originalFontSize: { type: Number, default: 18 },
  originalBold: { type: Boolean, default: false },
  originalColor: { type: String, default: '#FFFFFF' },
  originalAlpha: { type: Number, default: 0.85 },
  originalOutlineColor: { type: String, default: '#000000' },
  originalOutlineWidth: { type: Number, default: 1 },
  originalShadowEnabled: { type: Boolean, default: false },
  originalShadowOffset: { type: Number, default: 1 },
  originalMarginV: { type: Number, default: 30 },
  originalBackgroundEnabled: { type: Boolean, default: false },
  originalBackgroundColor: { type: String, default: '#000000' },
  originalBackgroundAlpha: { type: Number, default: 0.5 },
  originalBackgroundPaddingH: { type: Number, default: 10 },
  originalBackgroundPaddingV: { type: Number, default: 5 },
})

const previewUrl = ref('')
const loading = ref(false)
const error = ref(false)

// Resolution presets
const resolutionOptions = [
  { label: '720P', width: 1280, height: 720 },
  { label: '1080P', width: 1920, height: 1080 },
  { label: '4K', width: 3840, height: 2160 },
]
const selectedResolution = ref(resolutionOptions[1]) // Default 1080P

// Simple debounce implementation
function debounce(fn, delay) {
  let timer = null
  return function(...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

// Build request payload from props
const requestPayload = computed(() => ({
  translated_style: {
    font_name: props.translatedFont,
    font_size: props.translatedFontSize,
    font_bold: props.translatedBold,
    font_color: props.translatedColor,
    font_alpha: props.translatedAlpha,
    outline_width: props.translatedOutlineWidth,
    outline_color: props.translatedOutlineColor,
    shadow_enabled: props.translatedShadowEnabled,
    shadow_offset: props.translatedShadowOffset,
    margin_v: props.translatedMarginV,
    background_enabled: props.translatedBackgroundEnabled,
    background_color: props.translatedBackgroundColor,
    background_alpha: props.translatedBackgroundAlpha,
    background_padding_h: props.translatedBackgroundPaddingH,
    background_padding_v: props.translatedBackgroundPaddingV,
  },
  original_style: {
    font_name: props.originalFont,
    font_size: props.originalFontSize,
    font_bold: props.originalBold,
    font_color: props.originalColor,
    font_alpha: props.originalAlpha,
    outline_width: props.originalOutlineWidth,
    outline_color: props.originalOutlineColor,
    shadow_enabled: props.originalShadowEnabled,
    shadow_offset: props.originalShadowOffset,
    margin_v: props.originalMarginV,
    background_enabled: props.originalBackgroundEnabled,
    background_color: props.originalBackgroundColor,
    background_alpha: props.originalBackgroundAlpha,
    background_padding_h: props.originalBackgroundPaddingH,
    background_padding_v: props.originalBackgroundPaddingV,
  },
  width: selectedResolution.value.width,
  height: selectedResolution.value.height,
}))

// Fetch preview from backend
async function fetchPreview() {
  loading.value = true
  error.value = false
  
  try {
    const response = await api.post('/system/subtitle-preview', requestPayload.value, {
      responseType: 'blob'
    })
    
    // Revoke old URL to prevent memory leak
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value)
    }
    
    // Create blob URL from response
    previewUrl.value = URL.createObjectURL(response)
  } catch (e) {
    console.error('Failed to fetch subtitle preview:', e)
    error.value = true
  } finally {
    loading.value = false
  }
}

// Debounced fetch to avoid too many requests
const debouncedFetch = debounce(fetchPreview, 500)

// Watch all props and refetch preview
watch(requestPayload, () => {
  debouncedFetch()
}, { deep: true, immediate: true })

// Cleanup on unmount
onUnmounted(() => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
})

// ============================================================================
// CSS Fallback (used when API fails)
// ============================================================================

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function generateOutlineShadow(color, width) {
  if (width <= 0) return 'none'
  const shadows = []
  const directions = [
    [1, 0], [0, 1], [-1, 0], [0, -1],
    [1, 1], [-1, 1], [1, -1], [-1, -1]
  ]
  for (let i = 1; i <= width; i++) {
    for (const [dx, dy] of directions) {
      shadows.push(`${color} ${dx * i}px ${dy * i}px 0`)
    }
  }
  return shadows.join(', ')
}

const translatedStyle = computed(() => ({
  fontFamily: `"${props.translatedFont}", sans-serif`,
  fontSize: `${props.translatedFontSize}px`,
  fontWeight: props.translatedBold ? 'bold' : 'normal',
  color: hexToRgba(props.translatedColor, props.translatedAlpha),
  textShadow: generateOutlineShadow(props.translatedOutlineColor, props.translatedOutlineWidth),
  bottom: `${props.translatedMarginV}px`,
  backgroundColor: props.translatedBackgroundEnabled 
    ? hexToRgba(props.translatedBackgroundColor, props.translatedBackgroundAlpha)
    : 'transparent',
  padding: props.translatedBackgroundEnabled ? '2px 4px' : '0',
}))

const originalStyle = computed(() => ({
  fontFamily: `"${props.originalFont}", sans-serif`,
  fontSize: `${props.originalFontSize}px`,
  fontWeight: props.originalBold ? 'bold' : 'normal',
  color: hexToRgba(props.originalColor, props.originalAlpha),
  textShadow: generateOutlineShadow(props.originalOutlineColor, props.originalOutlineWidth),
  bottom: `${props.originalMarginV}px`,
  backgroundColor: props.originalBackgroundEnabled
    ? hexToRgba(props.originalBackgroundColor, props.originalBackgroundAlpha)
    : 'transparent',
  padding: props.originalBackgroundEnabled ? '2px 4px' : '0',
}))
</script>

<template>
  <div class="subtitle-preview">
    <div class="preview-header">
      <div class="preview-label">字幕预览</div>
      <div class="resolution-switcher">
        <button
          v-for="option in resolutionOptions"
          :key="option.label"
          class="resolution-btn"
          :class="{ active: selectedResolution.label === option.label }"
          @click="selectedResolution = option"
        >
          {{ option.label }}
        </button>
      </div>
      <div v-if="loading" class="preview-status loading">生成中...</div>
      <div v-else-if="error" class="preview-status error">预览生成失败</div>
    </div>
    <div class="preview-container">
      <!-- FFmpeg rendered preview -->
      <img 
        v-if="previewUrl && !error" 
        :src="previewUrl" 
        class="preview-image"
        :class="{ 'is-loading': loading }"
        alt="字幕预览"
      />
      
      <!-- CSS fallback when API fails -->
      <div v-else class="video-frame fallback">
        <div class="video-content">
          <span class="play-icon">▶</span>
          <span class="video-text">视频画面</span>
        </div>
        <div class="subtitle translated" :style="translatedStyle">
          这是翻译后的字幕示例
        </div>
        <div class="subtitle original" :style="originalStyle">
          This is the original subtitle example
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.subtitle-preview {
  margin: 20px 0;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.preview-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.resolution-switcher {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.resolution-btn {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }
  
  &.active {
    background: var(--color-primary);
    border-color: var(--color-primary);
    color: #fff;
  }
}

.preview-status {
  font-size: 12px;
  
  &.loading {
    color: var(--text-secondary);
  }
  
  &.error {
    color: var(--color-warning);
  }
}

.preview-container {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background: #1a1a2e;
}

.preview-image {
  display: block;
  width: 100%;
  height: auto;
  aspect-ratio: 16 / 9;
  object-fit: contain;
  transition: opacity 0.2s;
  
  &.is-loading {
    opacity: 0.6;
  }
}

.video-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  &.fallback {
    border: 2px dashed var(--border-color);
    border-radius: 0;
  }
}

.video-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.3);
  
  .play-icon {
    font-size: 48px;
  }
  
  .video-text {
    font-size: 14px;
  }
}

.subtitle {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  white-space: nowrap;
  max-width: 90%;
  overflow: hidden;
  text-overflow: ellipsis;
  border-radius: 0;
  
  &.translated {
    z-index: 2;
  }
  
  &.original {
    z-index: 1;
  }
}
</style>
