---
id: TASK-037
title: 编写 Dockerfile 和部署配置
status: Review
assignee: Kiro
priority: Medium
---

# 任务描述
编写 Docker 部署配置，包括 Dockerfile、docker-compose.yml，支持 GPU 加速。

# 验收标准 (Acceptance Criteria)
- [x] 后端 Dockerfile（含 FFmpeg、yt-dlp）
- [x] 前端构建集成
- [x] docker-compose.yml 配置
- [x] 数据卷挂载配置
- [x] GPU 支持配置（NVIDIA Runtime）
- [x] 环境变量配置示例

# 上下文 (Context)
- 参考 `系统架构文档.md` 6. 部署方案设计
- 目录：`deploy/`

# 实现说明

## 创建的文件

### deploy/Dockerfile
- 多阶段构建：前端构建 + 后端运行时
- 基于 Python 3.12-slim
- 包含 FFmpeg、yt-dlp、中文字体
- 非 root 用户运行
- 健康检查配置

### deploy/Dockerfile.gpu
- GPU 版本，基于 nvidia/cuda:12.1
- 包含 PyTorch + CUDA 支持
- 预装 openai-whisper
- 模型缓存卷挂载

### deploy/docker-compose.yml
- 标准部署配置
- 数据卷挂载 (data/)
- 环境变量配置
- 日志轮转配置
- 开发模式 profile

### deploy/docker-compose.gpu.yml
- GPU 部署配置
- NVIDIA Runtime 配置
- GPU 资源预留
- Whisper 模型缓存卷

### deploy/entrypoint.sh
- 启动脚本
- 打印版本信息
- 初始化数据库
- GPU 检测

### deploy/.env.example
- 环境变量示例
- 安全密钥生成说明

### .dockerignore
- Docker 构建忽略文件
