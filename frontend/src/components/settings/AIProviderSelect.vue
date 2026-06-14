<script setup>
/**
 * AI Provider selector component for service configurations
 * Supports filtering by api_type (e.g., 'gemini', 'openai', 'deepseek')
 */
import { computed, onMounted } from 'vue'
import { useAIProvidersStore } from '@/stores/aiProviders'

const props = defineProps({
  modelValue: String,
  placeholder: {
    type: String,
    default: '请选择 AI 服务商'
  },
  allowEmpty: {
    type: Boolean,
    default: true
  },
  // Filter providers by api_type (e.g., 'gemini' to show only Gemini providers)
  filterType: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update:modelValue'])

const store = useAIProvidersStore()

// Load providers if not loaded
onMounted(async () => {
  if (!store.providers.length) {
    await store.fetchProviders()
  }
})

const selectedValue = computed({
  get: () => props.modelValue || '',
  set: (val) => emit('update:modelValue', val || null)
})

// Filter enabled providers by api_type if filterType is specified
const filteredProviders = computed(() => {
  let providers = store.enabledProviders
  if (props.filterType) {
    providers = providers.filter(p => p.api_type === props.filterType)
  }
  return providers
})

// Get selected provider info
const selectedProvider = computed(() => {
  if (!props.modelValue) return null
  return store.getProviderById(props.modelValue)
})

// Generate hint text based on filterType
const filterTypeLabel = computed(() => {
  const labels = {
    'gemini': 'Gemini',
    'openai': 'OpenAI',
    'deepseek': 'DeepSeek',
    'openai_compatible': 'OpenAI 兼容'
  }
  return labels[props.filterType] || props.filterType
})
</script>

<template>
  <div class="ai-provider-select">
    <select v-model="selectedValue">
      <option v-if="allowEmpty" value="">{{ placeholder }}</option>
      <option 
        v-for="provider in filteredProviders" 
        :key="provider.id" 
        :value="provider.id"
      >
        {{ provider.name }} ({{ provider.api_type }})
      </option>
    </select>
    
    <div v-if="!filteredProviders.length" class="no-providers">
      <span v-if="filterType">暂无可用的 {{ filterTypeLabel }} 类型服务商，</span>
      <span v-else>暂无可用的 AI 服务商，</span>
      <router-link to="/settings/ai-providers">前往配置</router-link>
    </div>
    
    <div v-else class="provider-actions">
      <router-link to="/settings/ai-providers" class="config-link">配置 AI 服务商</router-link>
    </div>
    
    <div v-if="selectedProvider" class="provider-info">
      <span class="provider-url">{{ selectedProvider.base_url }}</span>
      <span v-if="selectedProvider.api_key_configured" class="provider-status">✓ 已配置</span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.ai-provider-select {
  select {
    width: 100%;
    max-width: 400px;
    padding: 10px 12px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 14px;
    cursor: pointer;
    
    &:focus {
      outline: none;
      border-color: var(--accent-color);
    }
  }
}

.no-providers {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  
  a {
    color: var(--accent-color);
    text-decoration: none;
    
    &:hover {
      text-decoration: underline;
    }
  }
}

.provider-actions {
  margin-top: 6px;
  
  .config-link {
    font-size: 12px;
    color: var(--accent-color);
    text-decoration: none;
    
    &:hover {
      text-decoration: underline;
    }
  }
}

.provider-info {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 12px;
  
  .provider-url {
    font-family: monospace;
  }
  
  .provider-status {
    color: var(--success);
  }
}
</style>
