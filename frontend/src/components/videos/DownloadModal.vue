<script setup>
/**
 * Download video modal component
 */
import { ref, watch, computed, onMounted } from 'vue'
import { configApi } from '@/api/config'

const props = defineProps({
  visible: Boolean
})

const emit = defineEmits(['close', 'submit'])

const url = ref('')
const useProxy = ref(true)  // Default to use proxy
const forceH264 = ref(true)  // Default to force H264 for browser compatibility
const submitting = ref(false)
const error = ref('')

// Tags state
const customTags = ref([])  // User-defined tags
const tagInput = ref('')    // Current tag input

// Config state
const downloadConfig = ref(null)
const globalConfig = ref(null)
const cookieTestLoading = ref(false)
const cookieTestResult = ref(null)

// Load configs and auto-test cookies
async function loadConfigs() {
  try {
    const [downloadRes, globalRes] = await Promise.all([
      configApi.get('download'),
      configApi.get('global')
    ])
    downloadConfig.value = downloadRes.data
    globalConfig.value = globalRes.data
    // Default useProxy based on whether proxy is configured
    useProxy.value = !!globalConfig.value?.proxy_url
    
    // Auto-test cookies if browser is configured
    if (downloadConfig.value?.cookies_browser && downloadConfig.value.cookies_browser !== 'none') {
      testCookies()
    }
  } catch (e) {
    console.error('Failed to load config:', e)
  }
}

// Test cookie extraction
async function testCookies() {
  const browser = downloadConfig.value?.cookies_browser
  if (!browser || browser === 'none') {
    cookieTestResult.value = {
      success: false,
      message: '未配置 Cookie 来源浏览器，请在设置中配置'
    }
    return
  }
  
  cookieTestLoading.value = true
  cookieTestResult.value = null
  
  try {
    const res = await configApi.testCookies(browser)
    // Response interceptor returns { data, message }, so use res.data directly
    cookieTestResult.value = res.data
  } catch (err) {
    cookieTestResult.value = {
      success: false,
      message: err.message || '测试失败'
    }
  } finally {
    cookieTestLoading.value = false
  }
}

// Reset form when modal closes
watch(() => props.visible, (visible) => {
  if (!visible) {
    url.value = ''
    error.value = ''
    submitting.value = false
    cookieTestResult.value = null
    customTags.value = []
    tagInput.value = ''
    forceH264.value = true
  } else {
    // Load configs when modal opens
    loadConfigs()
  }
})

// Tag management functions
function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !customTags.value.includes(tag)) {
    customTags.value.push(tag)
    tagInput.value = ''
  }
}

function removeTag(tag) {
  customTags.value = customTags.value.filter(t => t !== tag)
}

function handleTagInputKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    addTag()
  }
}

// Validate URL
function isValidUrl(str) {
  try {
    const u = new URL(str)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

// Detect source from URL
function detectSource(urlStr) {
  if (urlStr.includes('youtube.com') || urlStr.includes('youtu.be')) {
    return 'youtube'
  }
  if (urlStr.includes('bilibili.com') || urlStr.includes('b23.tv')) {
    return 'bilibili'
  }
  return 'unknown'
}

async function handleSubmit() {
  error.value = ''
  
  if (!url.value.trim()) {
    error.value = '请输入视频 URL'
    return
  }
  
  if (!isValidUrl(url.value)) {
    error.value = '请输入有效的 URL'
    return
  }
  
  const source = detectSource(url.value)
  if (source === 'unknown') {
    error.value = '暂不支持该平台，目前支持 YouTube 和 Bilibili'
    return
  }
  
  submitting.value = true
  try {
    emit('submit', {
      type: 'download',
      payload: { 
        url: url.value.trim(),
        use_proxy: useProxy.value,
        force_h264: forceH264.value,
        tags: customTags.value
      }
    })
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>📥 下载视频</h3>
          <button class="close-btn" @click="handleClose">✕</button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label>视频 URL</label>
            <input
              v-model="url"
              type="text"
              class="form-input"
              placeholder="https://www.youtube.com/watch?v=... 或 https://www.bilibili.com/video/..."
              @keyup.enter="handleSubmit"
            />
            <p v-if="error" class="error-text">{{ error }}</p>
          </div>
          
          <div class="supported-platforms">
            <p>支持的平台：</p>
            <div class="platforms">
              <span class="platform">📺 YouTube</span>
              <span class="platform">📱 Bilibili</span>
            </div>
          </div>
          
          <!-- Tags input -->
          <div class="form-group tags-section">
            <label>标签</label>
            <p class="tags-hint">下载完成后会自动添加来源平台和频道名作为标签</p>
            <div class="tags-input-wrapper">
              <input
                v-model="tagInput"
                type="text"
                class="form-input tag-input"
                placeholder="输入标签后按回车添加..."
                @keydown="handleTagInputKeydown"
              />
              <button type="button" class="btn-add-tag" @click="addTag" :disabled="!tagInput.trim()">添加</button>
            </div>
            <div v-if="customTags.length > 0" class="tags-list">
              <span v-for="tag in customTags" :key="tag" class="tag-item">
                {{ tag }}
                <button type="button" class="tag-remove" @click="removeTag(tag)">×</button>
              </span>
            </div>
          </div>
          
          <!-- Proxy option -->
          <div class="proxy-section">
            <label class="checkbox-label">
              <input type="checkbox" v-model="useProxy" :disabled="!globalConfig?.proxy_url" />
              <span>使用代理下载</span>
            </label>
            <span v-if="globalConfig?.proxy_url" class="proxy-info">
              ({{ globalConfig.proxy_url }})
            </span>
            <span v-else class="proxy-warning">
              未配置代理，请在通用设置中配置
            </span>
          </div>
          
          <!-- H264 codec option -->
          <div class="codec-section">
            <label class="checkbox-label">
              <input type="checkbox" v-model="forceH264" />
              <span>强制 H264 编码</span>
            </label>
            <span class="codec-hint">
              推荐开启，确保浏览器可以预览视频（HEVC 编码不支持预览）
            </span>
          </div>
          
          <!-- Cookie test section -->
          <div class="cookie-section">
            <div class="cookie-header">
              <span class="cookie-label">
                🍪 Cookie 来源：
                <strong>{{ downloadConfig?.cookies_browser === 'none' ? '未配置' : downloadConfig?.cookies_browser?.toUpperCase() || '加载中...' }}</strong>
              </span>
              <button 
                type="button" 
                class="btn-test-cookie"
                @click="testCookies"
                :disabled="cookieTestLoading || !downloadConfig?.cookies_browser || downloadConfig?.cookies_browser === 'none'"
              >
                {{ cookieTestLoading ? '测试中...' : '测试 Cookie' }}
              </button>
            </div>
            <div v-if="cookieTestResult" class="cookie-result" :class="{ success: cookieTestResult.success, error: !cookieTestResult.success }">
              <span class="result-icon">{{ cookieTestResult.success ? '✓' : '✗' }}</span>
              <span class="result-text">{{ cookieTestResult.message }}</span>
            </div>
            <p class="cookie-hint">YouTube 下载可能需要登录验证，请在设置中配置 Cookie 来源浏览器</p>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleClose">取消</button>
          <button 
            class="btn btn-primary" 
            :disabled="!url.trim() || submitting"
            @click="handleSubmit"
          >
            {{ submitting ? '提交中...' : '开始下载' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style lang="scss" scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background-color: var(--bg-secondary);
  border-radius: 12px;
  width: 90%;
  max-width: 480px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  
  h3 {
    margin: 0;
    font-size: 18px;
    color: var(--text-primary);
  }
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  
  &:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 20px;
  
  label {
    display: block;
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }
}

.form-input {
  width: 100%;
  padding: 12px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
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

.error-text {
  margin-top: 8px;
  font-size: 13px;
  color: var(--error);
}

.supported-platforms {
  p {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }
}

.platforms {
  display: flex;
  gap: 12px;
}

.platform {
  padding: 8px 16px;
  background-color: var(--bg-primary);
  border-radius: 6px;
  font-size: 14px;
  color: var(--text-secondary);
}

.tags-section {
  margin-top: 16px;
  
  .tags-hint {
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }
  
  .tags-input-wrapper {
    display: flex;
    gap: 8px;
    
    .tag-input {
      flex: 1;
    }
    
    .btn-add-tag {
      padding: 8px 16px;
      background-color: var(--bg-hover);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      color: var(--text-primary);
      font-size: 14px;
      cursor: pointer;
      white-space: nowrap;
      
      &:hover:not(:disabled) {
        background-color: var(--border-color);
      }
      
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
  
  .tags-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }
  
  .tag-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background-color: var(--accent-color);
    color: white;
    border-radius: 16px;
    font-size: 13px;
    
    .tag-remove {
      background: none;
      border: none;
      color: white;
      font-size: 16px;
      cursor: pointer;
      padding: 0;
      line-height: 1;
      opacity: 0.8;
      
      &:hover {
        opacity: 1;
      }
    }
  }
}

.proxy-section {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      accent-color: var(--accent-color);
      
      &:disabled {
        cursor: not-allowed;
      }
    }
    
    span {
      font-size: 14px;
      color: var(--text-primary);
    }
  }
  
  .proxy-info {
    font-size: 12px;
    color: var(--text-muted);
    font-family: monospace;
  }
  
  .proxy-warning {
    font-size: 12px;
    color: var(--warning, #f59e0b);
  }
}

.codec-section {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      accent-color: var(--accent-color);
    }
    
    span {
      font-size: 14px;
      color: var(--text-primary);
    }
  }
  
  .codec-hint {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.cookie-section {
  margin-top: 16px;
  padding: 12px;
  background-color: var(--bg-primary);
  border-radius: 8px;
  
  .cookie-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  
  .cookie-label {
    font-size: 13px;
    color: var(--text-secondary);
    
    strong {
      color: var(--text-primary);
    }
  }
  
  .btn-test-cookie {
    padding: 6px 12px;
    background-color: var(--bg-hover);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    
    &:hover:not(:disabled) {
      background-color: var(--border-color);
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
  
  .cookie-result {
    margin-top: 8px;
    padding: 8px 10px;
    border-radius: 4px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    
    &.success {
      background-color: rgba(34, 197, 94, 0.1);
      color: var(--success);
    }
    
    &.error {
      background-color: rgba(239, 68, 68, 0.1);
      color: var(--error);
    }
    
    .result-icon {
      font-weight: bold;
    }
  }
  
  .cookie-hint {
    margin-top: 8px;
    font-size: 11px;
    color: var(--text-muted);
  }
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
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
    
    &:hover {
      background-color: var(--border-color);
    }
  }
}
</style>
