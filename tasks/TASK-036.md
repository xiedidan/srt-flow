---
id: TASK-036
title: 实现前端预览与编辑功能
status: Review
assignee: Kiro
priority: Medium
---

# 任务描述
实现前端预览与编辑功能，包括视频播放器、字幕编辑器、字幕预览。

# 验收标准 (Acceptance Criteria)
- [x] 视频播放器组件（支持字幕显示）
- [x] 字幕编辑器组件
- [x] 字幕时间轴调整
- [x] 双字幕切换预览
- [x] 编辑保存功能

# 实现说明

## 新增组件
- `frontend/src/components/preview/VideoPlayer.vue` - 视频播放器组件
  - 支持播放/暂停、进度条、音量控制、全屏
  - 支持字幕叠加显示（原文/译文/双语/关闭）
  - 支持键盘快捷键（空格播放、方向键快进/后退）
  
- `frontend/src/components/preview/SubtitleEditor.vue` - 字幕编辑器组件
  - 支持字幕文本编辑
  - 支持时间轴调整（开始/结束时间）
  - 支持添加/删除/插入字幕条目
  - 支持整体时间偏移
  - 支持导出 SRT 文件
  - 点击字幕跳转到对应时间点
  
- `frontend/src/components/preview/PreviewModal.vue` - 预览编辑主模态
  - 预览标签页：视频播放 + 只读字幕列表
  - 编辑标签页：迷你播放器 + 可编辑字幕列表
  - 支持原始字幕/翻译字幕切换编辑
  - 保存功能调用后端 API

## 修改文件
- `frontend/src/components/videos/VideoDetailModal.vue` - 集成预览功能
  - 添加"预览"按钮
  - 文件列表中的字幕文件添加"编辑"按钮
  
- `backend/app/routers/videos.py` - 添加视频流式播放接口
  - `GET /videos/{video_id}/stream` - 支持 Range 请求

# 上下文 (Context)
- 参考 `需求文档.md` 4.8 节预览调整
- 目录：`frontend/src/components/`
