<script setup>
/**
 * TTS Voice Select Component
 * 
 * Provides voice selection for online TTS services:
 * - Azure TTS
 * - Edge TTS
 * - Volc TTS
 */
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  modelValue: String,
  engine: String  // azure_tts, edge_tts, volc_tts
})

const emit = defineEmits(['update:modelValue'])

const searchQuery = ref('')
const showDropdown = ref(false)

// Voice definitions for each engine
const azureVoices = [
  { name: 'zh-CN-XiaoxiaoNeural', label: '晓晓' },
  { name: 'zh-CN-XiaoxiaoMultilingualNeural', label: '晓晓 多语言' },
  { name: 'zh-CN-YunxiNeural', label: '云希' },
  { name: 'zh-CN-YunjianNeural', label: '云健' },
  { name: 'zh-CN-XiaoyiNeural', label: '晓伊' },
  { name: 'zh-CN-YunyangNeural', label: '云扬' },
  { name: 'zh-CN-XiaochenNeural', label: '晓辰' },
  { name: 'zh-CN-XiaochenMultilingualNeural', label: '晓辰 多语言' },
  { name: 'zh-CN-XiaohanNeural', label: '晓涵' },
  { name: 'zh-CN-XiaomengNeural', label: '晓梦' },
  { name: 'zh-CN-XiaomoNeural', label: '晓墨' },
  { name: 'zh-CN-XiaoqiuNeural', label: '晓秋' },
  { name: 'zh-CN-XiaorouNeural', label: '晓柔' },
  { name: 'zh-CN-XiaoruiNeural', label: '晓睿' },
  { name: 'zh-CN-XiaoshuangNeural', label: '晓双' },
  { name: 'zh-CN-XiaoxiaoDialectsNeural', label: '晓晓 方言' },
  { name: 'zh-CN-XiaoyanNeural', label: '晓颜' },
  { name: 'zh-CN-XiaoyouNeural', label: '晓悠' },
  { name: 'zh-CN-XiaoyuMultilingualNeural', label: '晓宇 多语言' },
  { name: 'zh-CN-XiaozhenNeural', label: '晓甄' },
  { name: 'zh-CN-YunfengNeural', label: '云枫' },
  { name: 'zh-CN-YunhaoNeural', label: '云皓' },
  { name: 'zh-CN-YunjieNeural', label: '云杰' },
  { name: 'zh-CN-YunxiaNeural', label: '云夏' },
  { name: 'zh-CN-YunyeNeural', label: '云野' },
  { name: 'zh-CN-YunyiMultilingualNeural', label: '云逸 多语言' },
  { name: 'zh-CN-YunzeNeural', label: '云泽' },
  { name: 'zh-CN-YunfanMultilingualNeural', label: 'Yunfan 多语言' },
  { name: 'zh-CN-YunxiaoMultilingualNeural', label: 'Yunxiao 多语言' }
]

const edgeVoices = [
  { name: 'zh-CN-XiaoxiaoNeural', label: '晓晓 中文 女' },
  { name: 'zh-CN-XiaoyiNeural', label: '晓依 中文 女' },
  { name: 'zh-CN-YunjianNeural', label: '云健 中文 男' },
  { name: 'zh-CN-YunxiNeural', label: '云希 中文 男' },
  { name: 'zh-CN-YunxiaNeural', label: '云夏 中文 男' },
  { name: 'zh-CN-YunyangNeural', label: '云扬 中文 男' },
  { name: 'zh-CN-liaoning-XiaobeiNeural', label: '晓北 辽宁 女' },
  { name: 'zh-CN-shaanxi-XiaoniNeural', label: '晓妮 陕西 女' },
  { name: 'zh-TW-HsiaoChenNeural', label: '曉臻 台湾 女' },
  { name: 'zh-TW-HsiaoYuNeural', label: '曉雨 台湾 女' },
  { name: 'zh-TW-YunJheNeural', label: '雲哲 台湾 男' },
  { name: 'zh-HK-HiuGaaiNeural', label: '曉佳 粤语 女' },
  { name: 'zh-HK-HiuMaanNeural', label: '曉曼 粤语 女' },
  { name: 'zh-HK-WanLungNeural', label: '雲龍 粤语 男' },
  { name: 'en-US-JennyNeural', label: 'Jenny 美式英语 女' },
  { name: 'en-US-GuyNeural', label: 'Guy 美式英语 男' },
  { name: 'en-GB-SoniaNeural', label: 'Sonia 英式英语 女' },
  { name: 'en-GB-RyanNeural', label: 'Ryan 英式英语 男' },
  { name: 'ja-JP-NanamiNeural', label: 'Nanami 日语 女' },
  { name: 'ja-JP-KeitaNeural', label: 'Keita 日语 男' },
  { name: 'ko-KR-SunHiNeural', label: 'SunHi 韩语 女' },
  { name: 'ko-KR-InJoonNeural', label: 'InJoon 韩语 男' }
]

const volcVoices = [
  { name: 'zh_female_story', label: '少儿故事 中英混' },
  { name: 'zh_female_qingxin', label: '清新女声 中英混' },
  { name: 'zh_female_zhubo', label: '女主播 中英混' },
  { name: 'zh_male_zhubo', label: '男主播 中英混' },
  { name: 'zh_male_xiaoming', label: '影视男解说 中英混' },
  { name: 'zh_female_sichuan', label: '四川女声 川英混' },
  { name: 'zh_male_rap', label: '嘻哈男歌手 中英混' },
  { name: 'en_female_sarah', label: '澳英女声 澳洲英语' },
  { name: 'jp_male_satoshi', label: '活力男青年 日语' },
  { name: 'jp_female_hana', label: '温柔女声 日语' }
]

// Get voices based on engine
const voices = computed(() => {
  switch (props.engine) {
    case 'azure_tts':
      return azureVoices
    case 'edge_tts':
      return edgeVoices
    case 'volc_tts':
      return volcVoices
    default:
      return []
  }
})

// Filter voices by search query
const filteredVoices = computed(() => {
  if (!searchQuery.value) return voices.value
  const query = searchQuery.value.toLowerCase()
  return voices.value.filter(v => 
    v.name.toLowerCase().includes(query) || 
    v.label.toLowerCase().includes(query)
  )
})

// Get current voice label
const currentVoiceLabel = computed(() => {
  const voice = voices.value.find(v => v.name === props.modelValue)
  return voice ? voice.label : props.modelValue || '请选择语音角色'
})

function selectVoice(voice) {
  emit('update:modelValue', voice.name)
  showDropdown.value = false
  searchQuery.value = ''
}

function handleClickOutside(event) {
  const el = event.target.closest('.tts-voice-select')
  if (!el) {
    showDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="tts-voice-select">
    <div class="select-trigger" @click="showDropdown = !showDropdown">
      <span class="selected-value">{{ currentVoiceLabel }}</span>
      <span class="arrow">▼</span>
    </div>
    
    <div v-if="showDropdown" class="dropdown">
      <div class="search-box">
        <input 
          v-model="searchQuery" 
          type="text" 
          placeholder="搜索语音角色..."
          @click.stop
        />
      </div>
      
      <div class="voice-list">
        <div 
          v-for="voice in filteredVoices" 
          :key="voice.name"
          class="voice-item"
          :class="{ selected: voice.name === modelValue }"
          @click="selectVoice(voice)"
        >
          <span class="voice-label">{{ voice.label }}</span>
          <span class="voice-name">{{ voice.name }}</span>
        </div>
        
        <div v-if="filteredVoices.length === 0" class="no-results">
          没有找到匹配的语音角色
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.tts-voice-select {
  position: relative;
  width: 100%;
  max-width: 400px;
}

.select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  .selected-value {
    color: var(--text-primary);
    font-size: 14px;
  }
  
  .arrow {
    font-size: 10px;
    color: var(--text-secondary);
  }
}

.dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 100;
  max-height: 350px;
  display: flex;
  flex-direction: column;
}

.search-box {
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
  
  input {
    width: 100%;
    padding: 8px 12px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 14px;
    
    &:focus {
      outline: none;
      border-color: var(--accent-color);
    }
    
    &::placeholder {
      color: var(--text-muted);
    }
  }
}

.voice-list {
  overflow-y: auto;
  max-height: 280px;
}

.voice-item {
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  
  &:last-child {
    border-bottom: none;
  }
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  &.selected {
    background-color: rgba(var(--accent-rgb), 0.1);
    
    .voice-label {
      color: var(--accent-color);
    }
  }
  
  .voice-label {
    font-size: 14px;
    color: var(--text-primary);
    margin-bottom: 2px;
  }
  
  .voice-name {
    font-size: 12px;
    color: var(--text-muted);
    font-family: monospace;
  }
}

.no-results {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
