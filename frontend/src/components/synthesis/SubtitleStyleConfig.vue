<script setup>
/**
 * Subtitle Style Configuration Component
 * Configures font, color, position, and effects for subtitle rendering
 */
import { ref, computed, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  label: { type: String, default: '字幕样式' },
  compact: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue'])

// Default style values
const defaultStyle = {
  font_name: 'Microsoft YaHei',
  font_size: 24,
  font_color: '#FFFFFF',
  font_alpha: 1.0,
  outline_width: 2,
  outline_color: '#000000',
  shadow_enabled: true,
  shadow_color: '#000000',
  shadow_offset: 2,
  position: 'bottom',
  margin_v: 30,
  margin_h: 20,
  background_enabled: false,
  background_color: '#000000',
  background_alpha: 0.5
}

// Local style state
const style = ref({ ...defaultStyle, ...props.modelValue })

// Watch for external changes
watch(() => props.modelValue, (newVal) => {
  style.value = { ...defaultStyle, ...newVal }
}, { deep: true })

// Emit changes
watch(style, (newVal) => {
  emit('update:modelValue', { ...newVal })
}, { deep: true })

// Font options
const fontOptions = [
  { value: 'Microsoft YaHei', label: '微软雅黑' },
  { value: 'SimHei', label: '黑体' },
  { value: 'SimSun', label: '宋体' },
  { value: 'KaiTi', label: '楷体' },
  { value: 'Arial', label: 'Arial' },
  { value: 'Noto Sans CJK SC', label: 'Noto Sans CJK' }
]

// Position options
const positionOptions = [
  { value: 'top', label: '顶部' },
  { value: 'center', label: '居中' },
  { value: 'bottom', label: '底部' }
]

// Show advanced options
const showAdvanced = ref(false)
</script>

<template>
  <div class="style-config" :class="{ compact }">
    <div class="config-header" v-if="label">
      <span class="config-label">{{ label }}</span>
    </div>
    
    <div class="config-grid">
      <!-- Font Settings -->
      <div class="form-group">
        <label>字体</label>
        <select v-model="style.font_name" class="form-select">
          <option v-for="opt in fontOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
      
      <div class="form-group">
        <label>字号</label>
        <input 
          v-model.number="style.font_size" 
          type="number" 
          class="form-input"
          min="12"
          max="72"
        />
      </div>
      
      <div class="form-group">
        <label>字体颜色</label>
        <div class="color-input">
          <input 
            v-model="style.font_color" 
            type="color" 
            class="color-picker"
          />
          <input 
            v-model="style.font_color" 
            type="text" 
            class="form-input color-text"
            placeholder="#FFFFFF"
          />
        </div>
      </div>
      
      <div class="form-group">
        <label>位置</label>
        <select v-model="style.position" class="form-select">
          <option v-for="opt in positionOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>
    
    <!-- Advanced Options Toggle -->
    <details class="advanced-section" :open="showAdvanced">
      <summary @click.prevent="showAdvanced = !showAdvanced">
        {{ showAdvanced ? '收起高级选项' : '展开高级选项' }}
      </summary>
      
      <div class="advanced-content">
        <div class="config-grid">
          <!-- Outline Settings -->
          <div class="form-group">
            <label>边框宽度</label>
            <input 
              v-model.number="style.outline_width" 
              type="number" 
              class="form-input"
              min="0"
              max="10"
            />
          </div>
          
          <div class="form-group">
            <label>边框颜色</label>
            <div class="color-input">
              <input 
                v-model="style.outline_color" 
                type="color" 
                class="color-picker"
              />
              <input 
                v-model="style.outline_color" 
                type="text" 
                class="form-input color-text"
              />
            </div>
          </div>
          
          <!-- Shadow Settings -->
          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" v-model="style.shadow_enabled" />
              启用阴影
            </label>
          </div>
          
          <div class="form-group" v-if="style.shadow_enabled">
            <label>阴影偏移</label>
            <input 
              v-model.number="style.shadow_offset" 
              type="number" 
              class="form-input"
              min="0"
              max="10"
            />
          </div>
          
          <!-- Margin Settings -->
          <div class="form-group">
            <label>垂直边距</label>
            <input 
              v-model.number="style.margin_v" 
              type="number" 
              class="form-input"
              min="0"
              max="200"
            />
          </div>
          
          <div class="form-group">
            <label>水平边距</label>
            <input 
              v-model.number="style.margin_h" 
              type="number" 
              class="form-input"
              min="0"
              max="200"
            />
          </div>
          
          <!-- Background Settings -->
          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" v-model="style.background_enabled" />
              启用背景色
            </label>
          </div>
          
          <div class="form-group" v-if="style.background_enabled">
            <label>背景颜色</label>
            <div class="color-input">
              <input 
                v-model="style.background_color" 
                type="color" 
                class="color-picker"
              />
              <input 
                v-model="style.background_color" 
                type="text" 
                class="form-input color-text"
              />
            </div>
          </div>
          
          <div class="form-group" v-if="style.background_enabled">
            <label>背景透明度</label>
            <input 
              v-model.number="style.background_alpha" 
              type="range" 
              class="form-range"
              min="0"
              max="1"
              step="0.1"
            />
            <span class="range-value">{{ (style.background_alpha * 100).toFixed(0) }}%</span>
          </div>
          
          <div class="form-group">
            <label>字体透明度</label>
            <input 
              v-model.number="style.font_alpha" 
              type="range" 
              class="form-range"
              min="0"
              max="1"
              step="0.1"
            />
            <span class="range-value">{{ (style.font_alpha * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>
    </details>
  </div>
</template>

<style lang="scss" scoped>
.style-config {
  padding: 16px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  
  &.compact {
    padding: 12px;
    
    .config-grid {
      gap: 12px;
    }
  }
}

.config-header {
  margin-bottom: 12px;
}

.config-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.form-group {
  label {
    display: block;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 4px;
  }
  
  &.checkbox-group label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-primary);
    
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      accent-color: var(--accent-color);
    }
  }
}

.form-select, .form-input {
  width: 100%;
  padding: 8px 10px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.color-input {
  display: flex;
  gap: 8px;
  align-items: center;
}

.color-picker {
  width: 36px;
  height: 32px;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  cursor: pointer;
  background: none;
  
  &::-webkit-color-swatch-wrapper {
    padding: 0;
  }
  
  &::-webkit-color-swatch {
    border: none;
    border-radius: 2px;
  }
}

.color-text {
  flex: 1;
  font-family: monospace;
}

.form-range {
  width: calc(100% - 50px);
  accent-color: var(--accent-color);
}

.range-value {
  display: inline-block;
  width: 40px;
  text-align: right;
  font-size: 12px;
  color: var(--text-muted);
}

.advanced-section {
  margin-top: 16px;
  
  summary {
    cursor: pointer;
    font-size: 13px;
    color: var(--text-secondary);
    padding: 8px 0;
    user-select: none;
    
    &:hover {
      color: var(--accent-color);
    }
  }
}

.advanced-content {
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}
</style>
