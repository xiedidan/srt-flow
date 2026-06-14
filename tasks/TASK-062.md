---
id: TASK-062
title: TTS在线服务集成
status: Review
assignee: Kiro
priority: High
---

# 任务描述
将 Azure TTS、Edge TTS 和火山 TTS 三个在线服务集成进系统的语音合成功能。

# 验收标准 (Acceptance Criteria)
- [x] 集成 Azure TTS 服务
- [x] 集成 Edge TTS 服务
- [x] 集成火山 TTS 服务
- [x] 支持各服务的语音角色选择
- [x] 在系统配置中添加相应的配置项
- [x] 语音合成任务支持选择在线服务

# 上下文 (Context)
- 来源：需求日记
- 参考代码：`reference/tts/` 目录下的示例代码和语音角色定义
- 相关文档：`docs/11-服务-语音合成服务设计.md`

# 实现说明

## 后端修改

### backend/services/tts.py
- 添加 `TTSEngine` 枚举：`AZURE_TTS`、`EDGE_TTS`、`VOLC_TTS`
- 添加 `TTSConfig` 配置字段：
  - Azure TTS: `azure_tts_voice`, `azure_tts_style`, `azure_tts_rate`, `azure_tts_pitch`
  - Edge TTS: `edge_tts_voice`, `edge_tts_rate`, `edge_tts_pitch`
  - Volc TTS: `volc_tts_voice`
- 实现三个在线TTS引擎类：
  - `AzureTTSEngine`: 使用微软翻译器TTS端点，支持情感风格
  - `EdgeTTSEngine`: 使用 edge-tts 库，稳定免费
  - `VolcTTSEngine`: 使用火山翻译TTS API，中文效果好
- 更新 `create_engine()` 工厂函数支持新引擎

### backend/core/config.py
- 添加 `TTSEngine` 枚举值
- 添加 `TTSConfig` 配置字段

## 前端修改

### frontend/src/views/SettingsView.vue
- TTS引擎选项添加三个在线服务
- 添加各服务的配置字段 schema（语音角色、语速、音调等）
- 使用 `showWhen` 条件显示

### frontend/src/components/settings/TTSVoiceSelect.vue (新增)
- TTS语音角色选择组件
- 支持搜索过滤
- 根据引擎类型显示不同的语音列表

### frontend/src/components/settings/ConfigForm.vue
- 注册 TTSVoiceSelect 组件
- 添加 `tts-voice-select` 组件渲染逻辑

## 依赖更新

### requirements.txt
- 添加 `edge-tts>=6.1.0`

## 文档更新

### docs/11-服务-语音合成服务设计.md
- 添加在线服务引擎列表
- 添加在线服务配置项说明
