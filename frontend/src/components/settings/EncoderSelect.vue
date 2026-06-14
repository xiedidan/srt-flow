<script setup>
/**
 * Video Encoder Select Component
 * Fetches GPU info and shows available encoders
 */
import { ref, computed, onMounted } from 'vue'
import api from '@/api'

const props = defineProps({
  modelValue: {
    type: String,
    default: 'libx264'
  }
})

const emit = defineEmits(['update:modelValue'])

const loading = ref(true)
const gpuInfo = ref(null)

const selectedEncoder = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// All encoder options with availability status
const encoderOptions = computed(() => {
  const nvencAvailable = gpuInfo.value?.nvenc_available || false
  
  return [
    { 
      value: 'libx264', 
      label: 'H.264 (CPU)', 
      available: true,
      description: '兼容性最好，适合大多数场景'
    },
    { 
      value: 'h264_nvenc', 
      label: 'H.264 NVENC (GPU)', 
      available: nvencAvailable,
      description: nvencAvailable ? 'NVIDIA GPU 加速，速度快' : '需要 NVIDIA 显卡'
    },
    { 
      value: 'libx265', 
      label: 'H.265/HEVC (CPU)', 
      available: true,
      description: '压缩率更高，但浏览器兼容性较差'
    },
    { 
      value: 'hevc_nvenc', 
      label: 'H.265 NVENC (GPU)', 
      available: nvencAvailable,
      description: nvencAvailable ? 'NVIDIA GPU 加速 HEVC 编码' : '需要 NVIDIA 显卡'
    }
  ]
})

async function loadGpuInfo() {
  loading.value = true
  try {
    const { data } = await api.get('/system/gpu')
    gpuInfo.value = data
  } catch (e) {
    console.error('Failed to load GPU info:', e)
    gpuInfo.value = { gpu_available: false, nvenc_available: false }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadGpuInfo()
})
</script>

<template>
  <div class="encoder-select">
    <div v-if="loading" class="loading">检测 GPU...</div>
    
    <template v-else>
      <!-- GPU Status -->
      <div class="gpu-status" :class="{ available: gpuInfo?.gpu_available }">
        <span class="status-icon">{{ gpuInfo?.gpu_available ? '🎮' : '💻' }}</span>
        <span class="status-text">
          {{ gpuInfo?.gpu_available ? `检测到 GPU: ${gpuInfo.gpu_name}` : '未检测到 NVIDIA GPU' }}
        </span>
      </div>
      
      <!-- Encoder Options -->
      <div class="encoder-options">
        <label
          v-for="opt in encoderOptions"
          :key="opt.value"
          class="encoder-option"
          :class="{ 
            selected: selectedEncoder === opt.value,
            disabled: !opt.available
          }"
        >
          <input
            type="radio"
            :value="opt.value"
            v-model="selectedEncoder"
            :disabled="!opt.available"
          />
          <div class="option-content">
            <div class="option-label">
              {{ opt.label }}
              <span v-if="!opt.available" class="unavailable-badge">不可用</span>
              <span v-else-if="opt.value.includes('nvenc')" class="gpu-badge">GPU</span>
            </div>
            <div class="option-desc">{{ opt.description }}</div>
          </div>
        </label>
      </div>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.encoder-select {
  width: 100%;
}

.loading {
  padding: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.gpu-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  
  &.available {
    background-color: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.3);
    color: var(--success);
  }
  
  .status-icon {
    font-size: 16px;
  }
}

.encoder-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.encoder-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background-color: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  input[type="radio"] {
    margin-top: 2px;
    accent-color: var(--accent-color);
  }
  
  &:hover:not(.disabled) {
    border-color: var(--accent-color);
  }
  
  &.selected {
    border-color: var(--accent-color);
    background-color: rgba(59, 130, 246, 0.05);
  }
  
  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    
    input[type="radio"] {
      cursor: not-allowed;
    }
  }
}

.option-content {
  flex: 1;
}

.option-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.option-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.gpu-badge {
  padding: 2px 6px;
  background-color: rgba(34, 197, 94, 0.15);
  color: var(--success);
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.unavailable-badge {
  padding: 2px 6px;
  background-color: rgba(239, 68, 68, 0.15);
  color: var(--error);
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}
</style>
