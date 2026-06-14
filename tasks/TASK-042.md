---
id: TASK-042
title: 字幕调整功能
status: Review
assignee: Kiro
priority: Low
---

# 任务描述

提供类似于 Subtitle Edit 的双语字幕调整功能，让用户可以对字幕进行精细编辑。

# 需求来源

docs/需求日记.md - 字幕调整功能

# 功能要点

1. 字幕时间轴调整（开始时间、结束时间）
2. 字幕文本编辑（原文、译文）
3. 字幕行的增删改
4. 字幕合并与拆分
5. 双语字幕对照显示
6. 与视频播放器联动预览

# 验收标准 (Acceptance Criteria)

- [x] 实现字幕编辑器组件，支持双语字幕显示
- [x] 支持字幕时间轴调整
- [x] 支持字幕文本编辑
- [x] 支持字幕行的增加、删除
- [x] 支持字幕行的合并与拆分
- [x] 编辑器与视频播放器联动，可预览效果
- [x] 编辑后的字幕可保存

# 上下文 (Context)

- 参考 `docs/14-服务-编辑服务设计.md` 了解编辑服务设计
- 参考 `frontend/src/components/preview/SubtitleEditor.vue` 了解现有字幕编辑组件
- 参考 Subtitle Edit 软件了解功能设计
