<script setup>
/**
 * AI Provider management component
 */
import { ref, onMounted, computed } from 'vue'
import { useAIProvidersStore } from '@/stores/aiProviders'

const store = useAIProvidersStore()

// API type options (hardcoded for reliability)
const apiTypeOptions = [
  { value: 'deepseek', label: 'DeepSeek', default_url: 'https://api.deepseek.com/v1', url_required: false },
  { value: 'openai', label: 'OpenAI', default_url: 'https://api.openai.com/v1', url_required: false },
  { value: 'gemini', label: 'Gemini', default_url: 'https://generativelanguage.googleapis.com/v1beta', url_required: false },
  { value: 'openai_compatible', label: 'OpenAI Compatible', default_url: '', url_required: true }
]

// Modal state
const showModal = ref(false)
const editingProvider = ref(null)
const formData = ref({
  name: '',
  api_type: 'deepseek',
  base_url: '',
  api_key: ''
})
const saving = ref(false)
const testResults = ref({})

// Load data on mount
onMounted(async () => {
  await store.fetchProviders()
})

// Get default URL for API type
function getDefaultUrl(apiType) {
  const type = apiTypeOptions.find(t => t.value === apiType)
  return type?.default_url || ''
}

// Check if URL is required for API type
function isUrlRequired(apiType) {
  const type = apiTypeOptions.find(t => t.value === apiType)
  return type?.url_required || false
}

// Open modal for creating new provider
function openCreateModal() {
  editingProvider.value = null
  formData.value = {
    name: '',
    api_type: 'deepseek',
    base_url: '',
    api_key: ''
  }
  showModal.value = true
}

// Open modal for editing provider
function openEditModal(provider) {
  editingProvider.value = provider
  formData.value = {
    name: provider.name,
    api_type: provider.api_type,
    base_url: provider.base_url === getDefaultUrl(provider.api_type) ? '' : provider.base_url,
    api_key: ''  // Don't pre-fill API key
  }
  showModal.value = true
}

// Close modal
function closeModal() {
  showModal.value = false
  editingProvider.value = null
}

// Handle API type change
function onApiTypeChange() {
  // Clear custom URL when type changes
  formData.value.base_url = ''
}

// Save provider
async function saveProvider() {
  saving.value = true
  try {
    const data = {
      name: formData.value.name,
      api_type: formData.value.api_type,
      base_url: formData.value.base_url || null
    }
    
    if (editingProvider.value) {
      // Update existing
      if (formData.value.api_key) {
        data.api_key = formData.value.api_key
      }
      await store.updateProvider(editingProvider.value.id, data)
    } else {
      // Create new
      data.api_key = formData.value.api_key
      await store.createProvider(data)
    }
    
    closeModal()
  } catch (err) {
    alert(err.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// Delete provider
async function deleteProvider(provider) {
  if (!confirm(`确定要删除 "${provider.name}" 吗？`)) return
  
  try {
    await store.deleteProvider(provider.id)
  } catch (err) {
    alert(err.message || '删除失败')
  }
}

// Toggle provider enabled state
async function toggleEnabled(provider) {
  try {
    await store.updateProvider(provider.id, {
      is_enabled: !provider.is_enabled
    })
  } catch (err) {
    alert(err.message || '更新失败')
  }
}

// Test provider connection
async function testProvider(provider) {
  testResults.value[provider.id] = { loading: true }
  const result = await store.testProvider(provider.id)
  testResults.value[provider.id] = result
  
  // Clear result after 5 seconds
  setTimeout(() => {
    delete testResults.value[provider.id]
  }, 5000)
}

// Get API type label
function getApiTypeLabel(apiType) {
  const type = apiTypeOptions.find(t => t.value === apiType)
  return type?.label || apiType
}
</script>

<template>
  <div class="ai-provider-manager">
    <div class="section-header">
      <h3>AI 服务商</h3>
      <button class="btn btn-primary" @click="openCreateModal">
        + 添加服务商
      </button>
    </div>
    
    <p class="section-desc">
      配置 AI API 服务商，供翻译、素材生成等功能使用
    </p>

    <!-- Provider list -->
    <div v-if="store.loading && !store.providers.length" class="loading">
      加载中...
    </div>
    
    <div v-else-if="!store.providers.length" class="empty-state">
      <p>暂无配置的 AI 服务商</p>
      <p class="hint">点击上方按钮添加第一个服务商</p>
    </div>
    
    <div v-else class="provider-list">
      <div 
        v-for="provider in store.providers" 
        :key="provider.id"
        class="provider-card"
        :class="{ disabled: !provider.is_enabled }"
      >
        <div class="provider-info">
          <div class="provider-name">
            {{ provider.name }}
            <span class="provider-type">{{ getApiTypeLabel(provider.api_type) }}</span>
          </div>
          <div class="provider-url">{{ provider.base_url }}</div>
          <div class="provider-key">
            <span class="key-label">API Key:</span>
            <span class="key-value">{{ provider.api_key_masked || '未配置' }}</span>
            <span v-if="provider.api_key_configured" class="key-status">✓</span>
          </div>
        </div>
        
        <div class="provider-actions">
          <!-- Test result -->
          <div v-if="testResults[provider.id]" class="test-result" :class="{ 
            success: testResults[provider.id].success,
            error: !testResults[provider.id].success && !testResults[provider.id].loading,
            loading: testResults[provider.id].loading
          }">
            <template v-if="testResults[provider.id].loading">测试中...</template>
            <template v-else-if="testResults[provider.id].success">
              ✓ {{ testResults[provider.id].latency_ms }}ms
            </template>
            <template v-else>✗ {{ testResults[provider.id].message }}</template>
          </div>
          
          <button 
            class="btn-icon" 
            title="测试连接"
            @click="testProvider(provider)"
            :disabled="testResults[provider.id]?.loading"
          >
            🔗
          </button>
          <button class="btn-icon" title="编辑" @click="openEditModal(provider)">
            ✏️
          </button>
          <button 
            class="btn-icon" 
            :title="provider.is_enabled ? '禁用' : '启用'"
            @click="toggleEnabled(provider)"
          >
            {{ provider.is_enabled ? '🟢' : '⚪' }}
          </button>
          <button class="btn-icon danger" title="删除" @click="deleteProvider(provider)">
            🗑️
          </button>
        </div>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingProvider ? '编辑服务商' : '添加服务商' }}</h3>
          <button class="btn-close" @click="closeModal">×</button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label>名称 *</label>
            <input 
              v-model="formData.name" 
              type="text" 
              placeholder="如：我的 DeepSeek"
              maxlength="100"
            />
          </div>
          
          <div class="form-group">
            <label>API 类型 *</label>
            <select v-model="formData.api_type" @change="onApiTypeChange">
              <option 
                v-for="type in apiTypeOptions" 
                :key="type.value" 
                :value="type.value"
              >
                {{ type.label }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>
              API 地址
              <span v-if="isUrlRequired(formData.api_type)" class="required">*</span>
            </label>
            <input 
              v-model="formData.base_url" 
              type="text" 
              :placeholder="getDefaultUrl(formData.api_type) || '请输入 API 地址'"
            />
            <p v-if="getDefaultUrl(formData.api_type)" class="field-hint">
              留空使用默认地址：{{ getDefaultUrl(formData.api_type) }}
            </p>
          </div>
          
          <div class="form-group">
            <label>
              API Key
              <span v-if="!editingProvider" class="required">*</span>
            </label>
            <input 
              v-model="formData.api_key" 
              type="password" 
              :placeholder="editingProvider ? '留空保持不变' : '请输入 API Key'"
            />
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeModal" :disabled="saving">
            取消
          </button>
          <button 
            class="btn btn-primary" 
            @click="saveProvider"
            :disabled="saving || !formData.name || (!editingProvider && !formData.api_key)"
          >
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>


<style lang="scss" scoped>
.ai-provider-manager {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  
  h3 {
    margin: 0;
    font-size: 18px;
    color: var(--text-primary);
  }
}

.section-desc {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 20px;
}

.loading, .empty-state {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border-radius: 8px;
  
  .hint {
    font-size: 13px;
    margin-top: 8px;
    opacity: 0.7;
  }
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--accent-color);
  }
  
  &.disabled {
    opacity: 0.6;
  }
}

.provider-info {
  flex: 1;
}

.provider-name {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.provider-type {
  font-size: 12px;
  font-weight: normal;
  color: var(--text-secondary);
  background: var(--bg-hover);
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.provider-url {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  font-family: monospace;
}

.provider-key {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  
  .key-label {
    color: var(--text-secondary);
  }
  
  .key-value {
    font-family: monospace;
    color: var(--text-primary);
  }
  
  .key-status {
    color: var(--success);
  }
}

.provider-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.test-result {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  margin-right: 8px;
  
  &.loading {
    color: var(--text-secondary);
  }
  
  &.success {
    color: var(--success);
    background: rgba(34, 197, 94, 0.1);
  }
  
  &.error {
    color: var(--error);
    background: rgba(239, 68, 68, 0.1);
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.2s;
  
  &:hover {
    background: var(--bg-hover);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  &.danger:hover {
    background: rgba(239, 68, 68, 0.1);
  }
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  &.btn-primary {
    background-color: var(--accent-color);
    color: white;
    
    &:hover:not(:disabled) {
      background-color: var(--accent-hover);
    }
  }
  
  &.btn-secondary {
    background-color: var(--bg-hover);
    color: var(--text-primary);
    
    &:hover:not(:disabled) {
      background-color: var(--border-color);
    }
  }
}

// Modal styles
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--bg-primary);
  border-radius: 12px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
  
  h3 {
    margin: 0;
    font-size: 18px;
  }
  
  .btn-close {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    font-size: 24px;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: 6px;
    
    &:hover {
      background: var(--bg-hover);
    }
  }
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: 20px;
  
  label {
    display: block;
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 8px;
    
    .required {
      color: var(--error);
    }
  }
  
  input, select {
    width: 100%;
    padding: 10px 12px;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 14px;
    
    &:focus {
      outline: none;
      border-color: var(--accent-color);
    }
  }
  
  .field-hint {
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-muted);
  }
}
</style>
