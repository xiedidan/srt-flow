# TASK-086: 视频 Agent Session 与任务对话后端 API

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 8小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

实现视频级 Agent 会话和任务对话 API。用户可以读取某个视频的 Agent Session、发送消息、查看待确认修复方案、批准/拒绝方案、修改限制条件。

## 需求

1. 新增 Agent Session Router。
2. 支持按 video_id 获取或创建视频 Agent Session。
3. 支持读取 Workflow Timeline、节点状态、消息列表、Evidence 摘要。
4. 支持用户发送自由文本限制。
5. 支持 pending_action 的批准、拒绝、修改限制。
6. WebSocket 增加 Agent Session / waiting_user 更新事件。

## API 草案

```text
GET  /api/v1/videos/{video_id}/agent-session
POST /api/v1/videos/{video_id}/agent-session/messages
POST /api/v1/agent-sessions/{session_id}/actions/{action_id}/approve
POST /api/v1/agent-sessions/{session_id}/actions/{action_id}/reject
PATCH /api/v1/agent-sessions/{session_id}/constraints
```

## 验收标准

- [ ] 能获取单视频 Agent Session
- [ ] 能发送用户消息并保存
- [ ] 能返回当前节点、参数摘要、状态和 Evidence
- [ ] 能处理 pending_action 的批准/拒绝
- [ ] WebSocket 能推送 waiting_user / repair_suggested

## 相关文件

- `backend/app/routers/agent_sessions.py`（建议新增）
- `backend/app/routers/websocket.py`
- `backend/app/routers/__init__.py`
- `backend/app/schemas.py`

## 依赖任务

- TASK-084
- TASK-085

