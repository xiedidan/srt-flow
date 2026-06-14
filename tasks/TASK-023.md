---
id: TASK-023
title: 实现下载服务模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现视频下载服务，封装 yt-dlp 和 BiliDown 工具，支持 YouTube 和 Bilibili 视频下载。

# 验收标准 (Acceptance Criteria)
- [x] yt-dlp 命令封装
- [ ] BiliDown 命令封装 (预留接口，待实现)
- [x] 视频去重检查 (接口已定义)
- [x] 元数据提取与存储
- [x] 下载进度解析与上报
- [x] 视频目录结构创建

# 上下文 (Context)
- 参考 `docs/07-服务-下载服务设计.md`
- 目录：`backend/services/download.py`
