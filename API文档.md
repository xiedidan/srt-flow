# SRT Flow API 文档

## 1. 概述

本 API 基于 RESTful 风格设计，所有接口前缀为 `/api/v1`。
后端使用 FastAPI 开发，自动生成 OpenAPI (Swagger) 文档，地址通常为 `/docs`。

### 通用响应格式

```json
{
  "code": 0,          // 0: 成功, 非0: 错误码
  "message": "success", // 提示信息
  "data": { ... }     // 业务数据
}
```

## 2. 任务管理 (Tasks)

任务是系统的核心，所有的耗时操作（下载、ASR、TTS等）都封装为任务。

### 2.1 提交任务
**POST** `/tasks`

提交一个新的处理任务。

**Request Body:**
```json
{
  "type": "download", // 任务类型: download, asr, translate, tts, synthesize, asset_gen
  "payload": {
    // 根据 type 不同而不同
    // download: { "url": "...", "use_proxy": true, "tags": ["tag1", "tag2"] }
    // asr: { "video_id": "...", "model": "large-v3" }
    // translate: { "video_id": "...", "source_language": "auto", "target_language": "zh-CN", "task_context": "..." }
    // ...
  },
  "group_id": "optional_group_id" // 可选，用于批量任务分组
}
```

**Download Payload 说明:**
- `url`: (必填) 视频 URL
- `use_proxy`: (可选) 是否使用代理，默认 true
- `tags`: (可选) 用户自定义标签数组，下载完成后会自动添加来源平台和频道名作为标签

**Translate Payload 说明:**
- `video_id`: (必填) 视频 UUID
- `source_language`: (可选) 源语言，默认 auto
- `target_language`: (可选) 目标语言，默认 zh-CN
- `task_context`: (可选) 任务背景信息，会添加到翻译提示词中帮助 AI 理解上下文
- `context_overlap_lines`: (可选) 批次上下文行数（0-10），每个批次前后包含的上下文行数，默认使用配置值

### 2.2 获取任务列表
**GET** `/tasks`

**Query Params:**
- `status`: (optional) pending, running, completed, failed
- `type`: (optional) download, asr, ...
- `video_id`: (optional) 关联的视频 ID
- `page`: 1
- `page_size`: 20

### 2.3 获取任务详情
**GET** `/tasks/{task_id}`

返回任务的详细状态、进度、日志摘要。

**Response Data:**
```json
{
  "id": "uuid",
  "type": "download",
  "status": "running",
  "progress": 45, // 0-100
  "created_at": "2023-10-27T10:00:00",
  "started_at": "2023-10-27T10:00:05",
  "error": null,
  "result": { ... } // 任务完成后的结果数据
}
```

### 2.4 任务操作 (重试/取消)
**POST** `/tasks/{task_id}/action`

**Request Body:**
```json
{
  "action": "retry" // retry, cancel
  "priority": "high" // (optional for retry) high (插队), normal (排队)
}
```

## 3. 视频管理 (Videos)

### 3.1 获取视频列表
**GET** `/videos`

**Query Params:**
- `tag`: (optional) 筛选标签
- `keyword`: (optional) 搜索标题
- `sort`: created_at_desc
- `include_downloading`: (optional) 是否包含下载中的视频，默认 true

**Response Data:**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Video Title",
      "source": "youtube",
      "duration": 360,
      "tags": ["YouTube", "ChannelName", "custom_tag"],
      "is_downloading": false,
      "files": { ... }
    },
    {
      "id": "task_uuid",
      "task_id": "uuid",
      "title": "视频标题",
      "thumbnail_url": "https://i.ytimg.com/vi/.../maxresdefault.jpg",
      "source": "youtube",
      "duration": 360,
      "channel_name": "频道名称",
      "tags": ["custom_tag"],
      "is_downloading": true,
      "download_status": "running",
      "download_progress": 45
    }
  ],
  "total": 10,
  "page": 1,
  "page_size": 20
}
```

**说明:**
- 当 `include_downloading=true` 时，会在第一页返回正在下载的任务作为"下载中"的视频
- 下载中的视频 `id` 以 `task_` 前缀标识，`is_downloading=true`
- 下载任务开始后会优先获取视频元数据（标题、封面、时长、频道名），通过 `title`、`thumbnail_url`、`duration`、`channel_name` 字段返回
- 如果元数据获取失败，`title` 会显示截断的 URL
- 下载完成后会自动添加来源平台（YouTube/Bilibili）和频道名作为标签

### 3.2 获取视频详情
**GET** `/videos/{video_id}`

返回视频的元数据、文件路径列表、关联的任务历史。

**Response Data:**
```json
{
  "id": "uuid",
  "title": "Video Title",
  "source": "youtube",
  "duration": 360,
  "tags": ["tech", "tutorial"],
  "files": {
    "video": "/data/downloads/.../video.mp4",
    "subtitle_original": "/data/downloads/.../subtitle_original.srt",
    "subtitle_translated": "/data/downloads/.../subtitle_translated.srt"
  }
}
```

### 3.3 更新视频信息
**PATCH** `/videos/{video_id}`

用于修改视频标题、标签、分组等。

**Request Body:**
```json
{
  "title": "New Title",
  "tags": ["new_tag"],
  "group_id": "new_group"
}
```

### 3.4 预览文件内容
**GET** `/videos/{video_id}/files/{file_type}/content`

读取文本文件内容（如字幕、日志、摘要）。
`file_type`: `subtitle_original`, `subtitle_translated`, `summary`, `log`

### 3.5 保存文件内容
**PUT** `/videos/{video_id}/files/{file_type}/content`

用于前端编辑器保存修改后的字幕或摘要。

### 3.6 视频预览
**GET** `/videos/{video_id}/preview`

获取视频文件用于预览播放。返回视频文件（FileResponse）。

### 3.7 视频流式播放
**GET** `/videos/{video_id}/stream`

流式播放视频文件，支持 Range 请求（用于视频拖动进度条）。
优先返回合成后的视频（video_output.mp4），如不存在则返回原始视频（video.mp4）。

**Response:** 视频文件流（video/mp4）

### 3.8 获取视频缩略图
**GET** `/videos/{video_id}/thumbnail`

获取视频的缩略图图片。按以下顺序搜索缩略图文件：
1. `assets/thumbnail.jpg` / `assets/thumbnail.png`
2. `thumbnail.jpg` / `thumbnail.png`
3. `video.jpg` / `video.png` / `video.webp`（yt-dlp 下载的缩略图）

**Response:** 图片文件（image/jpeg 或 image/png 或 image/webp）

**Error Response:**
- 404: 视频不存在或缩略图文件不存在

### 3.9 TTS 音频流
**GET** `/videos/{video_id}/audio/tts`

流式播放 TTS 合成的音频文件。按以下顺序搜索音频文件：
1. `audio_tts.m4a`
2. `audio_tts.mp3`
3. `audio_tts.wav`

**Response:** 音频文件流（audio/mp4、audio/mpeg 或 audio/wav）

**Error Response:**
- 404: 视频不存在或 TTS 音频文件不存在

## 4. 系统配置 (Config)

配置按类别管理，支持以下类别：
- `global`: 全局配置（默认语言、日志级别等）
- `download`: 下载服务配置
- `asr`: 语音识别配置
- `translate`: 翻译服务配置
- `tts`: 语音合成配置
- `synthesis`: 视频合成配置
- `asset`: 素材生成配置

### 4.1 获取配置类别列表
**GET** `/config`

返回所有可用的配置类别。

**Response Data:**
```json
{
  "categories": [
    {"name": "global", "description": "...", "has_secrets": false},
    {"name": "translate", "description": "...", "has_secrets": true}
  ]
}
```

### 4.2 获取指定类别配置
**GET** `/config/{category}`

获取指定类别的配置（敏感字段已脱敏）。

**Response Data:**
```json
{
  "provider": "deepseek",
  "model_name": "deepseek-reasoner",
  "batch_size": 30,
  "api_key_masked": "sk-a***",
  "api_key_configured": true
}
```

### 4.3 更新配置
**PUT** `/config/{category}`

更新指定类别的配置（部分更新）。

**Request Body:**
```json
{
  "updates": {
    "batch_size": 50,
    "temperature": 0.8
  }
}
```

### 4.4 设置敏感配置
**PUT** `/config/{category}/secrets/{key_name}`

设置敏感配置（如 API Key），值会被加密存储。

**Request Body:**
```json
{
  "value": "sk-your-api-key-here"
}
```

### 4.5 删除敏感配置
**DELETE** `/config/{category}/secrets/{key_name}`

删除指定的敏感配置。

### 4.6 验证配置
**POST** `/config/{category}/validate`

验证配置是否有效（不保存）。

**Request Body:**
```json
{
  "updates": {
    "batch_size": 200
  }
}
```

**Response Data:**
```json
{
  "valid": false,
  "errors": "batch_size: ensure this value is less than or equal to 100"
}
```

### 4.7 重置配置
**POST** `/config/{category}/reset`

将指定类别的配置重置为默认值（不影响敏感配置）。

### 4.8 导出所有配置
**GET** `/config/export/all`

导出所有配置（敏感信息脱敏）。

**Query Params:**
- `include_secrets`: (optional) 是否包含脱敏的敏感字段标识

### 4.9 测试 Cookie 获取
**POST** `/config/download/test-cookies`

测试从指定浏览器获取 Cookie 是否成功。用于验证下载配置中的 Cookie 来源浏览器设置。

**Request Body:**
```json
{
  "browser": "edge"  // chrome, firefox, edge, safari, opera, brave
}
```

**Response Data (成功):**
```json
{
  "success": true,
  "browser": "edge",
  "message": "成功从 Edge 获取 Cookie",
  "yt_dlp_version": "2024.12.13"
}
```

**Response Data (失败):**
```json
{
  "success": false,
  "browser": "edge",
  "message": "无法复制 Edge 的 Cookie 数据库，请确保浏览器已关闭",
  "error_detail": "ERROR: Could not copy Edge cookie database..."
}
```

## 5. ASR 模型管理 (ASR)

管理 Whisper 语音识别模型的下载和状态。

> 注意：模型文件在所有 Whisper 引擎（Whisper 本地、Faster Whisper XXL 本地）之间共享。

### 5.1 获取模型列表
**GET** `/asr/models`

获取所有可用模型及其下载状态。

**Response Data:**
```json
{
  "models": [
    {
      "model_size": "large-v3",
      "downloaded": true,
      "size_mb": 3000.5,
      "total_size_mb": 3000,
      "download_status": "idle",
      "download_progress": 0,
      "downloaded_mb": 0,
      "total_mb": 3000
    }
  ]
}
```

### 5.2 获取单个模型状态
**GET** `/asr/models/{model_size}`

获取指定模型的详细状态。

**Path Params:**
- `model_size`: 模型大小，可选值：`tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3`

**Response Data:**
```json
{
  "model_size": "large-v3",
  "downloaded": false,
  "size_mb": 0,
  "total_size_mb": 3000,
  "download_status": "downloading",
  "download_progress": 45,
  "downloaded_mb": 1350.5,
  "total_mb": 3000,
  "download_error": ""
}
```

### 5.3 下载模型
**POST** `/asr/models/download`

启动模型下载任务（后台执行，立即返回）。模型跨平台共享。

**Request Body:**
```json
{
  "model_size": "large-v3"
}
```

**Response Data:**
```json
{
  "model_size": "large-v3",
  "status": "started",
  "already_downloaded": false,
  "total_mb": 3000
}
```

**下载状态说明:**
- `idle`: 未下载或下载完成
- `downloading`: 下载中
- `completed`: 下载完成
- `failed`: 下载失败

### 5.4 删除模型
**DELETE** `/asr/models/{model_size}`

删除已下载的模型文件。

**Path Params:**
- `model_size`: 模型大小，可选值：`tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3`

**Response Data:**
```json
{
  "model_size": "large-v3",
  "deleted_size_mb": 3000.5
}
```

**错误情况:**
- 400: 模型正在下载中，无法删除
- 404: 模型未下载

### 5.5 获取支持的引擎列表
**GET** `/asr/engines`

获取支持的引擎和平台列表。

**Response Data:**
```json
{
  "engines": ["whisper_local", "faster_whisper_xxl"],
  "platforms": ["windows", "linux", "macos"]
}
```

### 5.6 获取引擎下载状态
**GET** `/asr/engines/{engine}`

获取指定引擎在所有平台的下载状态。

**Path Params:**
- `engine`: 引擎类型，可选值：`whisper_local`、`faster_whisper_xxl`

**Response Data:**
```json
{
  "engine": "whisper_local",
  "platforms": [
    {
      "engine": "whisper_local",
      "platform": "windows",
      "downloaded": true,
      "size_mb": 150.5,
      "download_status": "idle",
      "download_progress": 0,
      "downloaded_mb": 0,
      "total_mb": 0,
      "download_error": ""
    }
  ]
}
```

### 5.7 获取单个平台引擎状态
**GET** `/asr/engines/{engine}/{platform}`

获取指定引擎在指定平台的下载状态。

**Path Params:**
- `engine`: 引擎类型
- `platform`: 平台，可选值：`windows`、`linux`、`macos`

**Response Data:**
```json
{
  "engine": "whisper_local",
  "platform": "windows",
  "downloaded": true,
  "size_mb": 150.5,
  "download_status": "idle",
  "download_progress": 0,
  "downloaded_mb": 0,
  "total_mb": 0,
  "download_error": ""
}
```

### 5.8 下载引擎可执行文件
**POST** `/asr/engines/download`

启动引擎可执行文件下载任务。

**Request Body:**
```json
{
  "engine": "whisper_local",
  "platform": "windows"
}
```

**Response Data:**
```json
{
  "engine": "whisper_local",
  "platform": "windows",
  "status": "started",
  "already_downloaded": false
}
```

### 5.9 删除引擎可执行文件
**DELETE** `/asr/engines/{engine}/{platform}`

删除指定平台的引擎可执行文件。

**Path Params:**
- `engine`: 引擎类型
- `platform`: 平台

**Response Data:**
```json
{
  "engine": "whisper_local",
  "platform": "windows",
  "deleted_size_mb": 150.5
}
```

**错误情况:**
- 400: 正在下载中，无法删除
- 404: 该平台的引擎未下载

## 6. AI 服务商管理 (AI Providers)

管理 AI API 服务商配置，供翻译、素材生成等功能使用。

### 安全机制

API Key 采用双重加密保护：
1. **传输加密**：前端使用 RSA 公钥加密 API Key 后传输
2. **存储加密**：后端使用 AES-256-GCM 加密存储
3. **脱敏显示**：前端只能获取混淆串（前4字符+****+后4字符）

### 6.1 获取 RSA 公钥
**GET** `/ai-providers/public-key`

获取用于加密 API Key 的 RSA 公钥。前端在创建或更新服务商时，需先获取公钥，使用 RSA-OAEP (SHA-256) 加密 API Key。

**Response Data:**
```json
{
  "data": {
    "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkq...\n-----END PUBLIC KEY-----"
  }
}
```

### 6.2 获取服务商列表
**GET** `/ai-providers`

获取所有已配置的 AI 服务商（API Key 已脱敏）。

**Response Data:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "我的 DeepSeek",
      "api_type": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key_masked": "sk-a****key1",
      "api_key_configured": true,
      "is_enabled": true,
      "created_at": "2024-12-26T10:00:00Z",
      "updated_at": "2024-12-26T10:00:00Z"
    }
  ]
}
```

### 6.3 获取服务商类型选项
**GET** `/ai-providers/types/options`

获取支持的 API 类型及其默认 URL。

**Response Data:**
```json
{
  "data": [
    {
      "value": "deepseek",
      "label": "Deepseek",
      "default_url": "https://api.deepseek.com/v1",
      "url_required": false
    },
    {
      "value": "openai",
      "label": "Openai",
      "default_url": "https://api.openai.com/v1",
      "url_required": false
    },
    {
      "value": "gemini",
      "label": "Gemini",
      "default_url": "https://generativelanguage.googleapis.com/v1beta",
      "url_required": false
    },
    {
      "value": "openai_compatible",
      "label": "Openai Compatible",
      "default_url": "",
      "url_required": true
    }
  ]
}
```

### 6.4 创建服务商
**POST** `/ai-providers`

创建新的 AI 服务商配置。

**Request Body:**
```json
{
  "name": "我的 DeepSeek",
  "api_type": "deepseek",
  "base_url": null,
  "api_key_encrypted": "base64_encoded_rsa_encrypted_api_key"
}
```

**字段说明:**
- `name`: (必填) 自定义名称，最长 100 字符
- `api_type`: (必填) API 类型：deepseek, openai, gemini, openai_compatible
- `base_url`: (可选) 自定义 API 地址，留空使用默认地址；openai_compatible 类型必填
- `api_key_encrypted`: (必填) RSA 加密后的 API Key（Base64 编码）

**前端加密流程:**
1. 调用 `/ai-providers/public-key` 获取公钥
2. 使用 Web Crypto API 的 RSA-OAEP (SHA-256) 加密 API Key
3. 将加密结果 Base64 编码后作为 `api_key_encrypted` 发送

### 6.5 获取单个服务商
**GET** `/ai-providers/{provider_id}`

获取指定服务商的详细信息。

### 6.6 更新服务商
**PUT** `/ai-providers/{provider_id}`

更新服务商配置（部分更新）。

**Request Body:**
```json
{
  "name": "新名称",
  "api_type": "openai",
  "base_url": "https://custom.api.com/v1",
  "api_key_encrypted": "base64_encoded_rsa_encrypted_api_key",
  "is_enabled": true
}
```

**字段说明:**
- 所有字段均为可选，只更新提供的字段
- `api_key_encrypted` 留空则保持原值不变

### 6.7 删除服务商
**DELETE** `/ai-providers/{provider_id}`

删除指定的服务商配置。

### 6.8 测试服务商连接
**POST** `/ai-providers/{provider_id}/test`

测试服务商 API 连接是否正常。

**Response Data:**
```json
{
  "data": {
    "success": true,
    "message": "Connection successful",
    "latency_ms": 150
  }
}
```

**失败响应:**
```json
{
  "data": {
    "success": false,
    "message": "API returned 401: Invalid API key",
    "latency_ms": 200
  }
}
```

## 7. WebSocket (Real-time)

**WS** `/ws/status`

用于前端实时接收任务进度更新，避免高频轮询。
后端在任务状态或进度变化时推送 JSON 消息。

### 消息类型

#### 7.1 task_progress - 任务进度更新
```json
{
  "type": "task_progress",
  "data": {
    "task_id": "uuid",
    "progress": 45,
    "message": "下载中..."
  }
}
```

#### 7.2 task_update - 任务状态更新
```json
{
  "type": "task_update",
  "data": {
    "task_id": "uuid",
    "task_type": "download",
    "status": "completed",
    "video_id": "uuid",
    "error": null,
    "result": { ... }
  }
}
```

#### 7.3 task_metadata - 任务元数据更新
用于下载任务在获取视频元数据后通知前端更新显示。

```json
{
  "type": "task_metadata",
  "data": {
    "task_id": "uuid",
    "metadata": {
      "title": "视频标题",
      "thumbnail_url": "https://i.ytimg.com/vi/.../maxresdefault.jpg",
      "duration": 360,
      "channel_name": "频道名称"
    }
  }
}
```

#### 7.4 notification - 系统通知
```json
{
  "type": "notification",
  "data": {
    "level": "info",
    "title": "通知标题",
    "message": "通知内容",
    "extra": { ... }
  }
}
```

## 8. 统计信息 (Stats)

### 8.1 获取仪表盘统计
**GET** `/stats`

获取仪表盘统计数据。

**Response Data:**
```json
{
  "totalVideos": 10,
  "runningTasks": 2,
  "completedToday": 5
}
```

**字段说明:**
- `totalVideos`: 已下载视频总数
- `runningTasks`: 当前运行中的任务数
- `completedToday`: 今日完成的任务数


## 9. 参考音频管理 (Reference Audio)

管理 TTS 语音克隆的参考音频文件。

### 9.1 获取参考音频列表
**GET** `/reference-audio`

获取所有参考音频文件列表。

**Response Data:**
```json
{
  "data": [
    {
      "id": "uuid",
      "filename": "uuid.wav",
      "original_filename": "my_voice.wav",
      "description": "男声，温和",
      "file_size": 1024000,
      "duration": 15.5,
      "sample_rate": 44100,
      "created_at": "2024-12-29T10:00:00Z",
      "updated_at": "2024-12-29T10:00:00Z"
    }
  ]
}
```

### 9.2 上传参考音频
**POST** `/reference-audio`

上传新的参考音频文件。

**Request:** `multipart/form-data`
- `file`: (必填) 音频文件，支持 wav, mp3, m4a, flac, ogg, aac 格式，最大 50MB
- `description`: (可选) 音频描述

**Response Data:**
```json
{
  "data": {
    "id": "uuid",
    "filename": "uuid.wav",
    "original_filename": "my_voice.wav",
    "description": "男声，温和",
    "file_size": 1024000,
    "duration": 15.5,
    "sample_rate": 44100,
    "created_at": "2024-12-29T10:00:00Z",
    "updated_at": "2024-12-29T10:00:00Z"
  },
  "message": "上传成功"
}
```

### 9.3 获取单个参考音频
**GET** `/reference-audio/{audio_id}`

获取指定参考音频的元数据。

### 9.4 更新参考音频
**PUT** `/reference-audio/{audio_id}`

更新参考音频描述。

**Request Body:**
```json
{
  "description": "新的描述"
}
```

### 9.5 删除参考音频
**DELETE** `/reference-audio/{audio_id}`

删除参考音频文件及其元数据。

### 9.6 播放参考音频
**GET** `/reference-audio/{audio_id}/stream`

流式播放参考音频文件。

**Response:** 音频文件流（audio/wav, audio/mpeg 等）


## 10. TTS 语音合成 (TTS)

提供 TTS 相关操作，包括句子合并预览。

### 10.1 句子合并预览
**POST** `/tts/sentence-merge/preview`

预览 AI 句子合并结果，不执行 TTS 合成。用于在创建 TTS 任务前让用户预览和调整合并结果。

**Request Body:**
```json
{
  "video_id": "uuid",
  "subtitle_path": null
}
```

**字段说明:**
- `video_id`: (必填) 视频 UUID
- `subtitle_path`: (可选) 字幕文件路径，留空则自动查找翻译字幕

**Response Data:**
```json
{
  "original_entries": [
    {
      "index": 1,
      "start_time": 0.0,
      "end_time": 2.5,
      "text": "今天天气"
    },
    {
      "index": 2,
      "start_time": 2.5,
      "end_time": 5.0,
      "text": "真的很好"
    }
  ],
  "merged_entries": [
    {
      "merged_text": "今天天气真的很好",
      "original_indices": [0, 1],
      "start_time": 0.0,
      "end_time": 5.0
    }
  ],
  "original_count": 2,
  "merged_count": 1
}
```

**错误情况:**
- 400: 句子合并未启用或未配置 AI 服务商
- 404: 视频或字幕文件不存在
- 500: AI 合并失败

### 10.2 调整合并结果
**POST** `/tts/sentence-merge/adjust`

手动调整合并后的字幕条目，支持合并、拆分、编辑操作。

**Request Body:**
```json
{
  "entries": [
    {
      "merged_text": "今天天气真的很好",
      "original_indices": [0, 1],
      "start_time": 0.0,
      "end_time": 5.0
    }
  ],
  "action": "split",
  "target_index": 0,
  "merge_with_index": null,
  "new_text": null,
  "split_at_char": 4
}
```

**字段说明:**
- `entries`: (必填) 当前合并条目列表
- `action`: (必填) 操作类型：`merge`（合并）、`split`（拆分）、`edit`（编辑）
- `target_index`: (必填) 目标条目索引
- `merge_with_index`: (merge 操作必填) 要合并的相邻条目索引
- `new_text`: (edit 操作必填) 新的文本内容
- `split_at_char`: (split 操作必填) 拆分位置（字符索引）

**Response Data:**
```json
{
  "entries": [
    {
      "merged_text": "今天天气",
      "original_indices": [0],
      "start_time": 0.0,
      "end_time": 2.5
    },
    {
      "merged_text": "真的很好",
      "original_indices": [1],
      "start_time": 2.5,
      "end_time": 5.0
    }
  ],
  "count": 2
}
```

**错误情况:**
- 400: 无效的索引或操作参数


## 11. 系统信息 (System)

提供系统相关信息，如可用字体、GPU 状态等。

### 11.1 获取可用字体列表
**GET** `/system/fonts`

获取系统可用的字体列表，用于字幕样式配置。

**Response Data:**
```json
{
  "fonts": ["Arial", "Microsoft YaHei", "SimHei", ...],
  "categorized": {
    "chinese": ["Microsoft YaHei", "SimHei", "SimSun", ...],
    "english": ["Arial", "Helvetica", "Times New Roman", ...],
    "other": [...]
  },
  "recommended": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial", "Helvetica"]
}
```

**字段说明:**
- `fonts`: 所有可用字体的完整列表
- `categorized`: 按类别分组的字体
  - `chinese`: 中文字体
  - `english`: 英文字体
  - `other`: 其他字体
- `recommended`: 推荐用于字幕的字体

### 11.2 获取 GPU 信息
**GET** `/system/gpu`

获取 GPU 信息和可用的硬件编码器。

**Response Data:**
```json
{
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 3080",
  "nvenc_available": true,
  "encoders": {
    "h264": [
      {"value": "libx264", "label": "H.264 (CPU)", "available": true},
      {"value": "h264_nvenc", "label": "H.264 NVENC (GPU)", "available": true}
    ],
    "h265": [
      {"value": "libx265", "label": "H.265 (CPU)", "available": true},
      {"value": "hevc_nvenc", "label": "H.265 NVENC (GPU)", "available": true}
    ]
  }
}
```

**字段说明:**
- `gpu_available`: 是否检测到 NVIDIA GPU
- `gpu_name`: GPU 名称（如果可用）
- `nvenc_available`: FFmpeg 是否支持 NVENC 编码
- `encoders`: 可用的编码器列表
  - `value`: 编码器标识符（用于配置）
  - `label`: 显示名称
  - `available`: 是否可用

### 11.3 生成字幕预览图
**POST** `/system/subtitle-preview`

使用 FFmpeg 生成字幕样式预览图，提供与实际视频合成一致的预览效果。

**Request Body:**
```json
{
  "translated_style": {
    "font_name": "Microsoft YaHei",
    "font_size": 24,
    "font_bold": false,
    "font_color": "#FFFFFF",
    "font_alpha": 1.0,
    "outline_width": 2,
    "outline_color": "#000000",
    "margin_v": 30,
    "background_enabled": false,
    "background_color": "#000000",
    "background_alpha": 0.5
  },
  "original_style": {
    "font_name": "Microsoft YaHei",
    "font_size": 18,
    "font_color": "#FFFACD",
    "font_alpha": 1.0,
    "outline_width": 1,
    "outline_color": "#000000",
    "margin_v": 60,
    "background_enabled": false,
    "background_color": "#000000",
    "background_alpha": 0.5
  },
  "translated_text": "这是翻译后的字幕示例",
  "original_text": "This is the original subtitle example",
  "width": 640,
  "height": 360
}
```

**字段说明:**
- `translated_style`: 翻译字幕样式配置
- `original_style`: 原始字幕样式配置
- `translated_text`: 翻译字幕预览文本
- `original_text`: 原始字幕预览文本
- `width`: 预览图宽度（默认 640）
- `height`: 预览图高度（默认 360）

**Response:** PNG 图片文件（image/png）

**说明:**
- 预览图会被缓存，相同参数的请求会返回缓存的图片
- 使用 FFmpeg ASS 滤镜渲染，效果与实际视频合成完全一致

### 11.4 清除字幕预览缓存
**DELETE** `/system/subtitle-preview/cache`

清除字幕预览图缓存。

**Response Data:**
```json
{
  "message": "Preview cache cleared"
}
```
