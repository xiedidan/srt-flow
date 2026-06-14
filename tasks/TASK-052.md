---
id: TASK-052
title: 语音合成功能升级
status: Review
assignee: Kiro
priority: High
source: 需求日记
---

# 任务描述
1. 系统配置-语音合成，需要支持多种不同TTS服务各自的配置
2. 语音合成除了支持本地部署的TTS，也支持对应的TTS API调用

# 验收标准 (Acceptance Criteria)
- [x] 后端支持多种TTS服务的独立配置（Coqui TTS、ChatTTS、SparkTTS、IndexTTS、CozyVoice、VITS等）
- [x] 每种TTS服务有各自的配置项（API地址、模型参数等）
- [x] 支持本地部署TTS和云端TTS API两种调用方式
- [x] 前端配置界面支持切换和配置不同的TTS服务
- [x] 语音合成服务能根据配置调用对应的TTS服务

# 上下文 (Context)
- 相关功能：系统配置-语音合成
- 参考 `docs/11-服务-语音合成服务设计.md`
- 参考 `backend/services/tts.py`

# 实现记录

## 修改的文件

### 后端
1. `backend/core/config.py`
   - 扩展 `TTSConfig` 模型，新增各引擎独立配置：
     - 通用设置：`reference_audio`（参考音频路径）
     - ChatTTS：`chattts_temperature`, `chattts_top_p`, `chattts_top_k`
     - IndexTTS：`indextts_mode`（local/api）, `indextts_api_url`
     - SparkTTS：`sparktts_mode`, `sparktts_api_url`
     - CozyVoice：`cozyvoice_mode`, `cozyvoice_api_url`, `cozyvoice_speaker`
     - Coqui TTS：`coqui_model_name`
     - VITS：`vits_model_path`

2. `backend/services/tts.py`
   - 更新 `TTSConfig` dataclass 添加新配置字段
   - 新增 `APIBasedTTSEngine` 基类支持 HTTP API 调用
   - 新增 `IndexTTSAPIEngine`, `SparkTTSAPIEngine`, `CozyVoiceAPIEngine` API 模式引擎
   - 更新 `create_engine` 工厂函数，根据配置选择本地或 API 模式

3. `backend/app/main.py`
   - 更新 TTS 任务预处理逻辑，加载所有新配置字段

### 前端
4. `frontend/src/views/SettingsView.vue`
   - 更新 TTS schema，按引擎分组显示配置项
   - 使用 `showWhen` 条件显示各引擎特定配置
   - 支持本地/API 模式切换

## 配置项说明

| 引擎 | 本地模式 | API 模式 | 特有配置 |
|------|---------|---------|---------|
| ChatTTS | ✓ | - | temperature, top_p, top_k |
| IndexTTS | ✓ | ✓ | api_url |
| SparkTTS | ✓ | ✓ | api_url |
| CozyVoice | ✓ | ✓ | api_url, speaker |
| Coqui TTS | ✓ | - | model_name |
| VITS | ✓ | - | model_path |
