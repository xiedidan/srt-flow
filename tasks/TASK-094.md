# TASK-094: Agent 异常提醒与全局待处理中心

## 任务信息

- **优先级**: 中
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 8小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

当任务进入 waiting_user、repair_suggested 或 failed_needs_decision 状态时，系统应主动提示用户，并提供快速进入对应视频 Agent 会话的入口。

## 需求

1. 视频卡片显示 Agent 状态角标。
2. 顶部通知显示等待用户决策的视频数量。
3. 任务管理页支持 waiting_user / repair_suggested 状态过滤。
4. 新增全局“Agent 待确认”列表或入口。
5. 点击提醒后定位到对应视频 Session 和故障节点。

## 验收标准

- [ ] waiting_user 视频在视频列表有明显提示
- [ ] 顶部通知可显示待处理数量
- [ ] 任务页可过滤 Agent 待处理状态
- [ ] 点击提醒能打开正确视频 Agent Drawer
- [ ] 批量处理时不影响其他视频继续执行

## 相关文件

- `frontend/src/components/videos/VideoCard.vue`
- `frontend/src/components/AppHeader.vue`
- `frontend/src/views/TasksView.vue`
- `frontend/src/stores/agentSessions.js`
- `backend/app/routers/websocket.py`

## 依赖任务

- TASK-086
- TASK-087

