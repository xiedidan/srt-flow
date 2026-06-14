# TASK-088: 视频列表、详情、任务页集成 Agent 入口

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 6小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

在现有界面上增加进入视频 Agent 会话的入口，不重做原页面。

## 需求

1. 视频卡片/条目点击进入视频详情，并可切到 Agent 会话。
2. 视频卡片新增 Agent 快捷按钮。
3. 视频详情新增 Agent 会话入口或标签页。
4. 任务详情新增“进入视频 Agent 会话”入口。
5. 各步骤页面可从任务上下文返回视频 Agent 会话。
6. Timeline 每个步骤可跳转到原 ASR、翻译、TTS、合成、任务详情页面，并带上 video_id 或 task filter。

## 验收标准

- [ ] 视频列表卡片和条目模式均有 Agent 入口
- [ ] 下载中/处理中/已完成视频状态显示正确
- [ ] 从失败任务详情能返回对应视频 Agent 会话
- [ ] 从 Agent Timeline 能跳转到对应原步骤页面
- [ ] 不影响原 ASR / 翻译 / TTS / 合成任务创建流程

## 相关文件

- `frontend/src/components/videos/VideoCard.vue`
- `frontend/src/components/videos/VideoDetailModal.vue`
- `frontend/src/views/VideosView.vue`
- `frontend/src/components/tasks/TaskDetailModal.vue`
- `frontend/src/router/index.js`

## 依赖任务

- TASK-087

