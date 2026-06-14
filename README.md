# SRT Flow

<p align="center">
  <strong>视频处理全流程自动化工具</strong>
</p>

<p align="center">
  从 YouTube/Bilibili 视频下载到语音识别、字幕翻译、语音合成、视频合成的一站式解决方案
</p>

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🎬 视频下载 | 支持 YouTube、Bilibili 公开视频下载，自动提取元数据 |
| 🎤 语音识别 | 基于 Whisper 的本地语音识别，支持 GPU 加速 |
| 🌐 字幕翻译 | 支持 DeepSeek、Gemini、OpenAI 等多种 LLM |
| 🔊 语音合成 | 多种 TTS 引擎（Coqui TTS、ChatTTS、VITS 等） |
| 🎥 视频合成 | 字幕烧录、音轨替换，可配置字幕样式 |
| 📝 素材生成 | 自动生成标题、摘要、缩略图 |
| ✏️ 在线编辑 | 字幕预览与编辑，时间轴调整 |

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/srt-flow.git
cd srt-flow

# 2. 配置环境变量
cp deploy/.env.example .env
# 编辑 .env，设置 SECRET_KEY 和 ENCRYPTION_KEY

# 3. 启动服务
cd deploy
docker-compose up -d

# 4. 访问 http://localhost:8010
```

### 方式二：GPU 部署（Whisper/TTS 加速）

需要先安装 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

```bash
cd deploy
docker-compose -f docker-compose.gpu.yml up -d
```

### 方式三：本地开发

#### 环境准备

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 3. 安装后端依赖
pip install -r requirements.txt

# 4. 安装前端依赖
cd frontend
npm install
cd ..

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 SECRET_KEY 和 ENCRYPTION_KEY

# 6. 安装 7-Zip（用于解压引擎文件）
# Windows: 下载并安装 https://www.7-zip.org/download.html
# Linux: sudo apt install p7zip-full
# macOS: brew install p7zip
```

#### Windows 下配置 7-Zip

如果使用 Windows 开发，需要将 7-Zip 添加到 PATH 环境变量：

1. **下载并安装 7-Zip**
   - 访问 https://www.7-zip.org/download.html
   - 下载 64-bit 版本（推荐）
   - 默认安装到 `C:\Program Files\7-Zip\`

2. **添加到 PATH 环境变量**
   - 右键点击「此电脑」→「属性」
   - 点击「高级系统设置」
   - 点击「环境变量」
   - 在「系统变量」中找到 `Path`，点击「编辑」
   - 点击「新建」，添加：`C:\Program Files\7-Zip\`
   - 点击「确定」保存

3. **验证安装**
   ```cmd
   # 打开新的命令行窗口
   7z
   # 应该显示 7-Zip 的版本信息
   ```

> **注意**：如果不想配置 PATH，代码会自动检测常见安装路径，但建议配置 PATH 以获得更好的兼容性。

#### 启动开发服务器

**方式 A：使用启动脚本（推荐）**

```bash
# Linux/macOS
chmod +x scripts/*.sh
./scripts/dev-backend.sh   # 终端 1：后端（支持热更新）
./scripts/dev-frontend.sh  # 终端 2：前端（支持热更新）

# Windows
scripts\dev-backend.bat    # 终端 1：后端（支持热更新）
scripts\dev-frontend.bat   # 终端 2：前端（支持热更新）
```

**方式 B：手动启动**

```bash
# 终端 1：后端（支持热更新）
uvicorn backend.app.main:app --reload --reload-dir backend --host 0.0.0.0 --port 8010

# 终端 2：前端（支持热更新）
cd frontend
npm run dev
```

#### 访问应用

- 前端开发服务器：http://localhost:5173
- 后端 API：http://localhost:8010
- API 文档：http://localhost:8010/docs

#### 开发说明

- **后端热更新**：修改 `backend/` 目录下的 Python 文件会自动重启服务
- **前端热更新**：修改 `frontend/src/` 目录下的文件会自动刷新浏览器
- **数据库**：开发环境使用 SQLite，数据文件位于 `data/srtflow.db`
- **日志**：后端日志输出到控制台和 `data/logs/` 目录

## 📖 使用指南

### 1. 下载视频

1. 进入「视频管理」页面
2. 点击「下载视频」按钮
3. 输入 YouTube 或 Bilibili 视频链接
4. 等待下载完成

### 2. 语音识别

1. 选择已下载的视频
2. 点击「识别」按钮
3. 选择 Whisper 模型（推荐 large-v3）
4. 等待识别完成，生成原始字幕

### 3. 字幕翻译

1. 选择有原始字幕的视频
2. 点击「翻译」按钮
3. 选择目标语言和 LLM 提供商
4. 等待翻译完成

### 4. 视频合成

1. 选择有翻译字幕的视频
2. 点击「视频」按钮
3. 配置字幕样式（字体、颜色、位置等）
4. 选择是否替换音轨
5. 等待合成完成

### 5. 预览与编辑

1. 在视频详情中点击「预览」
2. 可切换原文/译文/双语字幕显示
3. 在编辑模式下可修改字幕内容和时间轴
4. 保存修改

## ⚙️ 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HOST` | 服务监听地址 | `0.0.0.0` |
| `PORT` | 服务端口 | `8010` |
| `DEBUG` | 调试模式 | `false` |
| `SECRET_KEY` | 会话密钥 | 必填 |
| `ENCRYPTION_KEY` | API Key 加密密钥 | 必填 |
| `DATABASE_PATH` | 数据库路径 | `data/srtflow.db` |
| `DOWNLOADS_DIR` | 下载目录 | `data/downloads` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `CUDA_VISIBLE_DEVICES` | GPU 设备 | `0` |

### 生成密钥

```bash
# 生成 SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# 生成 ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

### API Key 配置

在 Web 界面的「设置」页面配置各服务的 API Key：

- **翻译服务**：DeepSeek / Gemini / OpenAI API Key
- **素材生成**：LLM API Key、绘图接口配置

> 注意：API Key 会加密存储，前端只能修改不能查看明文

## 📁 目录结构

```
srt-flow/
├── backend/              # FastAPI 后端
│   ├── app/              # API 路由
│   ├── core/             # 核心组件
│   ├── services/         # 业务服务
│   └── workers/          # 任务调度
├── frontend/             # Vue.js 前端
│   └── src/
├── deploy/               # Docker 部署
│   ├── Dockerfile
│   ├── Dockerfile.gpu
│   └── docker-compose.yml
├── docs/                 # 设计文档
├── data/                 # 运行时数据
│   ├── downloads/        # 视频文件
│   ├── logs/             # 日志文件
│   └── srtflow.db        # SQLite 数据库
└── requirements.txt
```

### 视频文件结构

每个视频独立目录：

```
data/downloads/<UUID>_<标题>/
├── video.mp4              # 原始视频
├── video.info.json        # 元数据
├── subtitle_original.srt  # 原始字幕
├── subtitle_translated.srt # 翻译字幕
├── audio_tts.m4a          # 合成语音
├── video_output.mp4       # 输出视频
└── assets/                # 素材
    ├── thumbnail.jpg
    └── summary.txt
```

## 💻 系统要求

### 最低配置

- CPU: 4 核
- 内存: 8 GB
- 存储: 50 GB（视频文件较大）
- 系统: Linux / Windows / macOS

### 推荐配置（GPU 加速）

- CPU: 8 核
- 内存: 16 GB
- GPU: NVIDIA RTX 3060 或更高（8GB+ 显存）
- CUDA: 12.1+
- 存储: 100 GB SSD

### 软件依赖

| 软件 | 版本 | 用途 |
|------|------|------|
| Docker | 20.10+ | 容器化部署 |
| Docker Compose | 2.0+ | 服务编排 |
| Python | 3.12+ | 后端运行时 |
| Node.js | 20+ | 前端构建 |
| FFmpeg | 6.0+ | 音视频处理 |
| yt-dlp | 最新 | 视频下载 |
| 7-Zip | 最新 | 引擎文件解压（推荐） |

## ❓ 常见问题

### Q: 下载视频失败？

A: 检查以下几点：
1. 确保视频是公开的（不需要登录）
2. 检查网络连接
3. 更新 yt-dlp 到最新版本：`pip install -U yt-dlp`

### Q: Whisper 识别很慢？

A: 
1. 使用 GPU 版本部署可大幅加速
2. 可以选择较小的模型（如 medium）牺牲精度换速度
3. 确保 CUDA 正确安装

### Q: API Key 配置后不生效？

A:
1. 确保在设置页面正确保存
2. 检查 API Key 格式是否正确
3. 查看后端日志排查错误

### Q: 字幕时间轴不准确？

A:
1. 使用预览编辑功能手动调整
2. 可以使用「整体偏移」功能批量调整
3. 重新运行语音识别

### Q: Docker 构建失败？

A:
1. 确保 Docker 和 Docker Compose 版本符合要求
2. 检查网络连接（需要下载依赖）
3. 清理缓存重试：`docker-compose build --no-cache`

### Q: GPU 不被识别？

A:
1. 确认 NVIDIA 驱动已安装：`nvidia-smi`
2. 安装 NVIDIA Container Toolkit
3. 使用 `docker-compose.gpu.yml` 配置文件

## 📚 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档](需求文档.md) | 功能需求详细说明 |
| [系统架构文档](系统架构文档.md) | 技术架构设计 |
| [API 文档](API文档.md) | REST API 接口说明 |
| [项目管理模式文档](项目管理模式文档.md) | 开发流程规范 |
| [开发环境配置](docs/开发环境配置.md) | 本地开发环境搭建指南 |
| [配置说明](docs/配置说明.md) | 详细配置项说明 |

### 模块设计文档

- [配置管理器](docs/01-核心-配置管理器设计.md)
- [数据库管理器](docs/02-核心-数据库管理器设计.md)
- [日志管理器](docs/03-核心-日志管理器设计.md)
- [队列管理器](docs/04-调度-队列管理器设计.md)
- [工作进程](docs/05-调度-工作进程设计.md)
- [调度器](docs/06-调度-调度器设计.md)
- [下载服务](docs/07-服务-下载服务设计.md)
- [媒体管理](docs/08-服务-媒体管理服务设计.md)
- [语音识别](docs/09-服务-语音识别服务设计.md)
- [翻译服务](docs/10-服务-翻译服务设计.md)
- [语音合成](docs/11-服务-语音合成服务设计.md)
- [视频合成](docs/12-服务-视频合成服务设计.md)
- [素材生成](docs/13-服务-素材生成服务设计.md)
- [编辑服务](docs/14-服务-编辑服务设计.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
