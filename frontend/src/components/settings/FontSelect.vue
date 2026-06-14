<script setup>
/**
 * Font Select Component
 * Fetches available system fonts and provides categorized selection
 */
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/api'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const loading = ref(true)
const fonts = ref([])
const categorized = ref({ chinese: [], english: [], other: [] })
const recommended = ref([])
const searchQuery = ref('')
const showDropdown = ref(false)

const selectedFont = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// Filter fonts based on search query
const filteredFonts = computed(() => {
  if (!searchQuery.value.trim()) {
    return {
      recommended: recommended.value,
      chinese: categorized.value.chinese,
      english: categorized.value.english,
      other: categorized.value.other
    }
  }
  
  const query = searchQuery.value.toLowerCase()
  const filter = (arr) => arr.filter(f => f.toLowerCase().includes(query))
  
  return {
    recommended: filter(recommended.value),
    chinese: filter(categorized.value.chinese),
    english: filter(categorized.value.english),
    other: filter(categorized.value.other)
  }
})

const hasResults = computed(() => {
  const f = filteredFonts.value
  return f.recommended.length > 0 || f.chinese.length > 0 || f.english.length > 0 || f.other.length > 0
})

async function loadFonts() {
  loading.value = true
  try {
    const { data } = await api.get('/system/fonts')
    fonts.value = data.fonts || []
    categorized.value = data.categorized || { chinese: [], english: [], other: [] }
    recommended.value = data.recommended || []
  } catch (e) {
    console.error('Failed to load fonts:', e)
    // Fallback to common fonts
    recommended.value = ['Microsoft YaHei', 'SimHei', 'Arial', 'Helvetica']
  } finally {
    loading.value = false
  }
}

function selectFont(font) {
  selectedFont.value = font
  showDropdown.value = false
  searchQuery.value = ''
}

function handleInputFocus() {
  showDropdown.value = true
}

function handleClickOutside(e) {
  const el = e.target.closest('.font-select')
  if (!el) {
    showDropdown.value = false
  }
}

onMounted(() => {
  loadFonts()
  document.addEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="font-select">
    <div class="input-wrapper">
      <input
        v-model="selectedFont"
        type="text"
        class="font-input"
        placeholder="选择或输入字体名称..."
        @focus="handleInputFocus"
        @input="showDropdown = true"
      />
      <span class="dropdown-icon" @click="showDropdown = !showDropdown">▼</span>
    </div>
    
    <div v-if="showDropdown" class="dropdown-panel">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        placeholder="搜索字体..."
      />
      
      <div v-if="loading" class="loading">加载中...</div>
      
      <div v-else-if="!hasResults" class="no-results">
        未找到匹配的字体
      </div>
      
      <div v-else class="font-list">
        <!-- Recommended -->
        <div v-if="filteredFonts.recommended.length > 0" class="font-group">
          <div class="group-label">⭐ 推荐字体</div>
          <div
            v-for="font in filteredFonts.recommended"
            :key="'rec-' + font"
            class="font-item"
            :class="{ selected: font === selectedFont }"
            :style="{ fontFamily: font }"
            @click="selectFont(font)"
          >
            {{ font }}
          </div>
        </div>
        
        <!-- Chinese fonts -->
        <div v-if="filteredFonts.chinese.length > 0" class="font-group">
          <div class="group-label">🇨🇳 中文字体</div>
          <div
            v-for="font in filteredFonts.chinese"
            :key="'zh-' + font"
            class="font-item"
            :class="{ selected: font === selectedFont }"
            :style="{ fontFamily: font }"
            @click="selectFont(font)"
          >
            {{ font }}
          </div>
        </div>
        
        <!-- English fonts -->
        <div v-if="filteredFonts.english.length > 0" class="font-group">
          <div class="group-label">🇺🇸 英文字体</div>
          <div
            v-for="font in filteredFonts.english"
            :key="'en-' + font"
            class="font-item"
            :class="{ selected: font === selectedFont }"
            :style="{ fontFamily: font }"
            @click="selectFont(font)"
          >
            {{ font }}
          </div>
        </div>
        
        <!-- Other fonts -->
        <div v-if="filteredFonts.other.length > 0" class="font-group">
          <div class="group-label">📝 其他字体</div>
          <div
            v-for="font in filteredFonts.other"
            :key="'other-' + font"
            class="font-item"
            :class="{ selected: font === selectedFont }"
            :style="{ fontFamily: font }"
            @click="selectFont(font)"
          >
            {{ font }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.font-select {
  position: relative;
  width: 100%;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.font-input {
  width: 100%;
  padding: 10px 32px 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.dropdown-icon {
  position: absolute;
  right: 10px;
  color: var(--text-muted);
  font-size: 10px;
  cursor: pointer;
  user-select: none;
}

.dropdown-panel {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 100;
  max-height: 350px;
  display: flex;
  flex-direction: column;
}

.search-input {
  margin: 8px;
  padding: 8px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  
  &:focus {
    outline: none;
    border-color: var(--accent-color);
  }
}

.loading, .no-results {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.font-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.font-group {
  margin-bottom: 8px;
}

.group-label {
  padding: 6px 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background-color: var(--bg-primary);
  border-radius: 4px;
  margin-bottom: 4px;
  position: sticky;
  top: 0;
}

.font-item {
  padding: 8px 12px;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.15s;
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.selected {
    background-color: rgba(59, 130, 246, 0.15);
    color: var(--accent-color);
  }
}
</style>
