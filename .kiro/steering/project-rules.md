# SRT Flow 项目规则

## 项目概述

SRT Flow 是视频处理 Web 工具，支持 YouTube/Bilibili 视频下载、语音识别、字幕翻译、语音合成、视频合成、素材生成。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue.js 3 + Pinia + Axios |
| 后端 | FastAPI (Python 3.12) |
| 数据库 | SQLite + SQLAlchemy |
| 任务队列 | 自研持久化队列 (SQLite) |
| 部署 | Docker Compose |

## 目录结构

```
srt-flow/
├── backend/
│   ├── app/          # FastAPI 入口
│   ├── core/         # 核心组件 (Config, DB, Logger)
│   ├── services/     # 业务服务
│   └── workers/      # 任务消费者
├── frontend/
│   └── src/
├── deploy/           # Dockerfile, docker-compose.yml
├── docs/             # 设计文档
├── tasks/            # 任务管理文件
└── data/             # 运行时数据 (gitignore)
```

## 配置管理

### 分层

1. **系统级** (.env)：数据库路径、端口、加密密钥
2. **全局配置** (SQLite)：默认语言、日志级别
3. **功能配置** (SQLite)：各服务独立配置

### 敏感信息

- **传输加密**：前端使用 RSA-OAEP (SHA-256) 公钥加密 API Key
- **存储加密**：后端使用 AES-256-GCM 加密存储
- **脱敏显示**：前端只能获取混淆串（前4字符+****+后4字符，如 `sk-a****key1`）
- 前端除用户输入外，不能获取明文或密文的 API Key

### 配置项条件显示

- 配置表单只显示当前状态下可用的配置项
- 使用 `showWhen` 定义显示条件，格式：`{ fieldName: [allowedValues] }`
- 示例：Gemini API Key 只在识别引擎为 Gemini 时显示
- 示例：Whisper 模型大小只在识别引擎为 Whisper 本地时显示

### 配置字段同步规则

后端配置模型 (`backend/core/config.py`) 与前端配置 schema (`frontend/src/views/SettingsView.vue`) 必须保持同步：

1. **后端返回的所有字段必须在前端 schema 中定义**
   - 未定义的字段会以英文字段名显示在界面上
   - 每个字段需要定义 `label`（中文标签）和其他必要属性

2. **废弃字段必须同时从前后端删除**
   - 项目处于开发阶段，不保留 legacy 字段做向后兼容
   - 删除后端字段时，同步删除 `main.py` 中相关的预处理逻辑
   - 确保前端 schema 中没有对应的定义

3. **新增字段的检查清单**
   - [ ] 后端 `config.py` 中添加字段定义
   - [ ] 前端 `SettingsView.vue` 中添加 schema 定义（含中文 label）
   - [ ] 如需条件显示，添加 `showWhen` 配置
   - [ ] 如有预处理逻辑，在 `main.py` 中添加

## 任务系统

### 状态流转

```
pending → running → completed
              ↓
           failed → (retry) → pending
```

### 并发控制

- 每种任务类型最多 1 个并发
- 不同类型可并行（流水线）
- 支持任务时段控制

### 进度计算

- 主动拆分：批次进度（如翻译 30 条/批）
- 被动接收：外部工具输出（如 FFMPEG）

## API 规范

### 基础路径

`/api/v1`

### 响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": { }
}
```

### 前端 API 调用规范

前端使用 Axios 拦截器统一处理响应格式，拦截器会自动解包响应：
- 原始响应：`{ code: 0, message: "success", data: {...} }`
- 拦截器返回：`{ data: {...}, message: "success" }`

**正确用法：**
```javascript
const { data } = await api.get('/stats')
// data 直接是业务数据，不需要再访问 response.data.data
```

**错误用法：**
```javascript
const response = await api.get('/stats')
// ❌ response.data.code 不存在，拦截器已解包
// ❌ response.data.data 不存在
```

### WebSocket

`/ws/status` - 实时任务状态推送

## 文件管理

### 视频目录结构

```
data/downloads/<UUID>_<SafeTitle>/
├── video.mp4              # 原始视频
├── video.info.json        # 元数据
├── audio_original.m4a     # 原声音频
├── subtitle_original.srt  # 原始字幕
├── subtitle_translated.srt
├── audio_tts.m4a
├── video_output.mp4
├── assets/
│   ├── thumbnail.jpg
│   ├── summary.txt
│   └── title_candidates.txt
└── task.log
```

## 外部工具

| 工具 | 用途 |
|------|------|
| yt-dlp | YouTube 下载 |
| BiliDown | Bilibili 下载 |
| ffmpeg | 音视频处理 |
| ffprobe | 视频编码检测 |
| Whisper | 语音识别 (large-v3) |
| Coqui TTS / ChatTTS / SparkTTS / IndexTTS / CozyVoice / VITS | 语音合成 |

## 视频编码兼容性

### 浏览器预览限制

- HEVC (H265) 编码的视频在大多数浏览器中无法原生播放

### 编码检测与提示

- 后端使用 ffprobe 检测视频编码，返回 `video_codec` 和 `browser_compatible` 字段
- 前端 VideoPlayer 组件接收编码信息，不兼容时显示黄色警告条
- 警告提示用户重新下载时勾选"强制 H264 编码"选项

## 前端交互

### 列表视图模式

- 各列表界面支持卡片模式和条目模式切换
- 用户选择的视图模式需要持久化到 localStorage
- 每个列表页面独立记忆各自的视图模式

## 项目管理

### 看板

`KANBAN.md` - 任务状态总览

### 任务文件

`tasks/TASK-XXX.md` - 任务详情

### 协作规则

1. 领取任务前更新 KANBAN
2. 同一时间只处理一个任务
3. 完成后移至 Review

## 部署

### 端口

- 服务端口：8010

### Docker

```bash
docker-compose up -d
```

### 数据持久化

- 挂载 `data/` 目录
- 挂载 `config/` 目录

### GPU 支持

配置 NVIDIA Runtime 用于 Whisper/TTS等 加速

## 文档索引

| 用途/模块 | 文档 |
|------|------|
| 用户使用说明 | README.md |
| 项目管理 | 项目管理模式文档.md / KANBAN.md |
| 整体架构设计 | 系统架构文档.md |
| 需求 | 原始需求.md / 需求调研问卷.md / 需求文档.md |
| 配置管理器 | docs/01-核心-配置管理器设计.md |
| 数据库管理器 | docs/02-核心-数据库管理器设计.md |
| 日志管理器 | docs/03-核心-日志管理器设计.md |
| 队列管理器 | docs/04-调度-队列管理器设计.md |
| 工作进程 | docs/05-调度-工作进程设计.md |
| 调度器 | docs/06-调度-调度器设计.md |
| 下载服务 | docs/07-服务-下载服务设计.md |
| 媒体管理 | docs/08-服务-媒体管理服务设计.md |
| 语音识别 | docs/09-服务-语音识别服务设计.md |
| 翻译服务 | docs/10-服务-翻译服务设计.md |
| 语音合成 | docs/11-服务-语音合成服务设计.md |
| 视频合成 | docs/12-服务-视频合成服务设计.md |
| 素材生成 | docs/13-服务-素材生成服务设计.md |
| 编辑服务 | docs/14-服务-编辑服务设计.md |
| AI 配置重构 | docs/15-AI配置重构设计.md |
