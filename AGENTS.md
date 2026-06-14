# SRT Flow Agent Rules

本文件适用于在本仓库工作的 Codex、OpenCode 等代码 Agent。规则来源于 `.kiro/steering/`，并结合本项目现有实现整理。除非用户另有明确要求，Agent 应遵守本文件。

## 身份与协作方式

- 你是 SRT Flow 项目的代码 Agent，不是通用聊天助手。
- 可以使用 Codex 或 OpenCode 的工具调用格式，但必须遵守本仓库规则。
- 与用户沟通、提交说明、用户文档使用中文。
- 代码注释、内部变量命名、提交信息可使用英文；面向用户的说明优先中文。
- 不要泄露、记录或复制用户口令、API Key、Token、Cookie 等敏感信息。需要 sudo 或外部认证时，让用户在本机完成或临时提供，不要写入仓库文档。

## 项目概述

SRT Flow 是视频处理 Web 工具，支持：

- YouTube / Bilibili 视频下载
- 语音识别 ASR
- 字幕翻译
- 语音合成 TTS
- 视频合成
- 素材生成
- 在线预览与编辑

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue.js 3 + Pinia + Axios |
| 后端 | FastAPI (Python 3.12) |
| 数据库 | SQLite + SQLAlchemy |
| 任务队列 | 自研 SQLite 持久化队列 |
| 部署 | Docker Compose，服务端口 8010 |

## 目录结构

```text
backend/
  app/          FastAPI 入口与 routers
  core/         Config, DB, Logger, Models, Repositories
  services/     下载、ASR、翻译、TTS、合成、素材、编辑等业务服务
  workers/      队列、调度器、工作进程
frontend/
  src/          Vue 前端源码
deploy/         Dockerfile, docker-compose.yml
docs/           设计文档
tasks/          项目任务文件
data/           运行时数据，gitignored
```

## 开发环境

- 本地开发环境基于 WSL1 Ubuntu 24.04。
- 使用 PowerShell 启动和停止调试服务：
  - 启动：`start.ps1`
  - 停止：`stop.ps1`
- 本机代理：`http://127.0.0.1:10809`，用于访问受限网络。
- 不要把本机密码、临时 Token 或用户私有路径写进代码、日志或文档。

## 任务开始前必读

开始涉及代码或文档变更的任务前，至少阅读：

- `KANBAN.md`
- `项目管理模式文档.md`
- `系统架构文档.md`
- `API文档.md`

如果任务只涉及很小的局部修复，也应快速确认相关模块文档是否存在，例如 `docs/XX-...设计.md`。

## 任务完成后必检查

任务完成后，根据影响范围检查并更新：

- `KANBAN.md`：任务状态是否与实际一致
- `README.md`：如果影响用户使用方式
- `需求文档.md`：如果新增或修改需求
- `系统架构文档.md`：如果修改系统架构
- `API文档.md`：如果修改 API
- `docs/XX-...设计.md`：如果修改模块设计

创建新文档后，需要同步更新对应文档索引。

## 项目管理规则

- 看板：`KANBAN.md`
- 任务详情：`tasks/TASK-XXX.md`
- 领取任务前更新看板。
- 同一时间只处理一个任务。
- 完成后移至 Review。
- 如果用户临时指定任务，不要机械新增任务文件；优先完成用户当前请求，再按影响范围补文档。

## 配置管理规则

配置分三层：

1. 系统级：`.env`，如数据库路径、端口、加密密钥。
2. 全局配置：SQLite，如默认语言、代理、日志级别。
3. 功能配置：SQLite，如下载、ASR、翻译、TTS、合成、素材生成等模块配置。

### 配置字段同步

后端配置模型与前端设置 schema 必须同步：

- 后端配置字段在 `backend/core/config.py`。
- 前端配置 schema 在 `frontend/src/views/SettingsView.vue`。
- 后端新增字段时，前端必须新增中文 `label` 和必要属性。
- 删除后端字段时，同步删除前端 schema 和 `backend/app/main.py` 中相关预处理逻辑。
- 项目处于开发阶段，不保留 legacy 字段做兼容。

### 条件显示

- 设置项条件显示使用 `showWhen`。
- 格式：`showWhen: { fieldName: [allowedValues] }`。
- 示例：Gemini API Key 只在识别引擎为 Gemini 时显示。
- 示例：Whisper 模型大小只在识别引擎为本地 Whisper 时显示。

## 敏感信息与安全规则

- API Key 传输：前端使用 RSA-OAEP (SHA-256) 公钥加密。
- API Key 存储：后端使用 AES-256-GCM 加密存储。
- 前端只能显示脱敏串，例如 `sk-a****key1`。
- 前端除用户输入框外，不得获取 API Key 明文或密文。
- 日志、任务结果、WebSocket、浏览器控制台不得输出 API Key 明文。
- 不要将 `.env`、数据库、Cookie、Token 或本机凭据提交到仓库。

## 本机权限环境

- WSL2 Ubuntu 24.04 默认以 `root` 用户运行，不需要 `sudo`。
- PowerShell 环境没有启用 `sudo`，不要在 PowerShell 命令中使用 `sudo`。
- 不要配置 sudoers，除非用户明确要求切换到非 root Linux 用户。
- 高风险系统操作仍需先向用户说明并获得确认。

## Git 版本管理规则

- 本项目必须使用 Git 管理，默认分支为 `main`。
- Agent 开始修改前先查看 `git status --short --branch`，不要覆盖用户未提交的改动。
- 运行时数据、密钥、本机依赖和构建产物不得提交，包括 `.env`、`data/`、`venv/`、`node_modules/`、日志、数据库文件、模型权重和前端构建产物。
- 远端仓库默认命名为 `srt-flow`，远端名使用 `origin`。
- `main` 分支必须保持可运行、可回滚，不直接在 `main` 上开发新 Feature。
- 新 Feature、架构调整、跨模块改动必须从最新 `main` 新建分支实现，分支命名建议使用 `feature/<short-name>`、`fix/<short-name>`、`docs/<short-name>`。
- 小型文档修正或用户明确要求的即时改动，可以在 `main` 上直接提交，但提交前仍需确认工作区干净且变更范围清楚。
- Feature 分支完成后，先执行必要检查，再合并回 `main`；合并方式优先使用 `--no-ff` 或 Pull Request，保留 Feature 边界。
- 合并回 `main` 后再推送 `origin/main`；不要把未完成的实验性分支合并进 `main`。
- 一次提交只覆盖一组相关变更，提交信息要简短说明目的，推荐格式：`feat: ...`、`fix: ...`、`docs: ...`、`chore: ...`。
- 推送前检查 `git status --short --branch`、`git log --oneline -5` 和远端地址，确认没有误提交敏感文件或运行时产物。
- 未经用户明确要求，不执行 `git reset --hard`、强制推送或删除分支。
- 如需清理历史、重写提交或变基公共分支，必须先向用户说明风险并获得明确确认。

## API 规范

基础路径：

```text
/api/v1
```

统一响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 前端调用规范

前端 Axios 拦截器会自动解包响应：

```javascript
const { data } = await api.get('/stats')
```

不要写：

```javascript
const response = await api.get('/stats')
// 错误：response.data.code 不存在
// 错误：response.data.data 不存在
```

WebSocket：

```text
/ws/status
```

用于实时任务状态推送。

## 任务系统规则

任务状态流转：

```text
pending -> running -> completed
                  \-> failed -> retry -> pending
```

- 每种任务类型最多 1 个并发。
- 不同任务类型可并行运行。
- 支持任务时段控制。
- 进度计算有两类：
  - 主动拆分：如字幕翻译按批次计算。
  - 被动接收：如 FFMPEG 输出解析。

修改任务系统时必须关注：

- `backend/core/models.py` 中 `TaskType`、`TaskStatus`、`Task`。
- `backend/workers/queue.py` 的状态流转和并发控制。
- `backend/workers/scheduler.py` 的重试、超时、流水线触发。
- `backend/app/main.py` 当前包含大量任务前处理逻辑，新增任务配置时需同步检查。
- 前端任务列表、任务详情、WebSocket 状态展示是否同步。

## 视频目录结构

每个视频独立目录：

```text
data/downloads/<UUID>_<SafeTitle>/
  video.mp4
  video.info.json
  audio_original.m4a
  subtitle_original.srt
  subtitle_translated.srt
  audio_tts.m4a
  video_output.mp4
  assets/
    thumbnail.jpg
    summary.txt
    title_candidates.txt
  task.log
```

修改文件产物、预览、编辑、合成逻辑时，必须保持该目录约定，避免破坏已有视频数据。

## 外部工具

| 工具 | 用途 |
| --- | --- |
| `yt-dlp` | YouTube 下载 |
| `BiliDown` | Bilibili 下载 |
| `ffmpeg` | 音视频处理 |
| `ffprobe` | 视频编码检测 |
| `Whisper` | 语音识别，默认 large-v3 |
| Coqui TTS / ChatTTS / SparkTTS / IndexTTS / CozyVoice / VITS | 语音合成 |

### 视频编码兼容性

- HEVC/H265 在多数浏览器中不能原生播放。
- 后端使用 `ffprobe` 检测编码，返回 `video_codec` 和 `browser_compatible`。
- 前端 `VideoPlayer` 收到不兼容编码时显示黄色警告，提示用户重新下载时勾选“强制 H264 编码”。

## 前端规则

- 列表页面支持卡片模式和条目模式。
- 视图模式持久化到 `localStorage`。
- 每个列表页面独立记忆视图模式。
- 新增 API 调用时，优先在 `frontend/src/api/` 下封装。
- 新增跨页面状态时，优先使用 Pinia store。
- 设置页字段必须有中文标签，避免用户看到英文字段名。
- 不要在 UI 中展示 API Key 明文或密文。

## 后端规则

- FastAPI Router 放在 `backend/app/routers/`。
- 业务逻辑优先放在 `backend/services/`。
- 数据访问优先通过 `backend/core/repositories.py`。
- ORM 模型在 `backend/core/models.py`。
- 任务执行服务应尽量实现统一的 `BaseService.execute()` 风格。
- 避免把新的复杂业务逻辑继续堆进 `backend/app/main.py`；如必须接入当前 worker loop，后续应提取为 service/helper。

## 文档索引

| 用途/模块 | 文档 |
| --- | --- |
| 用户使用说明 | `README.md` |
| 项目管理 | `项目管理模式文档.md` / `KANBAN.md` |
| 整体架构设计 | `系统架构文档.md` |
| 需求 | `原始需求.md` / `需求调研问卷.md` / `需求文档.md` |
| 配置管理器 | `docs/01-核心-配置管理器设计.md` |
| 数据库管理器 | `docs/02-核心-数据库管理器设计.md` |
| 日志管理器 | `docs/03-核心-日志管理器设计.md` |
| 队列管理器 | `docs/04-调度-队列管理器设计.md` |
| 工作进程 | `docs/05-调度-工作进程设计.md` |
| 调度器 | `docs/06-调度-调度器设计.md` |
| 下载服务 | `docs/07-服务-下载服务设计.md` |
| 媒体管理 | `docs/08-服务-媒体管理服务设计.md` |
| 语音识别 | `docs/09-服务-语音识别服务设计.md` |
| 翻译服务 | `docs/10-服务-翻译服务设计.md` |
| 语音合成 | `docs/11-服务-语音合成服务设计.md` |
| 视频合成 | `docs/12-服务-视频合成服务设计.md` |
| 素材生成 | `docs/13-服务-素材生成服务设计.md` |
| 编辑服务 | `docs/14-服务-编辑服务设计.md` |
| AI 配置重构 | `docs/15-AI配置重构设计.md` |
| 流程管理 | `docs/16-功能-流程管理设计.md` |

## 验证建议

- 后端改动：优先运行相关 Python 单测或最小 API 调用验证。
- 前端改动：优先运行 `npm run build` 或对应页面手动验证。
- 涉及视频、字幕、音频、FFMPEG 的改动：用小样本文件验证，避免长视频阻塞。
- 涉及配置、安全、API Key 的改动：必须验证脱敏、加密和前后端字段同步。
