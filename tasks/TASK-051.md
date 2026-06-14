---
id: TASK-051
title: 语音识别Gemini接口纳入AI服务商体系
status: Review
assignee: Kiro
priority: High
source: 需求日记
---

# 任务描述
系统配置-语音识别如果选用Gemini，就从AI服务商配置中选取已配置的Gemini服务商。也允许用户在选用Gemini的时候，跳转到AI服务商配置。

# 验收标准 (Acceptance Criteria)
- [x] 语音识别选择Gemini时，显示已配置的Gemini服务商列表
- [x] 用户可以从下拉列表中选择要使用的Gemini服务商
- [x] 提供"配置AI服务商"的快捷跳转链接
- [x] 语音识别服务使用选中的AI服务商配置进行调用

# 上下文 (Context)
- 相关功能：系统配置-语音识别、AI服务商配置
- 参考 `docs/15-AI配置重构设计.md`
- 参考 `docs/09-服务-语音识别服务设计.md`

# 实现记录

## 修改的文件

### 前端
1. `frontend/src/components/settings/AIProviderSelect.vue`
   - 添加 `filterType` prop 支持按 api_type 过滤服务商
   - 添加"配置 AI 服务商"跳转链接
   - 当没有匹配类型的服务商时显示提示

2. `frontend/src/components/settings/ConfigForm.vue`
   - 传递 `filterType` prop 给 AIProviderSelect 组件

3. `frontend/src/views/SettingsView.vue`
   - 为 `gemini_provider_id` 字段添加 `filterType: 'gemini'` 配置

### 后端
4. `backend/app/main.py`
   - ASR 任务预处理逻辑支持从 AI Provider 获取 API Key
   - 优先使用 `gemini_provider_id` 关联的 AI Provider
   - 如果 AI Provider 有配置 base_url，则使用该地址
   - 保留 legacy `gemini_api_key` 作为后备方案
